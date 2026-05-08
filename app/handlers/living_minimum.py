from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.database import SessionLocal
from app.formatters import format_living_minimum_summary, format_living_minimum_updated
from app.keyboards import living_minimum_disabled_keyboard, living_minimum_enabled_keyboard, main_menu_keyboard
from app.services import living_minimum as living_service
from app.services.users import get_or_create_user_from_telegram
from app.states import LivingMinimumStates
from app.utils import parse_money

router = Router()


@router.message(Command("living_minimum"))
@router.message(F.text == "🛟 Минимум на жизнь")
async def living_minimum_handler(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        summary = await living_service.get_living_minimum_summary(session, user.id)
    keyboard = living_minimum_enabled_keyboard() if summary["settings"].is_enabled else living_minimum_disabled_keyboard()
    await message.answer(format_living_minimum_summary(summary), reply_markup=keyboard)


@router.callback_query(F.data == "living:set")
async def ask_living_minimum_amount(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(LivingMinimumStates.amount)
    await callback.message.answer("Какую сумму нужно оставить на жизнь до следующего дохода? Напиши сумму в рублях, например: 20000")
    await callback.answer()


@router.message(LivingMinimumStates.amount)
async def save_living_minimum_amount(message: Message, state: FSMContext) -> None:
    try:
        amount = parse_money(message.text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Напиши сумму больше нуля, например: 20000")
        return
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        settings = await living_service.enable_living_minimum(session, user.id, amount)
    await state.clear()
    await message.answer(format_living_minimum_updated(settings), reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "living:disable")
async def disable_living_minimum(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
        await living_service.disable_living_minimum(session, user.id)
    await callback.message.answer("Минимум на жизнь отключён.", reply_markup=main_menu_keyboard())
    await callback.answer()
