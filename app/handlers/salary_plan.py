from app.texts import BTN_SALARY_PLAN

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.database import SessionLocal
from app.formatters import format_salary_plan
from app.keyboards import main_menu_keyboard
from app.services import planning as planning_service
from app.services import salary_plan as salary_plan_service
from app.services.users import get_or_create_user_from_telegram

router = Router()


@router.message(Command("salary_plan"))
@router.message(F.text == BTN_SALARY_PLAN)
async def salary_plan_handler(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user_from_telegram(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        today = planning_service.get_today()
        summary = await salary_plan_service.get_salary_plan(session, user.id, today)
    await message.answer(format_salary_plan(summary), reply_markup=main_menu_keyboard())
