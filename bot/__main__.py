import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import TELEGRAM_TOKEN
from handlers.start_handler import router as start_router
from callbacks.food_callback import router as callback_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    bot = Bot(
        token=TELEGRAM_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp = Dispatcher()
    
    dp.include_router(start_router)
    dp.include_router(callback_router)
    
    logger.info("🍽️ FoodBot запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())