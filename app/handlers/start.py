from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.database import SessionLocal
from app.formatters import format_help
from app.keyboards import main_menu_keyboard
from app.services.users import get_or_create_user_from_telegram

router = Router()


@router.message(Command("start"))
async def start_handler(message: Message) -> None:
    async with SessionLocal() as session:
        await get_or_create_user_from_telegram(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
    text = (
        "Привет! Я АнтиПросрочка Bot. Помогу понять, сколько денег нужно отложить с каждого дохода, "
        "чтобы не пропустить платежи по кредитам, рассрочкам и обязательным платежам.\n\n"
        "Чтобы начать:\n"
        "1. Добавь свои кредиты и обязательные платежи.\n"
        "2. Добавь ожидаемые доходы.\n"
        "3. Когда деньги придут, отметь доход как полученный.\n"
        "4. Я скажу, сколько отложить и сколько можно тратить."
    )
    await message.answer(text, reply_markup=main_menu_keyboard())


@router.message(Command("menu"))
async def menu_handler(message: Message) -> None:
    await message.answer("Главное меню", reply_markup=main_menu_keyboard())


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(format_help(), reply_markup=main_menu_keyboard())
