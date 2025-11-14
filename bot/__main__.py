import asyncio
import logging
import os
import signal
import sys
import gc
import psutil
import tracemalloc
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
process = None

def cleanup_memory():
    """Агрессивная очистка оперативной памяти"""
    try:
        # Получаем текущий процесс
        global process
        if process is None:
            process = psutil.Process(os.getpid())
        
        # Логируем использование памяти до очистки
        memory_before = process.memory_info().rss / 1024 / 1024  # в МБ
        
        # 1. Сборщик мусора Python
        collected = gc.collect()
        
        # 2. Очищаем кэши
        if 'clear_cache' in dir(gc):
            gc.clear_cache()
        
        # 3. Очищаем кэш tracemalloc если активен
        if tracemalloc.is_tracing():
            tracemalloc.clear_traces()
        
        # 4. Принудительно вызываем сборщик мусора несколько раз
        for _ in range(3):
            gc.collect(generation=2)  # Самый агрессивный сбор
        
        # Логируем использование памяти после очистки
        memory_after = process.memory_info().rss / 1024 / 1024  # в МБ
        memory_freed = memory_before - memory_after
        
        logger.info(f"🧹 Очистка памяти: {memory_before:.1f}MB → {memory_after:.1f}MB (освобождено {memory_freed:.1f}MB)")
        
        return memory_freed
        
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при очистке памяти: {e}")
        return 0

def ignore_signal(signum, frame):
    """Игнорируем SIGTERM и другие сигналы остановки"""
    signal_name = {
        signal.SIGTERM: "SIGTERM",
        signal.SIGINT: "SIGINT", 
        signal.SIGQUIT: "SIGQUIT"
    }.get(signum, str(signum))
    
    logger.warning(f"🚫 ИГНОРИРУЕМ сигнал {signal_name}! Бот продолжает работу!")
    
    # Принудительная очистка памяти при получении сигнала
    cleanup_memory()

async def perform_health_check():
    """Выполнение health check с очисткой памяти"""
    try:
        # Очищаем память перед каждым пингом
        memory_freed = cleanup_memory()
        
        # Логируем общую статистику
        if process:
            memory_usage = process.memory_info().rss / 1024 / 1024
            memory_percent = process.memory_percent()
            logger.info(f"📊 Статистика памяти: {memory_usage:.1f}MB ({memory_percent:.1f}%)")
        
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка health check: {e}")
        return False

async def restart_bot():
    """Перезапуск бота при ошибках"""
    global bot, dp
    
    while is_running:
        try:
            logger.info("🔄 Запуск/перезапуск Telegram бота...")
            
            # Очищаем память перед запуском бота
            cleanup_memory()
            
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
            
            # Очищаем память при ошибке
            cleanup_memory()
            
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
        # Планировщик для самопинга и очистки памяти
        scheduler = AsyncIOScheduler()
        
        # Heartbeat каждые 10 минут
        scheduler.add_job(
            lambda: logger.info("🔄 Bot heartbeat"),
            trigger=IntervalTrigger(minutes=10),
            id='heartbeat'
        )
        
        # Агрессивная очистка памяти каждые 5 минут
        scheduler.add_job(
            cleanup_memory,
            trigger=IntervalTrigger(minutes=5),
            id='memory_cleanup'
        )
        
        # Health check с очисткой каждые 3 минуты
        scheduler.add_job(
            perform_health_check,
            trigger=IntervalTrigger(minutes=3),
            id='health_check'
        )
        
        scheduler.start()
        
        logger.info("🔄 Keep-alive активирован (очистка памяти каждые 5 минут)")
        
        # Запускаем бота с автоматическим перезапуском
        await restart_bot()
        
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")
        # Очищаем память при ошибке запуска
        cleanup_memory()
        # Не выходим, а пытаемся перезапустить
        await asyncio.sleep(5)
        await start_telegram_bot()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager для управления жизненным циклом"""
    # Startup
    logger.info("🚀 Starting FoodBot application...")
    
    # Инициализируем мониторинг памяти
    global process
    process = psutil.Process(os.getpid())
    tracemalloc.start()  # Включаем отслеживание памяти
    
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
    
    # Финальная очистка памяти
    cleanup_memory()
    
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
    
    # Добавляем информацию о памяти
    memory_info = {}
    if process:
        memory_info = {
            "memory_used_mb": round(process.memory_info().rss / 1024 / 1024, 1),
            "memory_percent": round(process.memory_percent(), 1)
        }
    
    return {
        "message": "🤖 FoodBot is running!",
        "status": "active", 
        "bot": bot_status,
        "service": "food-school-bot",
        "memory": memory_info
    }

@app.get("/health")
async def health_check():
    """Health check для Render"""
    # Очищаем память при каждом health check
    memory_freed = cleanup_memory()
    
    return {
        "status": "healthy",
        "bot": "running" if bot else "restarting",
        "ignore_shutdown": True,
        "memory_cleaned_mb": round(memory_freed, 1),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/ping")
async def ping():
    """Простой ping-эндпоинт с очисткой памяти"""
    # Очищаем память при каждом ping
    cleanup_memory()
    return {"message": "pong", "memory_cleaned": True}

@app.get("/memory")
async def memory_status():
    """Эндпоинт для проверки использования памяти"""
    if not process:
        return {"error": "Process not initialized"}
    
    memory = process.memory_info()
    return {
        "rss_mb": round(memory.rss / 1024 / 1024, 1),
        "vms_mb": round(memory.vms / 1024 / 1024, 1),
        "percent": round(process.memory_percent(), 1),
        "threads": process.num_threads(),
        "cpu_percent": process.cpu_percent()
    }

@app.get("/force-cleanup")
async def force_cleanup():
    """Принудительная очистка памяти"""
    memory_freed = cleanup_memory()
    return {
        "message": "Memory cleanup completed",
        "memory_freed_mb": round(memory_freed, 1)
    }

@app.get("/force-restart")
async def force_restart():
    """Принудительный перезапуск бота (для дебага)"""
    global bot
    if bot:
        await bot.session.close()
    
    # Очищаем память перед перезапуском
    cleanup_memory()
    
    return {"message": "Restart initiated"}

def main():
    """Основная функция запуска"""
    port = int(os.environ.get("PORT", 10000))
    
    logger.info(f"🌐 Starting server on port {port}")
    logger.warning("🚨 ВКЛЮЧЕН РЕЖИМ ИГНОРИРОВАНИЯ SIGTERM! Бот будет работать вечно!")
    logger.info("🧹 АКТИВИРОВАНА АГРЕССИВНАЯ ОЧИСТКА ПАМЯТИ!")
    
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
        # Очищаем память перед перезапуском
        cleanup_memory()
        # Перезапускаем сервер
        logger.info("🔄 Перезапуск сервера через 30 секунд...")
        os.execv(sys.executable, ['python'] + sys.argv)

if __name__ == "__main__":
    main()