import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import TELEGRAM_TOKEN
from handlers import start_handler, mark_handler, admin_handler
from callbacks import type_callback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные переменные
bot = None
dp = None
scheduler = None

async def start_telegram_bot():
    """Запуск Telegram бота"""
    global bot, dp, scheduler
    
    try:
        bot = Bot(
            token=TELEGRAM_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
        )
        dp = Dispatcher()
        
        # Планировщик для самопинга
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            lambda: logger.info("🔄 Bot heartbeat"),
            trigger=IntervalTrigger(minutes=10),
            id='heartbeat'
        )
        scheduler.start()
        
        # Регистрация роутеров
        dp.include_router(start_handler.router)
        dp.include_router(mark_handler.router)
        dp.include_router(type_callback.router)
        dp.include_router(admin_handler.router)
        
        logger.info("🍽️ FoodBot запущен!")
        logger.info("🔄 Keep-alive активирован (10 минут)")
        
        # Запускаем polling
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")
        raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager для управления жизненным циклом"""
    # Startup
    logger.info("🚀 Starting FoodBot application...")
    
    # Запускаем бота в фоновой задаче
    bot_task = asyncio.create_task(start_telegram_bot())
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down FoodBot...")
    
    # Останавливаем планировщик
    if scheduler and scheduler.running:
        scheduler.shutdown()
    
    # Закрываем сессию бота
    if bot:
        await bot.session.close()
    
    # Отменяем задачу бота
    bot_task.cancel()
    try:
        await bot_task
    except asyncio.CancelledError:
        logger.info("✅ Bot task cancelled successfully")

# Создаем FastAPI приложение
app = FastAPI(
    title="FoodBot",
    description="Telegram Bot for Food School",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "message": "🤖 FoodBot is running!",
        "status": "active",
        "service": "food-school-bot"
    }

@app.get("/health")
async def health_check():
    """Health check для Render"""
    return {
        "status": "healthy",
        "bot": "running"
    }

@app.get("/ping")
async def ping():
    """Простой ping-эндпоинт"""
    return {"message": "pong"}

def main():
    """Основная функция запуска"""
    port = int(os.environ.get("PORT", 10000))
    
    logger.info(f"🌐 Starting server on port {port}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        reload=False,  # На продакшене False!
        access_log=True
    )

if __name__ == "__main__":
    main()