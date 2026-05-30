from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.config import get_settings
from app.database import SessionLocal
from app.formatters import (
    format_dev_clear_all_result,
    format_dev_make_incomes_recurring_result,
    format_dev_reset_state_result,
)
from app.keyboards import (
    dev_clear_all_confirm_keyboard,
    dev_make_incomes_recurring_confirm_keyboard,
    dev_reset_confirm_keyboard,
    main_menu_keyboard,
)
from app.services import dev_tools as dev_tools_service
from app.services import planning as planning_service
from app.services.users import get_or_create_user_from_telegram

router = Router()

DEV_ONLY_TEXT = "Команда доступна только в режиме разработки."

DEV_RESET_CONFIRM_TEXT = (
    "⚠️ DEV-сброс состояния\n\n"
    "Это действие:\n"
    "— сбросит доходы в статус «Ожидается»;\n"
    "— очистит резервы;\n"
    "— очистит оплаты;\n"
    "— вернёт платежи в активное состояние;\n"
    "— не удалит сами доходы и платежи.\n\n"
    "Продолжить?"
)

DEV_CLEAR_ALL_CONFIRM_TEXT = (
    "⚠️ DEV-полная очистка\n\n"
    "Это действие полностью удалит:\n"
    "— все доходы;\n"
    "— все платежи;\n"
    "— все резервы;\n"
    "— все оплаты;\n"
    "— связанные записи прогресса.\n\n"
    "Это действие нельзя отменить.\n\n"
    "Продолжить?"
)

DEV_MAKE_INCOMES_RECURRING_CONFIRM_TEXT = (
    "⚠️ DEV-нормализация доходов\n\n"
    "Это действие сделает все существующие доходы регулярными:\n"
    "— is_recurring=True;\n"
    "— recurrence_type=monthly;\n"
    "— parent_income_id будет заполнен;\n"
    "— period_date будет заполнен.\n\n"
    "После этого бот создаст будущие ежемесячные экземпляры доходов.\n\n"
    "Резервы и оплаты не изменятся.\n\n"
    "Продолжить?"
)


def _dev_mode_enabled() -> bool:
    return get_settings().dev_mode


@router.message(Command("dev_reset_state"))
async def dev_reset_state(message: Message) -> None:
    if not _dev_mode_enabled():
        await message.answer(DEV_ONLY_TEXT, reply_markup=main_menu_keyboard())
        return
    await message.answer(DEV_RESET_CONFIRM_TEXT, reply_markup=dev_reset_confirm_keyboard())


@router.message(Command("dev_clear_all"))
async def dev_clear_all(message: Message) -> None:
    if not _dev_mode_enabled():
        await message.answer(DEV_ONLY_TEXT, reply_markup=main_menu_keyboard())
        return
    await message.answer(DEV_CLEAR_ALL_CONFIRM_TEXT, reply_markup=dev_clear_all_confirm_keyboard())


@router.message(Command("dev_make_all_incomes_recurring"))
async def dev_make_all_incomes_recurring(message: Message) -> None:
    if not _dev_mode_enabled():
        await message.answer(DEV_ONLY_TEXT, reply_markup=main_menu_keyboard())
        return
    await message.answer(
        DEV_MAKE_INCOMES_RECURRING_CONFIRM_TEXT,
        reply_markup=dev_make_incomes_recurring_confirm_keyboard(),
    )


@router.callback_query(F.data == "dev_confirm_reset_state")
async def confirm_dev_reset_state(callback: CallbackQuery) -> None:
    if not _dev_mode_enabled():
        await callback.message.answer(DEV_ONLY_TEXT, reply_markup=main_menu_keyboard())
        await callback.answer()
        return
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        summary = await dev_tools_service.reset_user_state_for_testing(session, user.id)
    await callback.message.answer(format_dev_reset_state_result(summary), reply_markup=main_menu_keyboard())
    await callback.answer("DEV-сброс выполнен")


@router.callback_query(F.data == "dev_confirm_clear_all")
async def confirm_dev_clear_all(callback: CallbackQuery) -> None:
    if not _dev_mode_enabled():
        await callback.message.answer(DEV_ONLY_TEXT, reply_markup=main_menu_keyboard())
        await callback.answer()
        return
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        summary = await dev_tools_service.clear_user_data_for_testing(session, user.id)
    await callback.message.answer(format_dev_clear_all_result(summary), reply_markup=main_menu_keyboard())
    await callback.answer("DEV-очистка выполнена")


@router.callback_query(F.data == "dev_confirm_make_incomes_recurring")
async def confirm_dev_make_all_incomes_recurring(callback: CallbackQuery) -> None:
    if not _dev_mode_enabled():
        await callback.message.answer(DEV_ONLY_TEXT, reply_markup=main_menu_keyboard())
        await callback.answer()
        return
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        summary = await dev_tools_service.make_all_incomes_recurring_for_testing(
            session,
            user.id,
            planning_service.get_today(),
        )
    await callback.message.answer(format_dev_make_incomes_recurring_result(summary), reply_markup=main_menu_keyboard())
    await callback.answer("Доходы нормализованы")


@router.callback_query(F.data == "dev_cancel")
async def cancel_dev_action(callback: CallbackQuery) -> None:
    await callback.message.answer("DEV-действие отменено.", reply_markup=main_menu_keyboard())
    await callback.answer()
