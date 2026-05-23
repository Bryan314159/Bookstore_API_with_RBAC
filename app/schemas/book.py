from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator, ConfigDict


class BookCreate(BaseModel):
    """创建图书"""
    title: str
    author_id: int
    published_year: Optional[int] = None

    @field_validator("published_year")
    @classmethod
    def validate_year(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("published_year must be a positive integer")
        return v


class BookUpdate(BaseModel):
    """更新图书（author_id 不可更改）"""
    title: str
    published_year: Optional[int] = None

    @field_validator("published_year")
    @classmethod
    def validate_year(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("published_year must be a positive integer")
        return v


class BookResponse(BaseModel):
    """图书信息响应"""
    id: int
    title: str
    author_id: int
    published_year: Optional[int] = None
    created_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)