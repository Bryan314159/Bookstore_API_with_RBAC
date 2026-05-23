from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.schemas.author import AuthorCreate, AuthorUpdate, AuthorResponse
from app.services import author_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/authors", tags=["authors"])


@router.get("", response_model=list[AuthorResponse])
async def get_authors(db: AsyncSession = Depends(get_db)):
    """A2: 公开获取作者列表"""
    return await author_service.get_authors(db)


@router.get("/{author_id}", response_model=AuthorResponse)
async def get_author(author_id: int, db: AsyncSession = Depends(get_db)):
    """A3: 公开获取单个作者"""
    return await author_service.get_author_by_id(db, author_id)


@router.post("", response_model=AuthorResponse, status_code=status.HTTP_201_CREATED)
async def create_author(
    author_data: AuthorCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """A1: 创建作者，自动记录创建者"""
    author = await author_service.create_author(db, author_data, current_user.id)
    background_tasks.add_task(
        log_action,
        user_id=current_user.id,
        action="CREATE",
        resource_type="Author",
        resource_id=author.id,
        description=f"Created author {author.name}",
    )
    return author


@router.put("/{author_id}", response_model=AuthorResponse)
async def update_author(
    author_id: int,
    author_data: AuthorUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """A4: 更新作者，仅创建者或管理员可操作"""
    author = await author_service.update_author(
        db, author_id, author_data, current_user.id, current_user.role
    )
    background_tasks.add_task(
        log_action,
        user_id=current_user.id,
        action="UPDATE",
        resource_type="Author",
        resource_id=author.id,
        description=f"Updated author {author.name}",
    )
    return author


@router.delete("/{author_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_author(
    author_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """A5: 删除作者，仅创建者或管理员可操作；若有关联图书则拒绝"""
    # 需要先获取作者名字（用于日志），服务层已检查权限和图书
    author = await author_service.get_author_by_id(db, author_id)
    await author_service.delete_author(db, author_id, current_user.id, current_user.role)
    background_tasks.add_task(
        log_action,
        user_id=current_user.id,
        action="DELETE",
        resource_type="Author",
        resource_id=author_id,
        description=f"Deleted author {author.name}",
    )
    return None