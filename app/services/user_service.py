from typing import Optional
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.audit_log import AuditLog


async def get_all_users(db: AsyncSession) -> list[User]:
    """返回所有用户列表（不含密码）"""
    result = await db.execute(select(User).order_by(User.id))
    return result.scalars().all()


async def change_user_status(
    db: AsyncSession,
    target_user_id: int,
    is_active: bool,
    current_user: User,
) -> User:
    """修改用户启用/禁用状态，admin 专用；不能对自己操作"""
    if target_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot disable yourself",
        )

    result = await db.execute(select(User).where(User.id == target_user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = is_active
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def change_user_role(
    db: AsyncSession,
    target_user_id: int,
    new_role: str,
    current_user: User,
) -> User:
    """修改用户角色，admin 专用；不能修改自己的角色"""
    if target_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot change your own role",
        )

    result = await db.execute(select(User).where(User.id == target_user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = new_role
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_audit_logs(
    db: AsyncSession,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> list[AuditLog]:
    """查询审计日志，支持按用户、操作类型、时间范围过滤"""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())

    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if start_time is not None:
        stmt = stmt.where(AuditLog.created_at >= start_time)
    if end_time is not None:
        stmt = stmt.where(AuditLog.created_at <= end_time)

    result = await db.execute(stmt)
    return result.scalars().all()