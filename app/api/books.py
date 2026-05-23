from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.schemas.book import BookCreate, BookUpdate, BookResponse
from app.services import book_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/books", tags=["books"])


@router.get("", response_model=list[BookResponse])
async def get_books(
    author_id: int | None = Query(None, description="过滤特定作者的图书"),
    db: AsyncSession = Depends(get_db),
):
    """B2: 公开获取图书列表，可按 author_id 过滤"""
    return await book_service.get_books(db, author_id)


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(book_id: int, db: AsyncSession = Depends(get_db)):
    """B3: 公开获取单本图书"""
    return await book_service.get_book_by_id(db, book_id)


@router.post("", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
async def create_book(
    book_data: BookCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """B1: 创建图书，校验作者存在，自动记录创建者"""
    book = await book_service.create_book(db, book_data, current_user.id)
    background_tasks.add_task(
        log_action,
        user_id=current_user.id,
        action="CREATE",
        resource_type="Book",
        resource_id=book.id,
        description=f"Created book '{book.title}'",
    )
    return book


@router.put("/{book_id}", response_model=BookResponse)
async def update_book(
    book_id: int,
    book_data: BookUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """B4: 更新图书，仅创建者或管理员可操作"""
    book = await book_service.update_book(
        db, book_id, book_data, current_user.id, current_user.role
    )
    background_tasks.add_task(
        log_action,
        user_id=current_user.id,
        action="UPDATE",
        resource_type="Book",
        resource_id=book.id,
        description=f"Updated book '{book.title}'",
    )
    return book


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(
    book_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """B5: 删除图书，仅创建者或管理员可操作"""
    book = await book_service.get_book_by_id(db, book_id)
    await book_service.delete_book(
        db, book_id, current_user.id, current_user.role
    )
    background_tasks.add_task(
        log_action,
        user_id=current_user.id,
        action="DELETE",
        resource_type="Book",
        resource_id=book_id,
        description=f"Deleted book '{book.title}'",
    )
    return None