import sys
from pathlib import Path
from unittest import mock

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# 将项目根目录加入 sys.path，确保导入 app 模块
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.config import settings
from app.database import get_db
from app.main import app
from app.models import Base


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """每个测试函数使用独立的内存数据库引擎"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine):
    """提供异步数据库会话（同一个测试内复用）"""
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def async_client(test_engine):
    """
    提供异步 HTTP 客户端，并完成两项覆盖：
    1. 替换路由层的数据库依赖（get_db）
    2. 替换审计服务中的会话工厂，使审计日志写入测试数据库
    """
    # 创建基于测试引擎的会话工厂
    test_session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # 覆盖路由依赖注入
    async def override_get_db():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # 使用 mock.patch 替换审计服务模块中的 async_session_factory
    from app.services import audit_service

    with mock.patch.object(
        audit_service, "async_session_factory", test_session_factory
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

    # 清理路由依赖覆盖
    app.dependency_overrides.clear()