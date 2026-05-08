from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NotificationLog


async def create_log(session: AsyncSession, user_id: int, obligation_id: int, notification_type: str, sent_date: date) -> NotificationLog:
    log = NotificationLog(user_id=user_id, obligation_id=obligation_id, notification_type=notification_type, sent_date=sent_date)
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


async def exists_log(session: AsyncSession, user_id: int, obligation_id: int, notification_type: str, sent_date: date) -> bool:
    existing = await session.scalar(
        select(NotificationLog.id).where(
            NotificationLog.user_id == user_id,
            NotificationLog.obligation_id == obligation_id,
            NotificationLog.notification_type == notification_type,
            NotificationLog.sent_date == sent_date,
        )
    )
    return existing is not None
