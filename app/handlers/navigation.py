from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.handlers import (
    calculations as calculations_handlers,
    common as common_handlers,
    incomes as incomes_handlers,
    obligations as obligations_handlers,
    progress as progress_handlers,
    settings as settings_handlers,
)
from app.keyboards import main_menu_keyboard
from app.texts import (
    BTN_ADD_INCOME,
    BTN_ADD_OBLIGATION,
    BTN_CANCEL_ACTION,
    BTN_EDIT,
    BTN_MENU,
    BTN_MY_INCOMES,
    BTN_PROGRESS,
    BTN_SAFE_TO_SPEND,
    BTN_SETTINGS,
    BTN_UPCOMING_PAYMENTS,
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


@router.message(StateFilter("*"), F.text == BTN_SAFE_TO_SPEND)
async def open_safe_to_spend(message: Message, state: FSMContext) -> None:
    await _clear_state(state)
    await calculations_handlers.spend_handler(message)


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
