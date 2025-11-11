import asyncio
import json
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import TELEGRAM_TOKEN
from handlers import start_handler, mark_handler
from callbacks import food_callback, type_callback
from database.db_supabase import supabase_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



async def main():
    
    bot = Bot(
        token=TELEGRAM_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp = Dispatcher()
    
    dp.include_router(start_handler.router)
    dp.include_router(mark_handler.router)
    dp.include_router(food_callback.router)
    dp.include_router(type_callback.router)
    
    logger.info("🍽️ FoodBot запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())