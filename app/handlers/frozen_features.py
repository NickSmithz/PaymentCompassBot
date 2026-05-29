from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.keyboards import main_menu_keyboard
from app.texts import (
    BTN_MARK_PAYMENT,
    BTN_PROGRESS,
    FROZEN_COMMANDS,
    FROZEN_FEATURE_BUTTONS,
    FROZEN_FEATURE_MESSAGE,
    FROZEN_PAYMENT_MESSAGE,
    FROZEN_PROGRESS_MESSAGE,
)

router = Router()


def _is_frozen_feature_text(text: str | None) -> bool:
    if not text:
        return False
    stripped = text.strip()
    command = stripped.split(maxsplit=1)[0].split("@", 1)[0]
    return stripped in FROZEN_FEATURE_BUTTONS or command in FROZEN_COMMANDS


def _is_frozen_payment_text(text: str | None) -> bool:
    if not text:
        return False
    stripped = text.strip()
    command = stripped.split(maxsplit=1)[0].split("@", 1)[0]
    return stripped == BTN_MARK_PAYMENT or command in {"/mark_payment", "/pay", "/payment"}


def _is_frozen_progress_text(text: str | None) -> bool:
    if not text:
        return False
    stripped = text.strip()
    command = stripped.split(maxsplit=1)[0].split("@", 1)[0]
    return stripped == BTN_PROGRESS or command == "/progress"


@router.message(StateFilter("*"), F.text.func(_is_frozen_feature_text))
async def frozen_feature_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    if _is_frozen_payment_text(message.text):
        text = FROZEN_PAYMENT_MESSAGE
    elif _is_frozen_progress_text(message.text):
        text = FROZEN_PROGRESS_MESSAGE
    else:
        text = FROZEN_FEATURE_MESSAGE
    await message.answer(text, reply_markup=main_menu_keyboard())
