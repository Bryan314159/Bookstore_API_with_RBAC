from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.author import Author
from app.schemas.author import AuthorCreate, AuthorUpdate


async def get_authors(db: AsyncSession) -> list[Author]:
    """获取所有作者列表"""
    result = await db.execute(select(Author).order_by(Author.id))
    return result.scalars().all()


async def get_author_by_id(db: AsyncSession, author_id: int) -> Author:
    """根据 ID 获取作者，不存在则抛 404"""
    result = await db.execute(select(Author).where(Author.id == author_id))
    author = result.scalar_one_or_none()
    if author is None:
        raise HTTPException(status_code=404, detail="Author not found")
    return author


async def create_author(db: AsyncSession, data: AuthorCreate, user_id: int) -> Author:
    """创建作者，记录创建者，名称重复时抛 409"""
    author = Author(name=data.name, bio=data.bio, created_by=user_id)
    db.add(author)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Author name already exists")
    await db.refresh(author)
    return author


async def update_author(
    db: AsyncSession,
    author_id: int,
    data: AuthorUpdate,
    current_user_id: int,
    current_user_role: str,
) -> Author:
    """更新作者，检查所有权/管理员，名称唯一性（排除自身）"""
    author = await get_author_by_id(db, author_id)

    if current_user_role != "admin" and current_user_id != author.created_by:
        raise HTTPException(
            status_code=403, detail="You do not have permission to perform this action"
        )

    existing = await db.execute(
        select(Author).where(Author.name == data.name, Author.id != author_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Author name already exists")

    author.name = data.name
    author.bio = data.bio
    db.add(author)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Author name already exists")
    await db.refresh(author)
    return author


async def delete_author(
    db: AsyncSession,
    author_id: int,
    current_user_id: int,
    current_user_role: str,
) -> None:
    """删除作者，检查所有权/管理员，存在图书时抛 409"""
    author = await get_author_by_id(db, author_id)

    if current_user_role != "admin" and current_user_id != author.created_by:
        raise HTTPException(
            status_code=403, detail="You do not have permission to perform this action"
        )

    if author.books:
        raise HTTPException(
            status_code=409, detail="Cannot delete author with associated books"
        )

    await db.delete(author)
    await db.commit()