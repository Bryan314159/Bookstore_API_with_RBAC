from fastapi import Depends, HTTPException, status
from app.models.user import User
from app.core.deps import get_current_active_user, get_admin_user


def require_ownership(resource_owner_id: int):
    """
    返回一个依赖函数，用于检查当前用户是否为资源所有者或管理员。
    如果不是，则抛出 403 Forbidden。
    """
    async def ownership_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.role != "admin" and current_user.id != resource_owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return ownership_checker


async def require_admin(
    admin_user: User = Depends(get_admin_user),
) -> User:
    """
    要求当前用户必须是管理员，否则自动返回 403。
    可直接在路由中使用 `Depends(require_admin)`。
    """
    return admin_user