from aiogram import Router, types
from aiogram.filters import Command
from functions.yandex_disk import yandex_disk
from keyboards.food_keyboard import create_dish_keyboard
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command("start"))
async def start_command(message: types.Message):
    """Обработчик команды /start"""
    try:
        # Пытаемся получить сегодняшние изображения
        images = await yandex_disk.get_today_images()
        
        # Если сегодняшних нет, берем самые свежие
        if not images:
            images = await yandex_disk.get_latest_images()
            if images:
                date_info = f" ({images[0].get('date', '')})"
            else:
                date_info = ""
        else:
            date_info = " (сегодня)"
        
        if not images:
            await message.answer("🍽️ Блюда временно недоступны!")
            return
        
        # Первое блюдо для превью
        first_dish = images[0]
        keyboard = await create_dish_keyboard(images, first_dish["full_name"])
        
        caption = f"🍴 **Выберите блюдо**{date_info}"
        
        try:
            await message.answer_photo(
                photo=first_dish["download_url"],
                caption=caption,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки фото: {e}")
            await message.answer(
                text=caption,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Ошибка в команде /start: {e}")
        await message.answer("❌ Произошла ошибка при загрузке меню")