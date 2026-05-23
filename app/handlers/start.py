from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import get_settings
from app.database import SessionLocal
from app.formatters import format_help
from app.keyboards import main_menu_keyboard
from app.services import activity as activity_service
from app.services.users import get_or_create_user_from_telegram

router = Router()


@router.message(Command("start"))
async def start_handler(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        show_im_back, show_return_prompt = await _get_return_menu_state(session, user)
    text = (
        "Привет! Я Платёжный Компас. Помогу понять, сколько денег нужно отложить с каждого дохода, "
        "чтобы вовремя закрывать кредиты, рассрочки и обязательные платежи.\n\n"
        "Чтобы начать:\n"
        "1. Добавь свои кредиты и обязательные платежи.\n"
        "2. Добавь ожидаемые доходы.\n"
        "3. Когда деньги придут, отметь доход как полученный.\n"
        "4. Я скажу, сколько отложить и сколько можно тратить."
    )
    await message.answer(text, reply_markup=main_menu_keyboard(show_im_back=show_im_back))
    if show_return_prompt:
        await message.answer(_return_prompt_text(), reply_markup=main_menu_keyboard(show_im_back=True))


@router.message(Command("menu"))
async def menu_handler(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        show_im_back, show_return_prompt = await _get_return_menu_state(session, user)
    text = _return_prompt_text() if show_return_prompt else "Главное меню"
    await message.answer(text, reply_markup=main_menu_keyboard(show_im_back=show_im_back))


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(format_help(), reply_markup=main_menu_keyboard())


async def _get_return_menu_state(session, user) -> tuple[bool, bool]:
    now = datetime.now(ZoneInfo(user.timezone or get_settings().timezone))
    show_im_back = await activity_service.should_show_im_back(session, user.id, now)
    show_return_prompt = await activity_service.should_show_return_prompt(session, user.id, now)
    if show_return_prompt:
        await activity_service.mark_return_prompt_shown(session, user.id, now)
    if not show_im_back:
        await activity_service.update_user_activity(session, user.id, now)
    return show_im_back, show_return_prompt


def _return_prompt_text() -> str:
    return (
        "Похоже, ты давно не заходил.\n\n"
        "Если за это время платежи и доходы уже произошли, я могу быстро привести план в порядок."
    )
