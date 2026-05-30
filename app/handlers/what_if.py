from app.texts import BTN_WHAT_IF_BUY

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.database import SessionLocal
from app.formatters import format_purchase_impact
from app.keyboards import cancel_action_keyboard, main_menu_keyboard, purchase_impact_keyboard
from app.services import planning as planning_service
from app.services import what_if as what_if_service
from app.services.users import get_or_create_user_from_telegram
from app.states import WhatIfPurchaseStates
from app.utils import parse_money

router = Router()


@router.message(Command("what_if_buy"))
@router.message(F.text == BTN_WHAT_IF_BUY)
async def what_if_start(message: Message, state: FSMContext) -> None:
    await state.set_state(WhatIfPurchaseStates.amount)
    await message.answer("Какую сумму планируешь потратить?\nНапиши сумму в рублях, например: 5000", reply_markup=cancel_action_keyboard())


@router.callback_query(F.data == "what_if:again")
async def what_if_again(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(WhatIfPurchaseStates.amount)
    await callback.message.answer("Какую сумму планируешь потратить?\nНапиши сумму в рублях, например: 5000", reply_markup=cancel_action_keyboard())
    await callback.answer()


@router.callback_query(F.data == "what_if:add_income")
async def what_if_add_income(callback: CallbackQuery) -> None:
    await callback.message.answer("Нажми «➕ Добавить доход» в меню или используй команду /add_income.", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "what_if:salary_plan")
async def what_if_salary_plan(callback: CallbackQuery) -> None:
    await callback.message.answer("Открой «📆 План до зарплаты» в меню или используй команду /salary_plan.", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "what_if:payments")
async def what_if_payments(callback: CallbackQuery) -> None:
    await callback.message.answer("Открой «📅 Ближайшие платежи» в меню или используй команду /payments.", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.message(WhatIfPurchaseStates.amount)
async def what_if_amount(message: Message, state: FSMContext) -> None:
    try:
        amount = parse_money(message.text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Не смог разобрать сумму. Напиши, например: 5000, 5 000, 5к или 5 000 ₽", reply_markup=cancel_action_keyboard())
        return

    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        today = planning_service.get_today()
        summary = await what_if_service.simulate_purchase(session, user.id, amount, today)
    await state.clear()
    keyboard = purchase_impact_keyboard(summary.get("recommendation_type", "better_not")) if summary.get("can_calculate") else main_menu_keyboard()
    await message.answer(format_purchase_impact(summary), reply_markup=keyboard)

