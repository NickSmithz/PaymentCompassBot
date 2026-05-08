from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from app.texts import BTN_SETTINGS

from app.database import SessionLocal
from app.formatters import format_help
from app.keyboards import main_menu_keyboard, settings_keyboard
from app.services import users as user_service
from app.services.users import get_or_create_user_from_telegram

router = Router()


@router.message(F.text == BTN_SETTINGS)
@router.message(F.text == BTN_SETTINGS)
async def settings_handler(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
    status = "включены" if user.reminders_enabled else "выключены"
    await message.answer(f"⚙️ Настройки\n\nУведомления: {status}", reply_markup=settings_keyboard(user.reminders_enabled))


@router.callback_query(F.data == "settings:toggle_reminders")
async def toggle_reminders(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
        user = await user_service.update_user_settings(session, user.id, reminders_enabled=not user.reminders_enabled)
    status = "включены" if user.reminders_enabled else "выключены"
    await callback.message.answer(f"Уведомления {status}.", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "settings:help")
async def settings_help(callback: CallbackQuery) -> None:
    await callback.message.answer(format_help(), reply_markup=main_menu_keyboard())
    await callback.answer()
