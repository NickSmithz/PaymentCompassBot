from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import get_settings
from app.handlers import common, calculations, frozen_features, incomes, navigation, obligations, payments, progress, return_flow, settings, start
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
        frozen_features.router,
        return_flow.router,
        # Временно отключено до стабилизации ядра MVP:
        # financial_status.router,
        # salary_plan.router,
        # living_minimum.router,
        # savings.router,
        # what_if.router,
        incomes.router,
        obligations.router,
        payments.router,
        calculations.router,
        progress.router,
        settings.router,
        common.router,
    ):
        dp.include_router(router)
    return dp


