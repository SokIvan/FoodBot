import asyncio
import json
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from aiohttp import web

from config import TELEGRAM_TOKEN
from handlers import start_handler, mark_handler, admin_handler
from callbacks import type_callback
from database.db_supabase import supabase_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные переменные для веб-сервера
bot_instance = None
dp_instance = None

async def self_ping():
    """Функция для само-пинга"""
    try:
        logger.info("🔄 Самопинг выполнен - бот активен")
    except Exception as e:
        logger.error(f"Ошибка при самопинге: {e}")

async def health_check(request):
    """Простой эндпоинт для health check"""
    return web.Response(text="Bot is alive!")

async def start_bot():
    """Запуск бота"""
    global bot_instance, dp_instance
    
    bot_instance = Bot(
        token=TELEGRAM_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp_instance = Dispatcher()
    
    # Настройка планировщика для самопинга
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        self_ping,
        trigger=IntervalTrigger(minutes=14),
        id='self_ping',
        replace_existing=True
    )
    scheduler.start()
    
    dp_instance.include_router(start_handler.router)
    dp_instance.include_router(mark_handler.router)
    dp_instance.include_router(type_callback.router)
    dp_instance.include_router(admin_handler.router)
    
    logger.info("🍽️ FoodBot запущен!")
    logger.info("🔄 Самопинг активирован - интервал 14 минут")
    
    # Запускаем бота в фоне
    asyncio.create_task(dp_instance.start_polling(bot_instance))

async def on_shutdown(app):
    """Корректное завершение работы"""
    if bot_instance:
        await bot_instance.session.close()

async def create_app():
    """Создание веб-приложения"""
    app = web.Application()
    
    # Добавляем эндпоинты
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    # Запускаем бота при старте приложения
    app.on_startup.append(lambda app: start_bot())
    app.on_shutdown.append(on_shutdown)
    
    return app

if __name__ == "__main__":
    # Запускаем веб-сервер на порте, который предоставляет Render
    port = int(os.environ.get("PORT", 10000))
    web.run_app(create_app(), port=port, host='0.0.0.0')