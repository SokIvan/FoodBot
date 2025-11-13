from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from keyboards.type_keyboard import get_rating_keyboard,get_comment_keyboard
from aiogram import types
from functions.yandex_disk import yandex_disk
from database.db_supabase import supabase_client
import re

import logging

router = Router()
logger = logging.getLogger(__name__)
global_user_id = None


class MealRating(StatesGroup):
    waiting_for_dish_rating = State()
    waiting_for_menu_rating = State()
    waiting_for_comment = State()

# Хранилище для временных данных
user_ratings = {}
# Защита от множественных нажатий
processing_ratings = set()

async def cleanup_chat(message: types.Message, state: FSMContext):
    """Очистка чата - удаляет последние сообщения бота"""
    data = await state.get_data()
    last_message_id = data.get('last_message_id')
    
    try:
        # Удаляем последнее сообщение бота (основное сообщение с оценками)
        if last_message_id:
            try:
                await message.bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=last_message_id
                )
            except Exception as e:
                logger.warning(f"Не удалось удалить последнее сообщение бота: {e}")
                
    except Exception as e:
        logger.error(f"Ошибка при очистке чата: {e}")

async def edit_or_send_message(message: types.Message, state: FSMContext, 
                              content: str, photo_url: str = None, 
                              keyboard = None, parse_mode: str = None):
    """Универсальная функция для редактирования/отправки сообщения"""
    data = await state.get_data()
    last_message_id = data.get('last_message_id')
    
    try:
        if photo_url:
            # Если есть фото - отправляем/редактируем медиа
            if last_message_id:
                await message.bot.edit_message_media(
                    chat_id=message.chat.id,
                    message_id=last_message_id,
                    media=types.InputMediaPhoto(
                        media=photo_url,
                        caption=content,
                        parse_mode=parse_mode
                    ),
                    reply_markup=keyboard
                )
            else:
                new_message = await message.answer_photo(
                    photo=photo_url,
                    caption=content,
                    reply_markup=keyboard,
                    parse_mode=parse_mode
                )
                await state.update_data(last_message_id=new_message.message_id)
        else:
            # Если нет фото - отправляем/редактируем текст
            if last_message_id:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=last_message_id,
                    text=content,
                    reply_markup=keyboard,
                    parse_mode=parse_mode
                )
            else:
                new_message = await message.answer(
                    text=content,
                    reply_markup=keyboard,
                    parse_mode=parse_mode
                )
                await state.update_data(last_message_id=new_message.message_id)
                
    except Exception as e:
        # Если редактирование не удалось, отправляем новое сообщение
        if photo_url:
            new_message = await message.answer_photo(
                photo=photo_url,
                caption=content,
                reply_markup=keyboard,
                parse_mode=parse_mode
            )
        else:
            new_message = await message.answer(
                text=content,
                reply_markup=keyboard,
                parse_mode=parse_mode
            )
        await state.update_data(last_message_id=new_message.message_id)

async def remove_photo_from_message(message: types.Message, state: FSMContext, 
                                   content: str, keyboard = None):
    """Специальная функция для удаления фото из сообщения (переход к тексту)"""
    data = await state.get_data()
    last_message_id = data.get('last_message_id')
    
    if not last_message_id:
        # Если нет предыдущего сообщения, просто отправляем текст
        new_message = await message.answer(
            text=content,
            reply_markup=keyboard
        )
        await state.update_data(last_message_id=new_message.message_id)
        return
    
    try:
        # Пытаемся отредактировать медиа-сообщение в текстовое
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=last_message_id,
            text=content,
            reply_markup=keyboard
        )
    except Exception as e:
        # Если не получилось (например, нельзя сменить тип контента), 
        # удаляем старое сообщение и создаем новое
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=last_message_id
            )
        except:
            pass
        
        new_message = await message.answer(
            text=content,
            reply_markup=keyboard
        )
        await state.update_data(last_message_id=new_message.message_id)

@router.callback_query(F.data.startswith("type_"))
async def process_meal_type(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора типа приема пищи"""
    
    # Проверяем, не занят ли пользователь другой оценкой
    current_state = await state.get_state()
    if current_state is not None:
        await callback.answer("⏳ Вы уже начали оценку меню. Завершите текущую оценку прежде чем начинать новую.", show_alert=True)
        return
    
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
        dish_ratings=[],  # Теперь это будет список словарей
        last_message_id=callback.message.message_id
    )
    
    # Показываем первую фотку с кнопками оценок
    await show_next_image(callback.message, state)
    
    # Переходим в состояние ожидания оценки блюда
    await state.set_state(MealRating.waiting_for_dish_rating)
    await callback.answer()

async def show_next_image(message: types.Message, state: FSMContext):
    """Показывает следующее изображение с кнопками оценок"""
    data = await state.get_data()
    images = data['images']
    current_index = data['current_image_index']
    
    if current_index >= len(images):
        # Все фото закончились, переходим к оценке меню
        await ask_menu_rating(message, state)
        return
    
    current_image = images[current_index]
    
    caption = (f"📸 Блюдо {current_image['name']} {current_index + 1} из {len(images)}\n"
               f"📝 Оцените блюдо:")
    
    await edit_or_send_message(
        message=message,
        state=state,
        content=caption,
        photo_url=current_image['download_url'],
        keyboard=get_rating_keyboard()
    )

async def ask_menu_rating(message: types.Message, state: FSMContext):
    """Запрашивает общую оценку меню"""
    data = await state.get_data()
    dish_ratings = data['dish_ratings']
    
    # Считаем среднюю оценку блюд
    if dish_ratings:
        avg_rating = sum(dish['mark'] for dish in dish_ratings) / len(dish_ratings)
    else:
        avg_rating = 0
    
    caption = (f"🍽 Вы оценили {len(dish_ratings)} блюд(а)\n"
              f"📊 Средняя оценка блюд: {avg_rating:.1f}\n\n"
              f"📝 Теперь оцените меню в целом:")
    
    # Используем специальную функцию для удаления фото
    await remove_photo_from_message(
        message=message,
        state=state,
        content=caption,
        keyboard=get_rating_keyboard()
    )
    
    await state.set_state(MealRating.waiting_for_menu_rating)

@router.callback_query(F.data.startswith("rating_"))
async def process_rating(callback: CallbackQuery, state: FSMContext):
    """Обработка оценки через кнопки"""
    current_state = await state.get_state()
    
    if not current_state:
        await callback.answer("Сессия завершена")
        return
    
    # Защита от множественных нажатий
    global global_user_id
    global_user_id = callback.from_user.id
    user_id = callback.from_user.id
    rating_key = f"{user_id}_{current_state}"
    
    if rating_key in processing_ratings:
        await callback.answer("⏳ Обрабатывается предыдущая оценка...")
        return
    
    processing_ratings.add(rating_key)
    
    try:
        rating = int(callback.data.split("_")[1])
    except (ValueError, IndexError):
        processing_ratings.discard(rating_key)
        await callback.answer("Ошибка обработки оценки")
        return
    
    # НЕ удаляем сообщение, только отвечаем на callback
    await callback.answer(f"Оценка {rating} принята!")
    
    try:
        if current_state == MealRating.waiting_for_dish_rating.state:
            # Оценка блюда
            data = await state.get_data()
            images = data['images']
            current_index = data['current_image_index']
            
            # Проверяем, что текущий индекс в пределах допустимого
            if current_index >= len(images):
                logger.warning(f"Текущий индекс {current_index} превышает количество изображений {len(images)}")
                return
            
            current_image = images[current_index]
            dish_ratings = data['dish_ratings']
            
            # Добавляем оценку в виде словаря
            dish_rating = {
                "name": current_image['name'],
                "mark": rating
            }
            dish_ratings.append(dish_rating)
            
            await state.update_data(
                dish_ratings=dish_ratings,
                current_image_index=current_index + 1
            )
            
            # Показываем следующее изображение
            await show_next_image(callback.message, state)
            
        elif current_state == MealRating.waiting_for_menu_rating.state:
            # Оценка меню
            await state.update_data(menu_rating=rating)
            
            # Запрашиваем комментарий
            caption = ("💬 Отлично! Теперь напишите ваш комментарий к меню\n"
                      "Или нажмите кнопку ниже чтобы пропустить:")
            
            await edit_or_send_message(
                message=callback.message,
                state=state,
                content=caption,
                keyboard=get_comment_keyboard()
            )
            
            await state.set_state(MealRating.waiting_for_comment)
    
    except Exception as e:
        logger.error(f"Ошибка при обработке оценки: {e}")
        await callback.answer("❌ Произошла ошибка при обработке оценки")
    
    finally:
        # Всегда снимаем блокировку
        processing_ratings.discard(rating_key)

@router.callback_query(F.data == "no_comment")
async def process_no_comment(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки 'Без комментариев'"""
    # Защита от множественных нажатий
    global global_user_id
    global_user_id = callback.from_user.id
    user_id = callback.from_user.id
    rating_key = f"{user_id}_no_comment"
    
    if rating_key in processing_ratings:
        await callback.answer("⏳ Обрабатывается...")
        return
    
    processing_ratings.add(rating_key)
    
    try:
        # НЕ удаляем сообщение, только отвечаем
        await callback.answer("Пропущено")
        await process_final_results(callback.message, state, comment=None)
    finally:
        processing_ratings.discard(rating_key)

@router.message(MealRating.waiting_for_comment)
async def process_comment_input(message: Message, state: FSMContext):
    """Обработка текстового комментария"""
    comment = message.text.strip()
    global global_user_id
    global_user_id = message.from_user.id 
    # Удаляем только сообщение с комментарием пользователя
    await message.delete()
    
    # Обрабатываем финальные результаты
    await process_final_results(message, state, comment)

async def process_final_results(message: types.Message, state: FSMContext, comment: str = None):
    """Обработка и вывод финальных результатов"""
    data = await state.get_data()
    
    # Получаем все данные
    meal_type = data['meal_type']
    dish_ratings = data['dish_ratings']
    menu_rating = data.get('menu_rating', 0)
    
    # === ДОБАВЛЯЕМ РАБОТУ С БАЗОЙ ДАННЫХ ===
    
    user_id = global_user_id
    user = await message.bot.get_chat(user_id)
    user_fname = user.first_name
    user_lname = user.last_name
    user_username = user.username
    current_date = message.date.date().isoformat()
    
    # Безопасный комментарий для food_menu (если None - пустая строка)
    safe_comment = comment if comment and comment != '-' else ""
    
    try:
        # 1. Проверяем и добавляем пользователя если нет
        if not await supabase_client.user_exists(user_id):
            user_data = {
                "id": user_id,
                "Username": user_username or f"user_{user_id}",
                "Name": f"{user_fname or ''} {user_lname or ''}".strip()
            }
            await supabase_client.set_user(user_data)
            logger.info(f"Добавлен новый пользователь: {user_id}")
        
        # 2. Сохраняем оценки блюд в таблицу food (БЕЗ КОММЕНТАРИЯ)
        for dish in dish_ratings:
            food_data = {
                "date": current_date,
                "name": dish['name'],
                "mark": dish['mark'],
                "user_id": user_id
                # НЕТ КОЛОНКИ comment - убрали из таблицы food
            }
            await supabase_client.add_food_review(food_data)
        
        # 3. Сохраняем оценку меню в таблицу food_menu (С КОММЕНТАРИЕМ)
        menu_data = {
            "date": current_date,
            "type": meal_type,
            "name": f"Меню {meal_type}",
            "mark": menu_rating,
            "comment": safe_comment,  # комментарий остался в food_menu
            "user_id": user_id
        }
        await supabase_client.add_food_menu_review(menu_data)
        
        logger.info(f"Данные успешно сохранены в БД для пользователя {user_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении в БД: {e}")
    # === КОНЕЦ РАБОТЫ С БАЗОЙ ДАННЫХ ===
    
    # Сохраняем результаты в локальное хранилище (для обратной совместимости)
    user_ratings[user_id] = {
        'meal_type': meal_type,
        'dish_ratings': dish_ratings,
        'menu_rating': menu_rating,
        'comment': comment if comment and comment != '-' else None,
        'timestamp': message.date.isoformat()
    }
    
    # Формируем итоговое сообщение
    if dish_ratings:
        avg_dish_rating = sum(dish['mark'] for dish in dish_ratings) / len(dish_ratings)
        dishes_details = "\n".join([f"  • {dish['name']}: {dish['mark']}/5" for dish in dish_ratings])
    else:
        avg_dish_rating = 0
        dishes_details = "  • Нет оценок"
    
    result_text = (
        f"✅ Спасибо за вашу оценку!\n\n"
        f"🍽 Тип меню: {meal_type.capitalize()}\n"
        f"📊 Оценка блюд ({len(dish_ratings)} шт.):\n{dishes_details}\n"
        f"📈 Средняя оценка блюд: {avg_dish_rating:.1f}/5.0\n"
        f"⭐ Общая оценка меню: {menu_rating}/5\n"
    )
    
    if comment and comment != '-':
        result_text += f"💬 Комментарий: {comment}\n"
    
    result_text += f"\n📊 Данные сохранены для анализа"
    
    # Очищаем чат перед выводом статистики
    await cleanup_chat(message, state)
    
    # Выводим финальное сообщение без клавиатуры
    await message.answer(result_text)
    
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