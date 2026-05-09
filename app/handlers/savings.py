from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from app.texts import BTN_SAVINGS

from app.database import SessionLocal
from app.formatters import format_savings_history, format_savings_settings_updated, format_savings_summary
from app.keyboards import cancel_action_keyboard, main_menu_keyboard, savings_disabled_keyboard, savings_enabled_keyboard
from app.services import savings as savings_service
from app.services.users import get_or_create_user_from_telegram
from app.states import SavingsStates

router = Router()


async def _send_savings_screen(message: Message, user) -> None:
    async with SessionLocal() as session:
        summary = await savings_service.get_savings_summary(session, user.id)
    keyboard = savings_enabled_keyboard() if summary["settings"].is_enabled else savings_disabled_keyboard()
    await message.answer(format_savings_summary(summary), reply_markup=keyboard)


@router.message(Command("savings"))
@router.message(F.text == BTN_SAVINGS)
async def savings_handler(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
    await _send_savings_screen(message, user)


@router.callback_query(F.data == "savings:enable_10")
async def enable_savings_10(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
        settings = await savings_service.enable_savings(session, user.id, 10)
    await callback.message.answer(format_savings_settings_updated(settings), reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "savings:custom_percent")
async def ask_savings_percent(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SavingsStates.percent)
    await callback.message.answer("Какой процент от дохода откладывать в копилку? Например: 10", reply_markup=cancel_action_keyboard())
    await callback.answer()


@router.message(SavingsStates.percent)
async def save_savings_percent(message: Message, state: FSMContext) -> None:
    try:
        percent = int(message.text.strip())
        if percent < 1 or percent > 50:
            raise ValueError
    except ValueError:
        await message.answer("Напиши число от 1 до 50.", reply_markup=cancel_action_keyboard())
        return
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        settings = await savings_service.update_savings_percent(session, user.id, percent)
    await state.clear()
    await message.answer(format_savings_settings_updated(settings), reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "savings:disable")
async def disable_savings(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
        await savings_service.disable_savings(session, user.id)
    await callback.message.answer("Копилка выключена.", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "savings:history")
async def savings_history(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
        items = await savings_service.get_savings_history(session, user.id, 10)
    await callback.message.answer(format_savings_history(items), reply_markup=main_menu_keyboard())
    await callback.answer()

