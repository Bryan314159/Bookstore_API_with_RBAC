import pytest
from sqlalchemy import inspect, text
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from app.models.user import User

# 导入所有模型（确保它们注册到 Base.metadata）
from app.models import Base, User, Author, Book, AuditLog
# 使用 aiossqlite 内存数据库，共享同一个引擎确保表持久存在
DATABASE_URL = "sqlite+aiosqlite://"


@pytest.mark.asyncio
async def test_tables_exist(test_engine):
    """验证所有预期的表都已被创建"""
    async with test_engine.connect() as conn:
        # 使用同步方式通过 run_sync 获取表名
        def get_table_names(connection):
            inspector = inspect(connection)
            return inspector.get_table_names()
        
        tables = await conn.run_sync(get_table_names)
        
    expected_tables = {"users", "authors", "books", "audit_logs"}
    assert expected_tables.issubset(set(tables)), f"Missing tables: {expected_tables - set(tables)}"

@pytest.mark.asyncio
async def test_users_table_columns(test_engine):
    """检查 users 表是否包含所有必要字段"""
    async with test_engine.connect() as conn:
        def get_columns(connection):
            inspector = inspect(connection)
            return {col["name"] for col in inspector.get_columns("users")}
        
        columns = await conn.run_sync(get_columns)
    
    required = {"id", "email", "hashed_password", "role", "is_active",
                "refresh_token_version", "reset_token_jti", "reset_token_expires",
                "created_at", "updated_at"}
    assert required.issubset(columns), f"Missing columns in users: {required - columns}"

@pytest.mark.asyncio
async def test_authors_table_columns(test_engine):
    """检查 authors 表字段"""
    async with test_engine.connect() as conn:
        def get_columns(connection):
            inspector = inspect(connection)
            return {col["name"] for col in inspector.get_columns("authors")}
        
        columns = await conn.run_sync(get_columns)
    
    required = {"id", "name", "bio", "created_by", "created_at", "updated_at"}
    assert required.issubset(columns), f"Missing columns in authors: {required - columns}"

@pytest.mark.asyncio
async def test_books_table_columns(test_engine):
    """检查 books 表字段"""
    async with test_engine.connect() as conn:
        def get_columns(connection):
            inspector = inspect(connection)
            return {col["name"] for col in inspector.get_columns("books")}
        
        columns = await conn.run_sync(get_columns)
    
    required = {"id", "title", "author_id", "published_year", "created_by",
                "created_at", "updated_at"}
    assert required.issubset(columns), f"Missing columns in books: {required - columns}"

@pytest.mark.asyncio
async def test_audit_logs_table_columns(test_engine):
    """检查 audit_logs 表字段"""
    async with test_engine.connect() as conn:
        def get_columns(connection):
            inspector = inspect(connection)
            return {col["name"] for col in inspector.get_columns("audit_logs")}
        
        columns = await conn.run_sync(get_columns)
    
    required = {"id", "user_id", "action", "resource_type", "resource_id",
                "description", "created_at"}
    assert required.issubset(columns), f"Missing columns in audit_logs: {required - columns}"

@pytest.mark.asyncio
async def test_users_email_unique_constraint(db_session):
    """验证 email 字段确实有唯一约束（通过重复插入触发 IntegrityError）"""
    user1 = User(email="unique@test.com", hashed_password="hash1")
    db_session.add(user1)
    await db_session.commit()

    user2 = User(email="unique@test.com", hashed_password="hash2")
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    # 回滚以保持会话干净
    await db_session.rollback()

@pytest.mark.asyncio
async def test_book_author_relationship(test_engine, db_session):
    """快速验证外键关系：创建一个作者和一本书，确认关联有效"""
    # 插入一个用户（因为 author.created_by 需要）
    from app.models.user import User
    from app.models.author import Author
    from app.models.book import Book
    
    user = User(email="test@test.com", hashed_password="hash")
    db_session.add(user)
    await db_session.flush()
    
    author = Author(name="Test Author", bio="A test", created_by=user.id)
    db_session.add(author)
    await db_session.flush()
    
    book = Book(title="Test Book", author_id=author.id, published_year=2023, created_by=user.id)
    db_session.add(book)
    await db_session.commit()
    
    # 通过关系加载
    await db_session.refresh(author, attribute_names=["books"])
    assert len(author.books) == 1
    assert author.books[0].title == "Test Book"
    # 反向关系
    await db_session.refresh(book, attribute_names=["author"])
    assert book.author.name == "Test Author"