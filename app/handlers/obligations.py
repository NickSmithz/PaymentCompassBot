import logging
from app.texts import BTN_ADD_OBLIGATION
from app.texts import BTN_UPCOMING_PAYMENTS

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import get_settings
from app.database import SessionLocal
from app.formatters import format_obligation_added, format_obligations_list
from app.keyboards import main_menu_keyboard, obligation_type_keyboard, priority_keyboard, recurring_keyboard
from app.services import obligations as obligation_service
from app.services.users import get_or_create_user_from_telegram
from app.states import AddObligationStates
from app.utils import parse_date, parse_money

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("add_obligation"))
@router.message(F.text == BTN_ADD_OBLIGATION)
@router.message(F.text == BTN_ADD_OBLIGATION)
async def add_obligation_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AddObligationStates.title)
    await message.answer("Как называется платёж? Например: Кредит Сбер, Ипотека, Рассрочка, Кредитка.")


@router.message(AddObligationStates.title)
async def add_obligation_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(AddObligationStates.type)
    await message.answer("Выбери тип платежа:", reply_markup=obligation_type_keyboard())


@router.callback_query(AddObligationStates.type, F.data.startswith("otype:"))
async def add_obligation_type(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(type=callback.data.split(":", 1)[1])
    await state.set_state(AddObligationStates.amount)
    await callback.message.answer("Какая сумма платежа в месяц? Напиши сумму в рублях, например: 12500")
    await callback.answer()


@router.message(AddObligationStates.amount)
async def add_obligation_amount(message: Message, state: FSMContext) -> None:
    try:
        amount = parse_money(message.text)
    except ValueError:
        await message.answer("Не смог разобрать сумму. Напиши, например: 12500 или 12 500 ₽")
        return
    await state.update_data(monthly_payment_amount=amount)
    await state.set_state(AddObligationStates.next_payment_date)
    await message.answer("Какая ближайшая дата платежа? Напиши в формате ДД.ММ.ГГГГ, например: 15.05.2026")


@router.message(AddObligationStates.next_payment_date)
async def add_obligation_date(message: Message, state: FSMContext) -> None:
    try:
        value = parse_date(message.text, get_settings().timezone)
    except ValueError:
        await message.answer("Не смог разобрать дату. Напиши в формате ДД.ММ.ГГГГ, например: 15.05.2026")
        return
    await state.update_data(next_payment_date=value)
    await state.set_state(AddObligationStates.is_recurring)
    await message.answer("Платёж повторяется каждый месяц?", reply_markup=recurring_keyboard())


@router.callback_query(AddObligationStates.is_recurring, F.data.startswith("recurring:"))
async def add_obligation_recurring(callback: CallbackQuery, state: FSMContext) -> None:
    is_recurring = callback.data.endswith("yes")
    data = await state.get_data()
    await state.update_data(is_recurring=is_recurring, payment_day=data["next_payment_date"].day if is_recurring else None)
    await state.set_state(AddObligationStates.total_debt_amount)
    await callback.message.answer("Какой общий остаток долга? Можно написать 0, если не хочешь указывать.")
    await callback.answer()


@router.message(AddObligationStates.total_debt_amount)
async def add_obligation_debt(message: Message, state: FSMContext) -> None:
    try:
        amount = parse_money(message.text)
    except ValueError:
        await message.answer("Не смог разобрать сумму. Напиши 0 или сумму в рублях.")
        return
    await state.update_data(total_debt_amount=amount if amount > 0 else None)
    await state.set_state(AddObligationStates.already_reserved_amount)
    await message.answer("Сколько уже отложено на этот платёж? Можно написать 0.")


@router.message(AddObligationStates.already_reserved_amount)
async def add_obligation_reserved(message: Message, state: FSMContext) -> None:
    try:
        amount = parse_money(message.text)
    except ValueError:
        await message.answer("Не смог разобрать сумму. Напиши 0 или сумму в рублях.")
        return
    await state.update_data(already_reserved_amount=amount)
    await state.set_state(AddObligationStates.priority)
    await message.answer("Насколько критичен этот платёж?", reply_markup=priority_keyboard())


@router.callback_query(AddObligationStates.priority, F.data.startswith("priority:"))
async def add_obligation_finish(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    data["priority"] = int(callback.data.split(":")[1])
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
        obligation = await obligation_service.create_obligation(session, user.id, data)
    await state.clear()
    await callback.message.answer(format_obligation_added(obligation), reply_markup=main_menu_keyboard())
    await callback.answer()


@router.message(Command("payments"))
@router.message(F.text == BTN_UPCOMING_PAYMENTS)
@router.message(F.text == BTN_UPCOMING_PAYMENTS)
async def upcoming_payments(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        items = await obligation_service.get_upcoming_obligations_summary(session, user.id, parse_date("сегодня", user.timezone))
    await message.answer(format_obligations_list(items), reply_markup=main_menu_keyboard())
