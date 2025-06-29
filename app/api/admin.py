from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, cast
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional, List
from datetime import datetime, timedelta
from app.core.database import get_db
from app.middleware.auth import get_admin_user
from app.models.user import User
from app.models.task import Task, TaskStatus, TaskPriority
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogList, SystemStats

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/audit-logs", response_model=AuditLogList)
async def get_audit_logs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user_id: Optional[int] = Query(None),
    task_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin only: View audit trail with filtering"""
    offset = (page - 1) * size
    
    query = db.query(AuditLog)
    
    # Apply filters
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if task_id:
        query = query.filter(AuditLog.task_id == task_id)
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    if date_from:
        query = query.filter(AuditLog.timestamp >= date_from)
    if date_to:
        query = query.filter(AuditLog.timestamp <= date_to)
    
    # Order by timestamp desc
    query = query.order_by(desc(AuditLog.timestamp))
    
    total = query.count()
    logs = query.offset(offset).limit(size).all()
    
    return {
        "logs": logs,
        "total": total,
        "page": page,
        "size": size
    }


@router.get("/system-stats", response_model=SystemStats)
async def get_system_stats(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin only: Dashboard statistics"""
    # User statistics
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    
    # Task statistics
    total_tasks = db.query(Task).filter(Task.is_deleted == False).count()
    
    # Tasks by status
    tasks_by_status = {}
    for status in TaskStatus:
        count = db.query(Task).filter(
            Task.status == status,
            Task.is_deleted == False
        ).count()
        tasks_by_status[status.value] = count
    
    # Tasks by priority
    tasks_by_priority = {}
    for priority in TaskPriority:
        count = db.query(Task).filter(
            Task.priority == priority,
            Task.is_deleted == False
        ).count()
        tasks_by_priority[priority.value] = count
    
    # Recent activities (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_activities = db.query(AuditLog).filter(
        AuditLog.timestamp >= yesterday
    ).count()
    
    return SystemStats(
        total_users=total_users,
        active_users=active_users,
        total_tasks=total_tasks,
        tasks_by_status=tasks_by_status,
        tasks_by_priority=tasks_by_priority,
        recent_activities=recent_activities
    )


@router.post("/bulk-assign")
async def bulk_assign_tasks(
    task_ids: List[int],
    user_id: int,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin only: Bulk task assignment"""
    # Validate user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )
    
    # Get tasks
    tasks = db.query(Task).filter(
        Task.id.in_(task_ids),
        Task.is_deleted == False
    ).all()
    
    if len(tasks) != len(task_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Some tasks not found"
        )
    
    # Update assignments
    updated_count = 0
    for task in tasks:
        if task.assigned_user_id != user_id:
            task.assigned_user_id = user_id
            updated_count += 1
    
    db.commit()
    
    return {
        "message": f"Bulk assigned {updated_count} tasks to user {user_id}",
        "updated_tasks": updated_count,
        "total_tasks": len(tasks)
    }


@router.get("/user-activity/{user_id}")
async def get_user_activity(
    user_id: int,
    days: int = Query(30, ge=1, le=365),
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin only: Get user activity summary"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Date range
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Activity statistics
    activities = db.query(AuditLog).filter(
        AuditLog.user_id == user_id,
        AuditLog.timestamp >= start_date
    ).all()
    
    # Tasks created
    tasks_created = db.query(Task).filter(
        Task.created_by == user_id,
        Task.created_at >= start_date
    ).count()
    
    # Tasks completed
    tasks_completed = db.query(AuditLog).filter(
        AuditLog.user_id == user_id,
        AuditLog.action == "TASK_UPDATED",
        AuditLog.timestamp >= start_date,
        cast(AuditLog.new_values, JSONB).contains({"status": "done"})
    ).count()
    
    # Activity by action
    activity_breakdown = {}
    for activity in activities:
        action = activity.action
        activity_breakdown[action] = activity_breakdown.get(action, 0) + 1
    
    return {
        "user_id": user_id,
        "username": user.username,
        "period_days": days,
        "total_activities": len(activities),
        "tasks_created": tasks_created,
        "tasks_completed": tasks_completed,
        "activity_breakdown": activity_breakdown
    }