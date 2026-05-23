from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AuthorCreate(BaseModel):
    """创建作者"""
    name: str
    bio: Optional[str] = None


class AuthorUpdate(BaseModel):
    """更新作者"""
    name: str
    bio: Optional[str] = None


class AuthorResponse(BaseModel):
    """作者信息响应"""
    id: int
    name: str
    bio: Optional[str] = None
    created_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)