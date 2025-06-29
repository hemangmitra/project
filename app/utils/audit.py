from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from app.models.audit_log import AuditLog


class AuditService:
    
    async def log_action(
        self,
        db: Session,
        user_id: int,
        action: str,
        task_id: Optional[int] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None
    ):
        audit_log = AuditLog(
            user_id=user_id,
            task_id=task_id,
            action=action,
            old_values=old_values,
            new_values=new_values
        )
        
        db.add(audit_log)
        db.commit()
        
        return audit_log
    
    def get_user_activities(
        self,
        db: Session,
        user_id: int,
        limit: int = 50
    ):
        return db.query(AuditLog).filter(
            AuditLog.user_id == user_id
        ).order_by(
            AuditLog.timestamp.desc()
        ).limit(limit).all()
    
    def get_task_history(
        self,
        db: Session,
        task_id: int
    ):
        return db.query(AuditLog).filter(
            AuditLog.task_id == task_id
        ).order_by(
            AuditLog.timestamp.asc()
        ).all()


# Global audit service instance
audit_service = AuditService()