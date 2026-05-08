from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import get_settings
from app.database import SessionLocal
from app.formatters import format_financial_status
from app.keyboards import main_menu_keyboard
from app.services import financial_status as financial_status_service
from app.services.users import get_or_create_user_from_telegram

router = Router()


@router.message(Command("status"))
@router.message(F.text == "📍 Финансовый статус")
async def financial_status_handler(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        today = datetime.now(ZoneInfo(user.timezone or get_settings().timezone)).date()
        summary = await financial_status_service.get_financial_status(session, user.id, today)
    await message.answer(format_financial_status(summary), reply_markup=main_menu_keyboard())
