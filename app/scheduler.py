from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.database import SessionLocal
from app.services.notifications import check_payment_reminders


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    if settings.reminders_enabled:
        scheduler.add_job(_run_reminders, "cron", hour=9, minute=0, args=[bot], id="payment_reminders", replace_existing=True)
    return scheduler


async def _run_reminders(bot: Bot) -> None:
    settings = get_settings()
    today = datetime.now(ZoneInfo(settings.timezone)).date()
    async with SessionLocal() as session:
        await check_payment_reminders(session, bot, today)
