from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import get_admin_user
from app.models.user import User
from app.schemas.user import UserResponse, UserRoleUpdate, UserStatusUpdate
from app.schemas.audit_log import AuditLogResponse
from app.services import user_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserResponse])
async def get_users(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """M1: 管理员获取所有用户列表"""
    return await user_service.get_all_users(db)


@router.patch("/users/{user_id}/status", response_model=UserResponse)
async def patch_user_status(
    user_id: int,
    status_data: UserStatusUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """M2: 管理员修改用户启用/禁用状态"""
    updated_user = await user_service.change_user_status(
        db, user_id, status_data.is_active, admin_user
    )
    background_tasks.add_task(
        log_action,
        user_id=admin_user.id,
        action="UPDATE",
        resource_type="User",
        resource_id=updated_user.id,
        description=f"Set active={status_data.is_active} for user {updated_user.email}",
    )
    return updated_user


@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def patch_user_role(
    user_id: int,
    role_data: UserRoleUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """M3: 管理员修改用户角色"""
    updated_user = await user_service.change_user_role(
        db, user_id, role_data.role, admin_user
    )
    background_tasks.add_task(
        log_action,
        user_id=admin_user.id,
        action="UPDATE",
        resource_type="User",
        resource_id=updated_user.id,
        description=f"Changed role to {role_data.role}",
    )
    return updated_user


@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def get_audit_logs(
    user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """L3: 管理员查看审计日志，支持多条件过滤"""
    return await user_service.get_audit_logs(
        db, user_id=user_id, action=action,
        start_time=start_time, end_time=end_time
    )