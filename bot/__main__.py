import asyncio
import logging
import os
import signal
import sys
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
is_running = True

def ignore_signal(signum, frame):
    """Игнорируем SIGTERM и другие сигналы остановки"""
    signal_name = {
        signal.SIGTERM: "SIGTERM",
        signal.SIGINT: "SIGINT", 
        signal.SIGQUIT: "SIGQUIT"
    }.get(signum, str(signum))
    
    logger.warning(f"🚫 ИГНОРИРУЕМ сигнал {signal_name}! Бот продолжает работу!")

async def restart_bot():
    """Перезапуск бота при ошибках"""
    global bot, dp
    
    while is_running:
        try:
            logger.info("🔄 Запуск/перезапуск Telegram бота...")
            
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
            await dp.start_polling(bot, handle_signals=False)
            
        except Exception as e:
            logger.error(f"💥 КРИТИЧЕСКАЯ ОШИБКА в боте: {e}")
            
            # Закрываем старые соединения
            if bot:
                try:
                    await bot.session.close()
                except:
                    pass
            
            # Ждем перед перезапуском
            logger.info("🕒 Перезапуск через 10 секунд...")
            await asyncio.sleep(10)
        finally:
            if bot:
                try:
                    await bot.session.close()
                except:
                    pass

async def start_telegram_bot():
    """Запуск Telegram бота с бесконечным перезапуском"""
    global scheduler
    
    try:
        # Планировщик для самопинга
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            lambda: logger.info("🔄 Bot heartbeat"),
            trigger=IntervalTrigger(minutes=10),
            id='heartbeat'
        )
        scheduler.start()
        
        logger.info("🔄 Keep-alive активирован (10 минут)")
        
        # Запускаем бота с автоматическим перезапуском
        await restart_bot()
        
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")
        # Не выходим, а пытаемся перезапустить
        await asyncio.sleep(5)
        await start_telegram_bot()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager для управления жизненным циклом"""
    # Startup
    logger.info("🚀 Starting FoodBot application...")
    
    # ИГНОРИРУЕМ сигналы остановки!
    signal.signal(signal.SIGTERM, ignore_signal)
    signal.signal(signal.SIGINT, ignore_signal)
    signal.signal(signal.SIGQUIT, ignore_signal)
    
    # Запускаем бота в фоновой задаче
    bot_task = asyncio.create_task(start_telegram_bot())
    
    yield
    
    # Shutdown (только при явном завершении)
    logger.info("🛑 Запрос на завершение работы...")
    global is_running
    is_running = False
    
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
        logger.info("✅ Bot task cancelled")

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
    bot_status = "running" if bot else "starting"
    return {
        "message": "🤖 FoodBot is running!",
        "status": "active", 
        "bot": bot_status,
        "service": "food-school-bot"
    }

@app.get("/health")
async def health_check():
    """Health check для Render"""
    return {
        "status": "healthy",
        "bot": "running" if bot else "restarting",
        "ignore_shutdown": True
    }

@app.get("/ping")
async def ping():
    """Простой ping-эндпоинт"""
    return {"message": "pong"}

@app.get("/force-restart")
async def force_restart():
    """Принудительный перезапуск бота (для дебага)"""
    global bot
    if bot:
        await bot.session.close()
    return {"message": "Restart initiated"}

def main():
    """Основная функция запуска"""
    port = int(os.environ.get("PORT", 10000))
    
    logger.info(f"🌐 Starting server on port {port}")
    logger.warning("🚨 ВКЛЮЧЕН РЕЖИМ ИГНОРИРОВАНИЯ SIGTERM! Бот будет работать вечно!")
    
    try:
        uvicorn.run(
            app,
            host="0.0.0.0", 
            port=port,
            reload=False,
            access_log=True
        )
    except Exception as e:
        logger.error(f"💥 Ошибка сервера: {e}")
        # Перезапускаем сервер
        logger.info("🔄 Перезапуск сервера через 30 секунд...")
        os.execv(sys.executable, ['python'] + sys.argv)

if __name__ == "__main__":
    main()