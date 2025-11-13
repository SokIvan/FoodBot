import asyncio
import json
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import TELEGRAM_TOKEN
from handlers import start_handler, mark_handler, admin_handler
from callbacks import type_callback
from database.db_supabase import supabase_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def self_ping():
    """Функция для само-пинга, чтобы бот не засыпал"""
    try:
        # Можно добавить логирование для отслеживания работы
        logger.info("🔄 Самопинг выполнен - бот активен")
        
        # Если у вас есть веб-сервер, можно делать HTTP запрос
        # Но для простого бота достаточно просто логирования
    except Exception as e:
        logger.error(f"Ошибка при самопинге: {e}")

async def main():
    
    bot = Bot(
        token=TELEGRAM_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp = Dispatcher()
    
    # Настройка планировщика для самопинга
    scheduler = AsyncIOScheduler()
    
    # Запускаем самопинг каждые 14 минут
    scheduler.add_job(
        self_ping,
        trigger=IntervalTrigger(minutes=14),
        id='self_ping',
        replace_existing=True
    )
    
    scheduler.start()
    
    dp.include_router(start_handler.router)
    dp.include_router(mark_handler.router)
    dp.include_router(type_callback.router)
    dp.include_router(admin_handler.router)
    
    logger.info("🍽️ FoodBot запущен!")
    logger.info("🔄 Самопинг активирован - интервал 14 минут")
    
    try:
        await dp.start_polling(bot)
    finally:
        # Корректное завершение работы планировщика
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())