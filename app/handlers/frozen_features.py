from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.keyboards import main_menu_keyboard
from app.texts import FROZEN_COMMANDS, FROZEN_FEATURE_BUTTONS, FROZEN_FEATURE_MESSAGE

router = Router()


def _is_frozen_feature_text(text: str | None) -> bool:
    if not text:
        return False
    stripped = text.strip()
    command = stripped.split(maxsplit=1)[0].split("@", 1)[0]
    return stripped in FROZEN_FEATURE_BUTTONS or command in FROZEN_COMMANDS


@router.message(StateFilter("*"), F.text.func(_is_frozen_feature_text))
async def frozen_feature_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(FROZEN_FEATURE_MESSAGE, reply_markup=main_menu_keyboard())
