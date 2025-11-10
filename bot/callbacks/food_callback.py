from aiogram import Router, types
from aiogram.types import InputMediaPhoto
from functions.yandex_disk import yandex_disk
from keyboards.food_keyboard import create_dish_keyboard

router = Router()

@router.callback_query(lambda c: c.data.startswith('dish:'))
async def handle_dish_callback(callback: types.CallbackQuery):
    """Обработчик смены блюд"""
    filename = callback.data.replace('dish:', '')
    
    # Получаем текущий набор изображений
    images = await yandex_disk.get_today_images() or await yandex_disk.get_latest_images()
    
    if not images:
        await callback.answer("❌ Блюда временно недоступны!", show_alert=True)
        return
    
    selected_dish = next((img for img in images if img["full_name"] == filename), None)
    
    if not selected_dish:
        await callback.answer("❌ Блюдо не найдено!", show_alert=True)
        return
    
    keyboard = await create_dish_keyboard(images, selected_dish["full_name"])
    
    # Добавляем информацию о дате
    date_info = f" ({selected_dish.get('date', '')})" if selected_dish.get('date') else ""
    caption = f"🍴 **Выберите блюдо**{date_info}"
    
    try:
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=selected_dish["download_url"],
                caption=caption,
                parse_mode="Markdown"
            ),
            reply_markup=keyboard
        )
    except Exception as e:
        try:
            await callback.message.edit_reply_markup(reply_markup=keyboard)
            await callback.message.edit_caption(caption=caption, parse_mode="Markdown")
        except Exception:
            await callback.answer("⚠️ Обновите сообщение!")
    
    await callback.answer()