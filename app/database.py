from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import settings

# 创建异步引擎
# echo=settings.DEBUG 可以在开发时打印 SQL，生产环境关闭
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,            # 使用 SQLAlchemy 2.0 风格
)

# 创建异步会话工厂
# expire_on_commit=False 防止提交后对象属性过期，在异步访问中更安全
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db() -> AsyncSession:
    """
    异步数据库会话依赖生成器。
    在请求上下文中创建会话，并在请求结束后自动关闭。
    """
    async with async_session_factory() as session:
        try:
            yield session
            # 正常结束后提交事务（若路由中未主动提交，可在此统一提交）
            # 注意：一般建议在服务层显式提交，这里仅作为安全网
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    """在应用启动时创建所有表（简易方案，生产环境建议使用 Alembic）"""
    async with engine.begin() as conn:
        from app.models import Base  # 避免循环导入，延迟导入
        await conn.run_sync(Base.metadata.create_all)