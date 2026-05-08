from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from app.texts import BTN_SAFE_TO_SPEND

from app.database import SessionLocal
from app.formatters import format_allocation_result
from app.keyboards import main_menu_keyboard
from app.services import allocation as allocation_service
from app.services.users import get_or_create_user_from_telegram
from app.utils import parse_date

router = Router()


@router.message(Command("spend"))
@router.message(F.text == BTN_SAFE_TO_SPEND)
@router.message(F.text == BTN_SAFE_TO_SPEND)
async def spend_handler(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        result = await allocation_service.recalculate_last_income(session, user.id, parse_date("сегодня", user.timezone))
    if result is None:
        await message.answer("Пока нет полученных доходов. Добавь доход, который уже пришёл, и я рассчитаю безопасную сумму.", reply_markup=main_menu_keyboard())
        return
    await message.answer(format_allocation_result(result), reply_markup=main_menu_keyboard())
