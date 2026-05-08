from datetime import datetime
from zoneinfo import ZoneInfo
from app.texts import BTN_MY_INCOMES
from app.texts import BTN_ADD_INCOME

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import get_settings
from app.database import SessionLocal
from app.formatters import format_allocation_result, format_income_added, format_incomes_list
from app.keyboards import income_status_keyboard, main_menu_keyboard, today_keyboard
from app.services import allocation as allocation_service
from app.services import incomes as income_service
from app.services.users import get_or_create_user_from_telegram
from app.states import AddIncomeStates
from app.utils import parse_date, parse_money

router = Router()


@router.message(Command("incomes"))
@router.message(F.text == BTN_MY_INCOMES)
async def incomes_list_handler(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        today = datetime.now(ZoneInfo(user.timezone or get_settings().timezone)).date()
        incomes = await income_service.get_user_incomes_summary(session, user.id, today)
    await message.answer(format_incomes_list(incomes), reply_markup=main_menu_keyboard())


@router.message(Command("add_income"))
@router.message(F.text == BTN_ADD_INCOME)
@router.message(F.text == BTN_ADD_INCOME)
async def add_income_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AddIncomeStates.title)
    await message.answer("Как назвать доход? Например: Аванс, Зарплата, Подработка.")


@router.message(AddIncomeStates.title)
async def add_income_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(AddIncomeStates.amount)
    await message.answer("Какая сумма дохода? Напиши сумму в рублях.")


@router.message(AddIncomeStates.amount)
async def add_income_amount(message: Message, state: FSMContext) -> None:
    try:
        amount = parse_money(message.text)
    except ValueError:
        await message.answer("Не смог разобрать сумму. Напиши, например: 35000 или 35к")
        return
    await state.update_data(amount=amount)
    await state.set_state(AddIncomeStates.income_date)
    await message.answer("Дата дохода? Напиши в формате ДД.ММ.ГГГГ или нажми «Сегодня».", reply_markup=today_keyboard("income_today"))


@router.callback_query(AddIncomeStates.income_date, F.data == "income_today")
async def add_income_today(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(income_date=parse_date("сегодня", get_settings().timezone))
    await state.set_state(AddIncomeStates.status)
    await callback.message.answer("Этот доход уже пришёл или ожидается?", reply_markup=income_status_keyboard())
    await callback.answer()


@router.message(AddIncomeStates.income_date)
async def add_income_date(message: Message, state: FSMContext) -> None:
    try:
        value = parse_date(message.text, get_settings().timezone)
    except ValueError:
        await message.answer("Не смог разобрать дату. Напиши ДД.ММ.ГГГГ или нажми «Сегодня».")
        return
    await state.update_data(income_date=value)
    await state.set_state(AddIncomeStates.status)
    await message.answer("Этот доход уже пришёл или ожидается?", reply_markup=income_status_keyboard())


@router.callback_query(AddIncomeStates.status, F.data.startswith("income_status:"))
async def add_income_finish(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    data["status"] = callback.data.split(":", 1)[1]
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
        income = await income_service.create_income(session, user.id, data)
        if income.status == "received":
            result = await allocation_service.process_received_income(session, user.id, income.id, parse_date("сегодня", user.timezone))
            text = format_allocation_result(result)
        else:
            text = format_income_added(income)
    await state.clear()
    await callback.message.answer(text, reply_markup=main_menu_keyboard())
    await callback.answer()
