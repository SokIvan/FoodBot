import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
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

async def start_bot():
    """Запуск Telegram бота"""
    global bot, dp, scheduler
    
    try:
        bot = Bot(
            token=TELEGRAM_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
        )
        dp = Dispatcher()
        
        # Настройка планировщика для самопинга
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            lambda: logger.info("🔄 Bot is alive"),
            trigger=IntervalTrigger(minutes=10),
            id='keep_alive'
        )
        scheduler.start()
        
        # Регистрация роутеров
        dp.include_router(start_handler.router)
        dp.include_router(mark_handler.router)
        dp.include_router(type_callback.router)
        dp.include_router(admin_handler.router)
        
        logger.info("🍽️ FoodBot запущен!")
        logger.info("🔄 Keep-alive активирован (10 минут)")
        
        # Запускаем бота в фоне
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")
        raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager для FastAPI"""
    # Startup
    logger.info("🚀 Starting application...")
    
    # Запускаем бота в фоне
    bot_task = asyncio.create_task(start_bot())
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down application...")
    
    if scheduler:
        scheduler.shutdown()
    
    if bot:
        await bot.session.close()
    
    bot_task.cancel()
    try:
        await bot_task
    except asyncio.CancelledError:
        pass

# Создаем FastAPI приложение
app = FastAPI(
    title="FoodBot API",
    description="Telegram Bot for Food School",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "message": "🤖 FoodBot is running!",
        "status": "active"
    }

@app.get("/health")
async def health_check():
    """Health check для Render"""
    return {
        "status": "healthy",
        "service": "food-bot"
    }

@app.get("/ping")
async def ping():
    """Простой ping"""
    return {"message": "pong"}

@app.post("/restart")
async def restart_bot():
    """Перезапуск бота (для админов)"""
    # Здесь можно добавить логику перезапуска
    return {"message": "Restart command received"}

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 10000))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False  # На продакшене reload должен быть False
    )