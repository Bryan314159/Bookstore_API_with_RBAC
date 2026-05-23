from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.author import Author
from app.models.book import Book
from app.schemas.book import BookCreate, BookUpdate


async def get_books(
    db: AsyncSession, author_id: Optional[int] = None
) -> list[Book]:
    """获取图书列表，可按作者过滤"""
    stmt = select(Book)
    if author_id is not None:
        stmt = stmt.where(Book.author_id == author_id)
    result = await db.execute(stmt.order_by(Book.id))
    return result.scalars().all()


async def get_book_by_id(db: AsyncSession, book_id: int) -> Book:
    """根据 ID 获取图书，不存在则抛 404"""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


async def create_book(db: AsyncSession, data: BookCreate, user_id: int) -> Book:
    """创建图书，验证作者存在，记录创建者"""
    author_result = await db.execute(select(Author).where(Author.id == data.author_id))
    if not author_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Author not found")

    book = Book(
        title=data.title,
        author_id=data.author_id,
        published_year=data.published_year,
        created_by=user_id,
    )
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book


async def update_book(
    db: AsyncSession,
    book_id: int,
    data: BookUpdate,
    current_user_id: int,
    current_user_role: str,
) -> Book:
    """更新图书，检查所有权/管理员"""
    book = await get_book_by_id(db, book_id)

    if current_user_role != "admin" and current_user_id != book.created_by:
        raise HTTPException(
            status_code=403, detail="You do not have permission to perform this action"
        )

    book.title = data.title
    book.published_year = data.published_year
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book


async def delete_book(
    db: AsyncSession,
    book_id: int,
    current_user_id: int,
    current_user_role: str,
) -> None:
    """删除图书，检查所有权/管理员"""
    book = await get_book_by_id(db, book_id)

    if current_user_role != "admin" and current_user_id != book.created_by:
        raise HTTPException(
            status_code=403, detail="You do not have permission to perform this action"
        )

    await db.delete(book)
    await db.commit()