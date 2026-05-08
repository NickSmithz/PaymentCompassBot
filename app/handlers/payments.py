from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import get_settings
from app.database import SessionLocal
from app.formatters import format_payment_added
from app.keyboards import main_menu_keyboard, obligations_inline_keyboard, today_keyboard
from app.services import obligations as obligation_service
from app.services import payments as payment_service
from app.services.users import get_or_create_user_from_telegram
from app.states import PaymentStates
from app.utils import parse_date, parse_money

router = Router()


@router.message(F.text == "✅ Отметить оплату")
async def payment_start(message: Message, state: FSMContext) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        obligations = await obligation_service.list_active_obligations(session, user.id)
    if not obligations:
        await message.answer("Пока нечего оплачивать: сначала добавь платёж.", reply_markup=main_menu_keyboard())
        return
    await state.set_state(PaymentStates.choose_obligation)
    await message.answer("Выбери платёж:", reply_markup=obligations_inline_keyboard(obligations, "pay_obl"))


@router.callback_query(F.data.startswith("pay_obl:"))
async def payment_choose(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Выбор обновлён")
    obligation_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    previous_obligation_id = data.get("obligation_id")

    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
        obligation = await payment_service.get_active_obligation_for_payment(session, user.id, obligation_id)

    if obligation is None:
        await callback.message.answer("Платёж не найден или уже отключён.", reply_markup=main_menu_keyboard())
        return

    await state.update_data(obligation_id=obligation.id, obligation_title=obligation.title)
    await state.set_state(PaymentStates.amount)
    prefix = "Выбран другой платёж" if previous_obligation_id and previous_obligation_id != obligation.id else "Выбран платёж"
    await callback.message.answer(f"{prefix}: {obligation.title}\n\nВведи сумму оплаты в рублях.\nНапример: 12500")


@router.message(PaymentStates.amount)
async def payment_amount(message: Message, state: FSMContext) -> None:
    try:
        amount = parse_money(message.text)
    except ValueError:
        await message.answer("Не смог разобрать сумму. Напиши сумму в рублях.")
        return
    await state.update_data(amount=amount)
    await state.set_state(PaymentStates.paid_at)
    await message.answer("Дата оплаты? Напиши дату или нажми «Сегодня».", reply_markup=today_keyboard("paid_today"))


@router.callback_query(PaymentStates.paid_at, F.data == "paid_today")
async def payment_today(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _finish_payment(callback.message, callback.from_user, state, parse_date("сегодня", get_settings().timezone))


@router.message(PaymentStates.paid_at)
async def payment_date(message: Message, state: FSMContext) -> None:
    try:
        paid_at = parse_date(message.text, get_settings().timezone)
    except ValueError:
        await message.answer("Не смог разобрать дату. Напиши ДД.ММ.ГГГГ или нажми «Сегодня».")
        return
    await _finish_payment(message, message.from_user, state, paid_at)


async def _finish_payment(message: Message, tg_user, state: FSMContext, paid_at):
    data = await state.get_data()
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, tg_user.id, tg_user.username, tg_user.first_name)
        obligation = await payment_service.process_obligation_payment(session, user.id, data["obligation_id"], data["amount"], paid_at)
    await state.clear()
    if obligation is None:
        await message.answer("Платёж не найден или уже отключён.", reply_markup=main_menu_keyboard())
        return
    await message.answer(format_payment_added(obligation), reply_markup=main_menu_keyboard())
