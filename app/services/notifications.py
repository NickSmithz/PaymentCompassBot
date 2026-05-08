from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.formatters import format_reminder
from app.repositories import notifications as notifications_repo
from app.repositories import obligations as obligations_repo
from app.repositories import reserves as reserves_repo


async def was_notification_sent(session: AsyncSession, user_id: int, obligation_id: int, notification_type: str, sent_date: date) -> bool:
    return await notifications_repo.exists_log(session, user_id, obligation_id, notification_type, sent_date)


async def log_notification(session: AsyncSession, user_id: int, obligation_id: int, notification_type: str, sent_date: date):
    return await notifications_repo.create_log(session, user_id, obligation_id, notification_type, sent_date)


async def send_payment_reminder(bot: Any, user, obligation, reminder_type: str, data: dict) -> None:
    await bot.send_message(user.telegram_id, format_reminder(data))


async def check_payment_reminders(session: AsyncSession, bot: Any, today: date) -> None:
    pairs = await obligations_repo.list_due_for_reminders(session, today)
    for obligation, user in pairs:
        reserved = await reserves_repo.sum_reserved_for_obligation(session, user.id, obligation.id)
        remaining = max(0, obligation.monthly_payment_amount - reserved)
        days_left = (obligation.next_payment_date - today).days
        if days_left not in {7, 3, 1, 0} and days_left >= 0:
            continue
        notification_type = "overdue" if days_left < 0 else f"due_{days_left}"
        if await was_notification_sent(session, user.id, obligation.id, notification_type, today):
            continue
        data = {
            "title": obligation.title,
            "amount": obligation.monthly_payment_amount,
            "reserved_amount": reserved,
            "remaining_amount": remaining,
            "date": obligation.next_payment_date,
            "days_left": days_left,
        }
        await send_payment_reminder(bot, user, obligation, notification_type, data)
        await log_notification(session, user.id, obligation.id, notification_type, today)
