import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from config import TELEGRAM_TOKEN
from database.db_supabase import supabase_client
from handlers.start_handler import router as start_router
from callbacks.food_callback import router as callback_router

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Инициализация бота (правильный способ для aiogram 3.x)
    bot = Bot(token=TELEGRAM_TOKEN, parse_mode=ParseMode.MARKDOWN)
    dp = Dispatcher()
    
    # Регистрация роутеров
    dp.include_router(start_router)
    dp.include_router(callback_router)
    
    # Инициализация базы данных
    try:
        await supabase_client.create_example("test_key", "test_example_value")
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка инициализации БД: {e}")
    
    logger.info("🍽️ FoodBot запущен!")
    
    # Запуск поллинга
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())