from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.keyboards import main_menu_keyboard
from app.texts import BTN_MARK_PAYMENT, FROZEN_COMMANDS, FROZEN_FEATURE_BUTTONS, FROZEN_FEATURE_MESSAGE, FROZEN_PAYMENT_MESSAGE

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


@router.message(StateFilter("*"), F.text.func(_is_frozen_feature_text))
async def frozen_feature_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    text = FROZEN_PAYMENT_MESSAGE if _is_frozen_payment_text(message.text) else FROZEN_FEATURE_MESSAGE
    await message.answer(text, reply_markup=main_menu_keyboard())
