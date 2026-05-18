import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from dotenv import load_dotenv

from db.database import init_db
from handlers.start import router as start_router
from handlers.calc import router as calc_router
from handlers.ai import router as ai_router

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

dp = Dispatcher()
dp.include_router(start_router)
dp.include_router(calc_router)
dp.include_router(ai_router)


async def main() -> None:
    """
    Запускает Telegram-бота в режиме polling.
    """
    if not TELEGRAM_TOKEN:
        raise RuntimeError("Не найден TELEGRAM_BOT_TOKEN в .env")

    init_db()

    bot = Bot(
        token=TELEGRAM_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())