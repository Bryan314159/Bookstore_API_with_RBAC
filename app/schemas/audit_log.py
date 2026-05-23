from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    """审计日志响应"""
    id: int
    user_id: Optional[int] = None
    action: str
    resource_type: str
    resource_id: int
    description: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogFilter(BaseModel):
    """审计日志查询过滤参数"""
    user_id: Optional[int] = None
    action: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None