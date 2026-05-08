import asyncio
import logging

from aiogram.types import BotCommand

from app.bot import create_bot, create_dispatcher
from app.database import init_db
from app.scheduler import setup_scheduler


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    await init_db()
    bot = create_bot()
    dp = create_dispatcher()
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Запустить бота"),
            BotCommand(command="menu", description="Главное меню"),
            BotCommand(command="status", description="Финансовый статус"),
            BotCommand(command="salary_plan", description="План до зарплаты"),
            BotCommand(command="living_minimum", description="Минимум на жизнь"),
            BotCommand(command="what_if_buy", description="Что если купить"),
            BotCommand(command="add_income", description="Добавить доход"),
            BotCommand(command="incomes", description="Мои доходы"),
            BotCommand(command="savings", description="Накопления"),
            BotCommand(command="add_obligation", description="Добавить платёж"),
            BotCommand(command="spend", description="Сколько можно тратить"),
            BotCommand(command="payments", description="Ближайшие платежи"),
            BotCommand(command="progress", description="Прогресс долгов"),
            BotCommand(command="help", description="Помощь"),
        ]
    )
    scheduler = setup_scheduler(bot)
    scheduler.start()
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
