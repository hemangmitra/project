from pydantic import BaseModel
from typing import Optional, Any, Dict
from datetime import datetime


class AuditLogResponse(BaseModel):
    id: int
    user_id: int
    task_id: Optional[int]
    action: str
    old_values: Optional[Dict[str, Any]]
    new_values: Optional[Dict[str, Any]]
    timestamp: datetime
    
    class Config:
        from_attributes = True


class AuditLogList(BaseModel):
    logs: list[AuditLogResponse]
    total: int
    page: int
    size: int


class SystemStats(BaseModel):
    total_users: int
    active_users: int
    total_tasks: int
    tasks_by_status: Dict[str, int]
    tasks_by_priority: Dict[str, int]
    recent_activities: int