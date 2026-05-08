from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from app.texts import BTN_PROGRESS

from app.database import SessionLocal
from app.formatters import format_progress
from app.keyboards import main_menu_keyboard
from app.services import progress as progress_service
from app.services.users import get_or_create_user_from_telegram

router = Router()


@router.message(Command("progress"))
@router.message(F.text == BTN_PROGRESS)
@router.message(F.text == BTN_PROGRESS)
async def progress_handler(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        data = await progress_service.get_debt_progress(session, user.id)
    await message.answer(format_progress(data), reply_markup=main_menu_keyboard())
