import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import TELEGRAM_TOKEN
from handlers import start_handler, mark_handler, admin_handler
from callbacks import type_callback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Основная функция запуска бота"""
    bot = Bot(
        token=TELEGRAM_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp = Dispatcher()
    
    # Регистрация роутеров
    dp.include_router(start_handler.router)
    dp.include_router(mark_handler.router)
    dp.include_router(type_callback.router)
    dp.include_router(admin_handler.router)
    
    logger.info("🍽️ FoodBot запущен!")
    
    # Запускаем polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")