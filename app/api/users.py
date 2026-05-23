from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import get_current_active_user
from app.core.security import verify_password, hash_password
from app.schemas.user import PasswordChange, UserResponse
from app.models.user import User
from app.services.audit_service import log_action

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_active_user)):
    """U5: 返回当前登录用户的信息"""
    return current_user


@router.post("/me/change-password")
async def change_password(
    pw_data: PasswordChange,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """U6: 修改密码，需提供正确的旧密码"""
    if not verify_password(pw_data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Old password is incorrect",
        )

    new_hashed = hash_password(pw_data.new_password)
    current_user.hashed_password = new_hashed
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)

    background_tasks.add_task(
        log_action,
        user_id=current_user.id,
        action="UPDATE",
        resource_type="User",
        resource_id=current_user.id,
        description=f"User {current_user.email} changed password",
    )

    return {"message": "Password updated successfully."}