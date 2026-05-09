from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.handlers import (
    calculations as calculations_handlers,
    common as common_handlers,
    financial_status as financial_status_handlers,
    incomes as incomes_handlers,
    living_minimum as living_minimum_handlers,
    obligations as obligations_handlers,
    payments as payments_handlers,
    progress as progress_handlers,
    salary_plan as salary_plan_handlers,
    savings as savings_handlers,
    settings as settings_handlers,
    what_if as what_if_handlers,
)
from app.keyboards import main_menu_keyboard
from app.texts import (
    BTN_ADD_INCOME,
    BTN_ADD_OBLIGATION,
    BTN_CANCEL_ACTION,
    BTN_EDIT,
    BTN_FINANCIAL_STATUS,
    BTN_LIVING_MINIMUM,
    BTN_MARK_PAYMENT,
    BTN_MENU,
    BTN_MY_INCOMES,
    BTN_PROGRESS,
    BTN_SAFE_TO_SPEND,
    BTN_SALARY_PLAN,
    BTN_SAVINGS,
    BTN_SETTINGS,
    BTN_UPCOMING_PAYMENTS,
    BTN_WHAT_IF_BUY,
)

router = Router()


async def _clear_state(state: FSMContext) -> None:
    if await state.get_state() is not None:
        await state.clear()


@router.message(StateFilter("*"), Command("cancel"))
@router.message(StateFilter("*"), F.text == BTN_CANCEL_ACTION)
async def cancel_current_action(message: Message, state: FSMContext, fsm_was_active: bool = False) -> None:
    current_state = await state.get_state()
    if fsm_was_active or current_state:
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_menu_keyboard())
    else:
        await message.answer("Сейчас нет активного действия.", reply_markup=main_menu_keyboard())


@router.message(StateFilter("*"), Command("menu"))
@router.message(StateFilter("*"), F.text == BTN_MENU)
async def go_to_menu(message: Message, state: FSMContext) -> None:
    await _clear_state(state)
    await message.answer("Главное меню.", reply_markup=main_menu_keyboard())


@router.message(StateFilter("*"), F.text == BTN_FINANCIAL_STATUS)
async def open_financial_status(message: Message, state: FSMContext) -> None:
    await _clear_state(state)
    await financial_status_handlers.financial_status_handler(message)


@router.message(StateFilter("*"), F.text == BTN_SAFE_TO_SPEND)
async def open_safe_to_spend(message: Message, state: FSMContext) -> None:
    await _clear_state(state)
    await calculations_handlers.spend_handler(message)


@router.message(StateFilter("*"), F.text == BTN_WHAT_IF_BUY)
async def open_what_if_buy(message: Message, state: FSMContext) -> None:
    await _clear_state(state)
    await what_if_handlers.what_if_start(message, state)


@router.message(StateFilter("*"), F.text == BTN_SALARY_PLAN)
async def open_salary_plan(message: Message, state: FSMContext) -> None:
    await _clear_state(state)
    await salary_plan_handlers.salary_plan_handler(message)


@router.message(StateFilter("*"), F.text == BTN_LIVING_MINIMUM)
async def open_living_minimum(message: Message, state: FSMContext) -> None:
    await _clear_state(state)
    await living_minimum_handlers.living_minimum_handler(message)


@router.message(StateFilter("*"), F.text == BTN_ADD_INCOME)
async def open_add_income(message: Message, state: FSMContext) -> None:
    await _clear_state(state)
    await incomes_handlers.add_income_start(message, state)


@router.message(StateFilter("*"), F.text == BTN_MY_INCOMES)
async def open_my_incomes(message: Message, state: FSMContext) -> None:
    await _clear_state(state)
    await incomes_handlers.incomes_list_handler(message)


@router.message(StateFilter("*"), F.text == BTN_ADD_OBLIGATION)
async def open_add_obligation(message: Message, state: FSMContext) -> None:
    await _clear_state(state)
    await obligations_handlers.add_obligation_start(message, state)


@router.message(StateFilter("*"), F.text == BTN_UPCOMING_PAYMENTS)
async def open_upcoming_payments(message: Message, state: FSMContext) -> None:
    await _clear_state(state)
    await obligations_handlers.upcoming_payments(message)


@router.message(StateFilter("*"), F.text == BTN_SAVINGS)
async def open_savings(message: Message, state: FSMContext) -> None:
    await _clear_state(state)
    await savings_handlers.savings_handler(message)


@router.message(StateFilter("*"), F.text == BTN_MARK_PAYMENT)
async def open_mark_payment(message: Message, state: FSMContext) -> None:
    await _clear_state(state)
    await payments_handlers.payment_start(message, state)


@router.message(StateFilter("*"), F.text == BTN_PROGRESS)
async def open_progress(message: Message, state: FSMContext) -> None:
    await _clear_state(state)
    await progress_handlers.progress_handler(message)


@router.message(StateFilter("*"), F.text == BTN_EDIT)
async def open_edit(message: Message, state: FSMContext) -> None:
    await _clear_state(state)
    await common_handlers.edit_menu(message)


@router.message(StateFilter("*"), F.text == BTN_SETTINGS)
async def open_settings(message: Message, state: FSMContext) -> None:
    await _clear_state(state)
    await settings_handlers.settings_handler(message)
