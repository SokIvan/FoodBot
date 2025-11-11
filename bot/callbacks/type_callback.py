from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from aiogram import types
from functions.yandex_disk import yandex_disk
import re

import logging

router = Router()
logger = logging.getLogger(__name__)

class MealRating(StatesGroup):
    waiting_for_dish_rating = State()
    waiting_for_menu_rating = State()
    waiting_for_comment = State()

# Хранилище для временных данных
user_ratings = {}

@router.callback_query(F.data.startswith("type_"))
async def process_meal_type(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора типа приема пищи"""
    

    
    
    
    meal_type_map = {
        "type_zavtrak": "завтрак",
        "type_obed": "обед", 
        "type_poldnik": "полдник"
    }
    
    meal_type = meal_type_map.get(callback.data)
    if not meal_type:
        await callback.answer("Неизвестный тип меню")
        return
    
    # Получаем изображения для выбранного типа
    images = await yandex_disk.get_meal_images(meal_type)
    
    if not images:
        await callback.message.edit_text(
            f"❌ Фотографии для {meal_type} не найдены",
            reply_markup=None
        )
        return
    
    # Сохраняем данные в состоянии
    await state.update_data(
        meal_type=meal_type,
        images=images,
        current_image_index=0,
        dish_ratings=[],
        invalid_input_count=0,
        last_message_id=callback.message.message_id  # Сохраняем ID сообщения для редактирования
    )
    # Показываем первую фотку (редактируем исходное сообщение)
    await show_next_image(callback.message, state)
    
    # Переходим в состояние ожидания оценки блюда
    await state.set_state(MealRating.waiting_for_dish_rating)
    await callback.answer()

async def show_next_image(message: types.Message, state: FSMContext):
    """Показывает следующее изображение и просит оценку (редактирует сообщение)"""
    data = await state.get_data()
    images = data['images']
    current_index = data['current_image_index']
    last_message_id = data.get('last_message_id', message.message_id)
    
    if current_index >= len(images):
        # Все фото закончились, переходим к оценке меню
        await ask_menu_rating(message, state)
        return
    
    current_image = images[current_index]
    
    try:
        # Редактируем сообщение с новой фоткой
        await message.bot.edit_message_media(
            chat_id=message.chat.id,
            message_id=last_message_id,
            media=types.InputMediaPhoto(
                media=current_image['download_url'],
                caption=f"📸 Блюдо {current_index + 1} из {len(images)}\n"
                        f"📝 Введите оценку от 1 до 10:"
            )
        )
    except Exception as e:
        # Если не удалось отредактировать (например, фото не меняется), отправляем новое
        new_message = await message.answer_photo(
            photo=current_image['download_url'],
            caption=f"📸 Блюдо {current_index + 1} из {len(images)}\n"
                    f"📝 Введите оценку от 1 до 10:"
        )
        await state.update_data(last_message_id=new_message.message_id)

async def ask_menu_rating(message: types.Message, state: FSMContext):
    """Запрашивает общую оценку меню (редактирует сообщение)"""
    data = await state.get_data()
    dish_ratings = data['dish_ratings']
    last_message_id = data.get('last_message_id', message.message_id)
    
    # Считаем среднюю оценку блюд
    avg_rating = sum(dish_ratings) / len(dish_ratings) if dish_ratings else 0
    
    try:
        # Редактируем сообщение для запроса оценки меню
        # Вместо edit_message_caption используем edit_message_text
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=last_message_id,
            text=f"🍽 Вы оценили {len(dish_ratings)} блюд(а)\n"
                f"📊 Средняя оценка блюд: {avg_rating:.1f}\n\n"
                f"📝 Теперь оцените меню в целом от 1 до 10:"
        )
    except Exception as e:
        # Если не удалось отредактировать, отправляем новое сообщение
        new_message = await message.answer(
            f"🍽 Вы оценили {len(dish_ratings)} блюд(а)\n"
            f"📊 Средняя оценка блюд: {avg_rating:.1f}\n\n"
            f"📝 Теперь оцените меню в целом от 1 до 10:"
        )
        await state.update_data(last_message_id=new_message.message_id)
    
    await state.set_state(MealRating.waiting_for_menu_rating)

@router.message(MealRating.waiting_for_dish_rating)
async def process_dish_rating(message: Message, state: FSMContext):
    """Обработка оценки блюда"""
    data = await state.get_data()
    invalid_input_count = data.get('invalid_input_count', 0)
    last_message_id = data.get('last_message_id')
    images = data['images']
    current_index = data['current_image_index']
    
    # Удаляем сообщение с оценкой пользователя
    await message.delete()
    
    # Проверяем валидность ввода
    if not re.match(r'^([1-9]|10)$', message.text.strip()):
        invalid_input_count += 1
        
        if invalid_input_count >= 3:
            await message.bot.edit_message_caption(
                chat_id=message.chat.id,
                message_id=last_message_id,
                caption="❌ Слишком много неверных попыток. Оценка отменена."
            )
            await state.clear()
            return
        
        await state.update_data(invalid_input_count=invalid_input_count)
        
        # Обновляем текущее фото с сообщением об ошибке
        try:
            current_image = images[current_index]
            await message.bot.edit_message_caption(
                chat_id=message.chat.id,
                message_id=last_message_id,
                caption=f"❌ Неверный формат оценки!\n"
                       f"📸 Блюдо {current_index + 1} из {len(images)}\n"
                       f"📝 Введите оценку от 1 до 10 (попытка {invalid_input_count + 1}/3):"
            )
        except Exception as e:
            # Если редактирование не удалось, создаем новое сообщение
            new_message = await message.answer(
                f"❌ Неверный формат оценки!\n"
                f"📸 Блюдо {current_index + 1} из {len(images)}\n"
                f"📝 Введите оценку от 1 до 10 (попытка {invalid_input_count + 1}/3):"
            )
            await state.update_data(last_message_id=new_message.message_id)
        return
    
    # Валидная оценка
    rating = int(message.text.strip())
    
    # Сохраняем оценку
    dish_ratings = data['dish_ratings']
    dish_ratings.append(rating)
    
    # Сбрасываем счетчик невалидных вводов и переходим к следующему изображению
    await state.update_data(
        dish_ratings=dish_ratings,
        invalid_input_count=0,
        current_image_index=current_index + 1
    )
    
    # Показываем следующее изображение
    await show_next_image(message, state)

@router.message(MealRating.waiting_for_menu_rating)
async def process_menu_rating(message: Message, state: FSMContext):
    """Обработка общей оценки меню"""
    data = await state.get_data()
    last_message_id = data.get('last_message_id')
    
    # Удаляем сообщение с оценкой пользователя
    await message.delete()
    
    # Проверяем валидность ввода
    if not re.match(r'^([1-9]|10)$', message.text.strip()):
        try:
            await message.bot.edit_message_caption(
                chat_id=message.chat.id,
                message_id=last_message_id,
                caption="❌ Неверный формат оценки! Введите число от 1 до 10:"
            )
        except Exception as e:
            new_message = await message.answer("❌ Неверный формат оценки! Введите число от 1 до 10:")
            await state.update_data(last_message_id=new_message.message_id)
        return
    
    menu_rating = int(message.text.strip())
    
    # Сохраняем оценку меню
    await state.update_data(menu_rating=menu_rating)
    
    # Запрашиваем комментарий (редактируем сообщение)
    try:
        await message.bot.edit_message_caption(
            chat_id=message.chat.id,
            message_id=last_message_id,
            caption="💬 Отлично! Теперь напишите ваш комментарий к меню "
                   "(или отправьте '-' если не хотите оставлять комментарий):"
        )
    except Exception as e:
        new_message = await message.answer(
            "💬 Отлично! Теперь напишите ваш комментарий к меню "
            "(или отправьте '-' если не хотите оставлять комментарий):"
        )
        await state.update_data(last_message_id=new_message.message_id)
    
    await state.set_state(MealRating.waiting_for_comment)

@router.message(MealRating.waiting_for_comment)
async def process_comment(message: Message, state: FSMContext):
    """Обработка комментария"""
    comment = message.text.strip()
    data = await state.get_data()
    last_message_id = data.get('last_message_id')
    
    # Получаем все данные
    meal_type = data['meal_type']
    dish_ratings = data['dish_ratings']
    menu_rating = data['menu_rating']
    
    # Сохраняем результаты
    user_id = message.from_user.id
    user_ratings[user_id] = {
        'meal_type': meal_type,
        'dish_ratings': dish_ratings,
        'menu_rating': menu_rating,
        'comment': comment if comment != '-' else None,
        'timestamp': message.date.isoformat()
    }
    
    # Формируем итоговое сообщение
    avg_dish_rating = sum(dish_ratings) / len(dish_ratings) if dish_ratings else 0
    
    result_text = (
        f"✅ Спасибо за вашу оценку!\n\n"
        f"🍽 Тип меню: {meal_type.capitalize()}\n"
        f"📊 Оценка блюд: {len(dish_ratings)} шт., средняя: {avg_dish_rating:.1f}\n"
        f"⭐ Общая оценка меню: {menu_rating}/10\n"
    )
    
    if comment and comment != '-':
        result_text += f"💬 Комментарий: {comment}\n"
    
    result_text += f"\n📈 Данные сохранены для анализа"
    
    # Редактируем последнее сообщение с результатами
    try:
        # Вместо edit_message_caption используем edit_message_text
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=last_message_id,
            text=result_text
        )
    except Exception as e:
        # Если не удалось отредактировать, отправляем новое сообщение
        await message.answer(result_text)
    
    # Удаляем сообщение с комментарием пользователя
    await message.delete()
    
    # Очищаем состояние
    await state.clear()

# Функции для работы с данными (остаются без изменений)
def get_user_ratings(user_id: int):
    """Получить оценки пользователя"""
    return user_ratings.get(user_id)

def cleanup_old_ratings():
    """Очистка старых оценок"""
    global user_ratings
    user_ratings = {}