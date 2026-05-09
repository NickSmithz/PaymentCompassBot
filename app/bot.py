from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import get_settings
from app.handlers import common, calculations, financial_status, incomes, living_minimum, navigation, obligations, payments, progress, salary_plan, savings, settings, start, what_if
from app.middlewares.navigation_reset import NavigationResetMiddleware


def create_bot() -> Bot:
    settings = get_settings()
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is empty. Create .env from .env.example and add your Telegram bot token.")
    return Bot(token=settings.bot_token)


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(NavigationResetMiddleware())
    for router in (
        start.router,
        navigation.router,
        financial_status.router,
        what_if.router,
        salary_plan.router,
        obligations.router,
        incomes.router,
        calculations.router,
        payments.router,
        progress.router,
        savings.router,
        living_minimum.router,
        settings.router,
        common.router,
    ):
        dp.include_router(router)
    return dp


