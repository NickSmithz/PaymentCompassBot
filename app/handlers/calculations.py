from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from app.texts import BTN_SAFE_TO_SPEND

from app.config import get_settings
from app.database import SessionLocal
from app.formatters import format_spending_summary
from app.keyboards import main_menu_keyboard
from app.services import income_recurrence
from app.services import spending as spending_service
from app.services.users import get_or_create_user_from_telegram

router = Router()


@router.message(Command("spend"))
@router.message(F.text == BTN_SAFE_TO_SPEND)
async def spend_handler(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        now = datetime.now(ZoneInfo(user.timezone or get_settings().timezone))
        await income_recurrence.ensure_income_instances(session, user.id, now.date())
        summary = await spending_service.get_spending_summary(session, user.id, now.date(), now)
    await message.answer(format_spending_summary(summary), reply_markup=main_menu_keyboard())
