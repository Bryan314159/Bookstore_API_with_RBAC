import asyncio
import traceback
from app.database import async_session_factory
from app.models.audit_log import AuditLog

async def log_action(
    user_id: int,
    action: str,
    resource_type: str,
    resource_id: int,
    description: str = "",
) -> None:
    """
    异步写入审计日志，使用独立数据库会话，不阻塞主请求。
    可以安全地在后台任务中调用（例如 asyncio.create_task(log_action(...))）。
    """
    async with async_session_factory() as session:
        try:
            log_entry = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                description=description,
            )
            session.add(log_entry)
            await session.commit()
        except Exception:
            # 审计日志写入失败不应影响主流程，记录异常并回滚
            await session.rollback()
            # 在实际生产环境中，这里可以替换为结构化日志
            print("Failed to write audit log:")
            traceback.print_exc()