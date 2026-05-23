from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import get_settings
from app.database import SessionLocal
from app.formatters import format_obligations_list, format_return_preview, format_return_result
from app.keyboards import cancel_action_keyboard, main_menu_keyboard, return_preview_keyboard, return_result_keyboard
from app.services import activity as activity_service
from app.services import obligations as obligations_service
from app.services import return_flow as return_flow_service
from app.services.users import get_or_create_user_from_telegram
from app.states import AddIncomeStates
from app.texts import BTN_IM_BACK

router = Router()


@router.message(StateFilter("*"), Command("im_back"))
@router.message(StateFilter("*"), F.text == BTN_IM_BACK)
async def im_back_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        now = datetime.now(ZoneInfo(user.timezone or get_settings().timezone))
        today = now.date()
        summary = await return_flow_service.get_return_preview(session, user.id, today)
        await activity_service.update_user_activity(session, user.id, now)

    has_updates = summary["overdue_obligations_count"] > 0 or summary["past_expected_incomes_count"] > 0
    keyboard = return_preview_keyboard() if has_updates else main_menu_keyboard()
    await message.answer(format_return_preview(summary, today), reply_markup=keyboard)


@router.callback_query(F.data == "confirm_im_back")
async def confirm_im_back(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        now = datetime.now(ZoneInfo(user.timezone or get_settings().timezone))
        today = now.date()
        summary = await return_flow_service.apply_return_flow(session, user.id, today)
        await activity_service.update_user_activity(session, user.id, now)

    await callback.message.answer(format_return_result(summary, today), reply_markup=return_result_keyboard())
    await callback.answer("Данные обновлены")


@router.callback_query(F.data == "cancel_im_back")
async def cancel_im_back(callback: CallbackQuery) -> None:
    await callback.message.answer("Обновление отменено.", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "im_back:add_income")
async def im_back_add_income(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddIncomeStates.title)
    await callback.message.answer("Как назвать доход? Например: Аванс, Зарплата, Подработка.", reply_markup=cancel_action_keyboard())
    await callback.answer()


@router.callback_query(F.data == "im_back:payments")
async def im_back_payments(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        today = datetime.now(ZoneInfo(user.timezone or get_settings().timezone)).date()
        summary = await obligations_service.get_upcoming_obligations_summary(session, user.id, today)

    await callback.message.answer(format_obligations_list(summary), reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "im_back:menu")
async def im_back_menu(callback: CallbackQuery) -> None:
    await callback.message.answer("Главное меню", reply_markup=main_menu_keyboard())
    await callback.answer()
