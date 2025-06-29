from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import Optional, List
from datetime import datetime
from app.core.database import get_db
from app.middleware.auth import get_current_active_user, get_admin_user
from app.models.user import User, UserRole
from app.models.task import Task, TaskStatus, TaskPriority
from app.schemas.task import (
    TaskCreate, TaskUpdate, TaskResponse, TaskList, 
    TaskAssignment, TaskFilters
)
from app.utils.audit import audit_service

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new task"""
    # Validate assigned user if provided
    if task_data.assigned_user_id:
        assigned_user = db.query(User).filter(User.id == task_data.assigned_user_id).first()
        if not assigned_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assigned user not found"
            )
    
    task = Task(
        title=task_data.title,
        description=task_data.description,
        status=task_data.status,
        priority=task_data.priority,
        due_date=task_data.due_date,
        assigned_user_id=task_data.assigned_user_id,
        created_by=current_user.id
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # Log task creation
    await audit_service.log_action(
        db=db,
        user_id=current_user.id,
        task_id=task.id,
        action="TASK_CREATED",
        new_values={
            "title": task.title,
            "status": task.status,
            "priority": task.priority,
            "assigned_user_id": task.assigned_user_id
        }
    )
    
    return task


@router.get("/", response_model=TaskList)
async def list_tasks(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    status: Optional[TaskStatus] = Query(None),
    priority: Optional[TaskPriority] = Query(None),
    assigned_user_id: Optional[int] = Query(None),
    created_by: Optional[int] = Query(None),
    due_date_from: Optional[datetime] = Query(None),
    due_date_to: Optional[datetime] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List tasks with advanced filtering and pagination"""
    offset = (page - 1) * size
    
    # Base query - users can see their own tasks or tasks assigned to them
    query = db.query(Task).filter(Task.is_deleted == False)
    
    # Non-admin users can only see their tasks
    if current_user.role != UserRole.ADMIN:
        query = query.filter(
            or_(
                Task.created_by == current_user.id,
                Task.assigned_user_id == current_user.id
            )
        )
    
    # Apply filters
    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)
    if assigned_user_id:
        query = query.filter(Task.assigned_user_id == assigned_user_id)
    if created_by:
        query = query.filter(Task.created_by == created_by)
    if due_date_from:
        query = query.filter(Task.due_date >= due_date_from)
    if due_date_to:
        query = query.filter(Task.due_date <= due_date_to)
    if search:
        query = query.filter(
            or_(
                Task.title.ilike(f"%{search}%"),
                Task.description.ilike(f"%{search}%")
            )
        )
    
    # Order by updated_at desc
    query = query.order_by(Task.updated_at.desc())
    
    total = query.count()
    tasks = query.offset(offset).limit(size).all()
    
    return {
        "tasks": tasks,
        "total": total,
        "page": page,
        "size": size
    }


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get single task details"""
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.is_deleted == False
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Check permissions
    if (current_user.role != UserRole.ADMIN and 
        task.created_by != current_user.id and 
        task.assigned_user_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view this task"
        )
    
    return task


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update task (owner or admin)"""
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.is_deleted == False
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Check permissions
    if (current_user.role != UserRole.ADMIN and 
        task.created_by != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update this task"
        )
    
    # Store old values for audit
    old_values = {
        "title": task.title,
        "description": task.description,
        "status": task.status.value if task.status else None,  # Convert enum to string
        "priority": task.priority.value if task.priority else None,  # Convert enum to string
        "due_date": task.due_date.isoformat() if task.due_date else None,  # Convert datetime to string
        "assigned_user_id": task.assigned_user_id
    }
    
    # Update fields
    if task_update.title is not None:
        task.title = task_update.title
    if task_update.description is not None:
        task.description = task_update.description
    if task_update.status is not None:
        task.status = task_update.status
    if task_update.priority is not None:
        task.priority = task_update.priority
    if task_update.due_date is not None:
        task.due_date = task_update.due_date
    if task_update.assigned_user_id is not None:
        # Validate assigned user
        if task_update.assigned_user_id:
            assigned_user = db.query(User).filter(User.id == task_update.assigned_user_id).first()
            if not assigned_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Assigned user not found"
                )
        task.assigned_user_id = task_update.assigned_user_id
    
    db.commit()
    db.refresh(task)
    
    # Log task update
    new_values = {
        "title": task.title,
        "description": task.description,
        "status": task.status.value if task.status else None,  # Convert enum to stringAdd commentMore actions
        "priority": task.priority.value if task.priority else None,  # Convert enum to string
        "due_date": task.due_date.isoformat() if task.due_date else None,  # Convert datetime to string
        "assigned_user_id": task.assigned_user_id
    }
    
    await audit_service.log_action(
        db=db,
        user_id=current_user.id,
        task_id=task.id,
        action="TASK_UPDATED",
        old_values=old_values,
        new_values=new_values
    )
    
    return task


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Soft delete task with confirmation"""
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.is_deleted == False
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Check permissions
    if (current_user.role != UserRole.ADMIN and 
        task.created_by != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete this task"
        )
    
    # Soft delete
    task.is_deleted = True
    db.commit()
    
    # Log task deletion
    await audit_service.log_action(
        db=db,
        user_id=current_user.id,
        task_id=task.id,
        action="TASK_DELETED",
        old_values={"is_deleted": False},
        new_values={"is_deleted": True}
    )
    
    return {"message": "Task deleted successfully"}


@router.post("/{task_id}/assign")
async def assign_task(
    task_id: int,
    assignment: TaskAssignment,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin only: Assign task to user"""
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.is_deleted == False
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Validate user
    user = db.query(User).filter(User.id == assignment.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )
    
    old_assigned_user_id = task.assigned_user_id
    task.assigned_user_id = assignment.user_id
    db.commit()
    
    # Log assignment
    await audit_service.log_action(
        db=db,
        user_id=admin_user.id,
        task_id=task.id,
        action="TASK_ASSIGNED",
        old_values={"assigned_user_id": old_assigned_user_id},
        new_values={"assigned_user_id": assignment.user_id}
    )
    
    return {"message": f"Task assigned to user {assignment.user_id}"}


@router.get("/assigned/{user_id}")
async def get_tasks_assigned_to_user(
    user_id: int,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin only: Get tasks assigned to user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    tasks = db.query(Task).filter(
        Task.assigned_user_id == user_id,
        Task.is_deleted == False
    ).all()
    
    return {
        "user_id": user_id,
        "username": user.username,
        "tasks": tasks
    }