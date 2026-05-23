from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, func
from typing import Optional

class Base(DeclarativeBase):
    """
    所有 ORM 模型的抽象基类。
    提供通用的 id, created_at, updated_at 字段。
    """
    __abstract__ = True  # 声明为抽象基类，不会单独创建表

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # 数据库端默认当前时间
        nullable=False,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),  # 更新时自动刷新
        nullable=True,
    )