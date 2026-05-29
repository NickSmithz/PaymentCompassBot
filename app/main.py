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
            BotCommand(command="help", description="Помощь"),
            BotCommand(command="add_income", description="Добавить доход"),
            BotCommand(command="incomes", description="Мои доходы"),
            BotCommand(command="add_obligation", description="Добавить платёж"),
            BotCommand(command="payments", description="Ближайшие платежи"),
            BotCommand(command="spend", description="Сколько можно тратить"),
            BotCommand(command="im_back", description="Я вернулся"),
            BotCommand(command="cancel", description="Отменить действие"),
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
