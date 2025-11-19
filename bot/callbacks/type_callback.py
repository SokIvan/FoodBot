from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

from functions.yandex_disk import yandex_disk
from database.db_supabase import supabase_client
from keyboards.survey_keyboards import (
    get_school_confirmation_keyboard,
    get_emoji_rating_keyboard,
    get_comment_skip_keyboard,
    get_meal_comment_keyboard
)

router = Router()
logger = logging.getLogger(__name__)

class SurveyStates(StatesGroup):
    waiting_for_school_confirmation = State()
    waiting_for_user_info = State()
    waiting_for_overall_satisfaction = State()
    waiting_for_overall_comment = State()
    waiting_for_meal_rating = State()
    waiting_for_meal_comment = State()


# Глобальная переменная для хранения user_id
current_user_id = None

# Хранилище для ID сообщений которые нужно удалять
message_ids_to_delete = {}

@router.callback_query(F.data.startswith("school_"))
async def process_school_confirmation(callback: CallbackQuery, state: FSMContext):
    """Обработка подтверждения питания в школе"""
    global current_user_id
    
    # Сохраняем ID пользователя
    current_user_id = callback.from_user.id
    logger.info(f"👤 Сохранен user_id: {current_user_id}")
    
    eats_at_school = callback.data == "school_yes"
    
    # Удаляем сообщение с первым вопросом
    await callback.message.delete()
    
    if not eats_at_school:
        await callback.message.answer(
            "❌ *К сожалению, этот бот предназначен только для учащихся, "
            "которые питаются в столовой школы №64.*\n\n"
            "Если это ошибка, начните заново с команды /mark",
            parse_mode="Markdown"
        )
        await state.clear()
        return
    
    # Сохраняем в состоянии
    await state.update_data(eats_at_school=True)
    
    # Переходим к запросу ФИО и класса
    new_message = await callback.message.answer(
        "📝 *Отлично! Теперь расскажите о себе:*\n\n"
        "Напишите ваши *полные Фамилию и Имя* и *класс* в формате:\n"
        "`Иванов Иван 5А`\n\n"
        "*Пример:* Иванова Мария 8Б",
        parse_mode="Markdown"
    )
    
    await state.update_data(user_info_message_id=new_message.message_id)
    await state.set_state(SurveyStates.waiting_for_user_info)
    await callback.answer()

@router.message(SurveyStates.waiting_for_user_info)
async def process_user_info(message: Message, state: FSMContext):
    """Обработка ФИО и класса пользователя"""
    user_input = message.text.strip()
    
    # Простая валидация ввода
    if len(user_input.split()) < 3:
        await message.answer(
            "❌ *Пожалуйста, введите данные в правильном формате:*\n"
            "`Фамилия Имя Класс`\n\n"
            "*Пример:* Иванов Иван 5А",
            parse_mode="Markdown"
        )
        return
    
    # Удаляем сообщение с пользовательским вводом
    await message.delete()
    
    # Извлекаем данные
    parts = user_input.split()
    class_part = parts[-1]
    name_parts = parts[:-1]
    
    full_name = " ".join(name_parts)
    class_name = class_part
    
    # Сохраняем данные
    await state.update_data(
        full_name=full_name,
        class_name=class_name
    )
    
    # Создаем/обновляем пользователя в БД
    try:
        user_data = {
            "telegram_id": message.from_user.id,
            "full_name": full_name,
            "class": class_name,
            "has_profile": True
        }
        
        if not await supabase_client.user_exists(message.from_user.id):
            await supabase_client.create_user(user_data)
            logger.info(f"✅ Создан новый пользователь: {message.from_user.id}")
        else:
            await supabase_client.update_user_info(
                message.from_user.id, 
                full_name, 
                class_name
            )
            logger.info(f"✅ Обновлен пользователь: {message.from_user.id}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения пользователя: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте снова.")
        return
    
    # Удаляем предыдущее сообщение с запросом ФИО
    data = await state.get_data()
    if 'user_info_message_id' in data:
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=data['user_info_message_id']
            )
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")
    
    # Переходим к общей оценке
    overall_message = await message.answer(
        "🍽️ *Оцените, пожалуйста, насколько вам нравится питание в столовой в целом?*",
        reply_markup=get_emoji_rating_keyboard("overall"),
        parse_mode="Markdown"
    )
    
    await state.update_data(overall_message_id=overall_message.message_id)
    await state.set_state(SurveyStates.waiting_for_overall_satisfaction)

@router.callback_query(F.data.startswith("rating_overall_"))
async def process_overall_rating(callback: CallbackQuery, state: FSMContext):
    """Обработка общей оценки питания"""
    try:
        rating = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка обработки оценки")
        return
    
    # Удаляем сообщение с общей оценкой
    await callback.message.delete()
    
    await state.update_data(overall_satisfaction=rating)
    
    if rating <= 3:
        # Если низкая оценка - запрашиваем комментарий
        comment_message = await callback.message.answer(
            "💬 *Пожалуйста, напишите, что именно вам не нравится в питании?*\n\n"
            "Ваши комментарии помогут улучшить ситуацию!",
            reply_markup=get_comment_skip_keyboard("overall"),
            parse_mode="Markdown"
        )
        await state.update_data(overall_comment_message_id=comment_message.message_id)
        await state.set_state(SurveyStates.waiting_for_overall_comment)
    else:
        # Если высокая оценка - переходим к оценке блюд
        await start_meal_rating(callback.message, state)
    
    await callback.answer(f"Оценка {rating} принята!")

@router.callback_query(F.data == "skip_comment_overall")
async def skip_overall_comment(callback: CallbackQuery, state: FSMContext):
    """Пропуск комментария к общей оценке"""
    await callback.answer("Комментарий пропущен")
    
    # Удаляем сообщение с запросом комментария
    await callback.message.delete()
    
    await start_meal_rating(callback.message, state)

@router.message(SurveyStates.waiting_for_overall_comment)
async def process_overall_comment(message: Message, state: FSMContext):
    """Обработка комментария к общей оценке"""
    comment = message.text.strip()
    
    # Удаляем сообщение с комментарием пользователя
    await message.delete()
    
    # Удаляем сообщение с запросом комментария
    data = await state.get_data()
    if 'overall_comment_message_id' in data:
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=data['overall_comment_message_id']
            )
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")
    
    await state.update_data(overall_comment=comment)
    await start_meal_rating(message, state)

async def start_meal_rating(message: Message, state: FSMContext):
    """Начинает оценку блюд"""
    # Получаем сегодняшние блюда
    meals = await yandex_disk.get_today_meals()
    
    if not meals:
        await message.answer(
            "❌ *На сегодня фотографии блюд еще не загружены.*\n\n"
            "Попробуйте позже или обратитесь к администратору.",
            parse_mode="Markdown"
        )
        await state.clear()
        return
    
    # Сохраняем блюда в состоянии
    await state.update_data(
        meals=meals,
        current_meal_index=0,
        meal_ratings=[],
        low_rated_meals=[]
    )
    
    # Показываем первое блюдо
    await show_next_meal(message, state)

async def show_next_meal(message: Message, state: FSMContext):
    """Показывает следующее блюдо для оценки"""
    data = await state.get_data()
    meals = data['meals']
    current_index = data['current_meal_index']
    
    if current_index >= len(meals):
        # Все блюда оценены
        await process_meal_comments(message, state)
        return
    
    current_meal = meals[current_index]
    
    caption = (f"🍽 *{current_meal['name']}*\n\n"
               f"Оцените это блюдо:")
    
    try:
        meal_message = await message.answer_photo(
            photo=current_meal['download_url'],
            caption=caption,
            reply_markup=get_emoji_rating_keyboard("meal"),
            parse_mode="Markdown"
        )
        await state.update_data(current_meal_message_id=meal_message.message_id)
    except Exception as e:
        # Если не удалось отправить фото, отправляем текстом
        logger.error(f"Ошибка отправки фото: {e}")
        meal_message = await message.answer(
            caption,
            reply_markup=get_emoji_rating_keyboard("meal"),
            parse_mode="Markdown"
        )
        await state.update_data(current_meal_message_id=meal_message.message_id)
    
    await state.set_state(SurveyStates.waiting_for_meal_rating)

@router.callback_query(F.data.startswith("rating_meal_"))
async def process_meal_rating(callback: CallbackQuery, state: FSMContext):
    """Обработка оценки блюда через смайлики"""
    try:
        rating = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка обработки оценки")
        return
    
    # Удаляем сообщение с фото блюда
    await callback.message.delete()
    
    data = await state.get_data()
    meals = data['meals']
    current_index = data['current_meal_index']
    meal_ratings = data['meal_ratings']
    low_rated_meals = data['low_rated_meals']
    
    current_meal = meals[current_index]
    
    # Сохраняем оценку
    meal_rating = {
        "type": current_meal['type'],
        "rating": rating
    }
    meal_ratings.append(meal_rating)
    
    # Если оценка низкая, добавляем в список для комментариев
    if rating <= 3:
        low_rated_meals.append(current_meal['type'])
    
    # Обновляем состояние
    await state.update_data(
        meal_ratings=meal_ratings,
        low_rated_meals=low_rated_meals,
        current_meal_index=current_index + 1
    )
    
    # Показываем эмодзи в ответе
    emoji_map = {1: "😠", 2: "😕", 3: "😐", 4: "😊", 5: "🤩"}
    await callback.answer(f"Оценка {rating} {emoji_map.get(rating, '')} принята!")
    
    # Показываем следующее блюдо
    await show_next_meal(callback.message, state)

async def process_meal_comments(message: Message, state: FSMContext):
    """Обработка комментариев к блюдам с низкими оценками"""
    data = await state.get_data()
    low_rated_meals = data['low_rated_meals']
    
    if not low_rated_meals:
        # Нет низких оценок - завершаем опрос
        await finish_survey(message, state)
        return
    
    # Начинаем сбор комментариев для низкооцененных блюд
    await state.update_data(
        current_comment_meal_index=0,
        meal_comments=[]
    )
    
    await show_next_comment_request(message, state)

async def show_next_comment_request(message: Message, state: FSMContext):
    """Запрашивает комментарий для следующего низкооцененного блюда"""
    data = await state.get_data()
    low_rated_meals = data['low_rated_meals']
    current_index = data['current_comment_meal_index']
    
    if current_index >= len(low_rated_meals):
        # Все комментарии собраны
        await finish_survey(message, state)
        return
    
    meal_type = low_rated_meals[current_index]
    meal_name = meal_type.capitalize()
    
    comment_message = await message.answer(
        f"💬 *Комментарий для {meal_name}:*\n\n"
        f"Пожалуйста, напишите:\n"
        f"• Почему не понравилось это блюдо?\n"
        f"• На какое блюдо хотели бы поменять?\n\n"
        f"*Пример:* \"Слишком соленое, хотелось бы гречневую кашу\"",
        reply_markup=get_meal_comment_keyboard(),
        parse_mode="Markdown"
    )
    
    await state.update_data(current_comment_message_id=comment_message.message_id)
    await state.set_state(SurveyStates.waiting_for_meal_comment)

@router.callback_query(F.data == "skip_meal_comment")
async def skip_meal_comment(callback: CallbackQuery, state: FSMContext):
    """Пропуск комментария к блюду"""
    await callback.answer("Комментарий пропущен")
    
    # Удаляем сообщение с запросом комментария
    await callback.message.delete()
    
    data = await state.get_data()
    current_index = data['current_comment_meal_index']
    await state.update_data(current_comment_meal_index=current_index + 1)
    
    await show_next_comment_request(callback.message, state)

@router.message(SurveyStates.waiting_for_meal_comment)
async def process_meal_comment(message: Message, state: FSMContext):
    """Обработка комментария к блюду"""
    comment = message.text.strip()
    
    # Удаляем сообщение с комментарием пользователя
    await message.delete()
    
    # Удаляем сообщение с запросом комментария
    data = await state.get_data()
    if 'current_comment_message_id' in data:
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=data['current_comment_message_id']
            )
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")
    
    data = await state.get_data()
    low_rated_meals = data['low_rated_meals']
    current_index = data['current_comment_meal_index']
    meal_comments = data['meal_comments']
    
    meal_type = low_rated_meals[current_index]
    
    # Сохраняем комментарий
    meal_comment = {
        "type": meal_type,
        "comment": comment
    }
    meal_comments.append(meal_comment)
    
    # Обновляем состояние
    await state.update_data(
        meal_comments=meal_comments,
        current_comment_meal_index=current_index + 1
    )
    
    await show_next_comment_request(message, state)

async def finish_survey(message: Message, state: FSMContext):
    """Завершение опроса и сохранение/обновление данных"""
    global current_user_id
    
    data = await state.get_data()
    
    try:
        # УБЕЖДАЕМСЯ, что пользователь создан в таблице users
        user_data = {
            "telegram_id": current_user_id,  # Используем сохраненный ID
            "full_name": data.get('full_name', ''),
            "class": data.get('class_name', ''),
            "has_profile": True
        }
        
        if not await supabase_client.user_exists(current_user_id):
            await supabase_client.create_user(user_data)
            logger.info(f"✅ Создан пользователь: {current_user_id}")
        else:
            await supabase_client.update_user_info(
                current_user_id, 
                data.get('full_name', ''), 
                data.get('class_name', '')
            )
            logger.info(f"✅ Обновлен пользователь: {current_user_id}")
        
        # Теперь проверяем, есть ли уже анкета
        existing_survey = await supabase_client.get_user_survey(current_user_id)  # Используем сохраненный ID
        
        if existing_survey.data:
            # ОБНОВЛЯЕМ существующую анкету
            survey_id = existing_survey.data[0]['id']
            
            # Обновляем анкету
            survey_data = {
                "eats_at_school": data['eats_at_school'],
                "overall_satisfaction": data.get('overall_satisfaction'),
                "overall_comment": data.get('overall_comment', '')
            }
            await supabase_client.update_survey(survey_id, survey_data)
            
            # Удаляем старые оценки и комментарии
            await supabase_client.delete_meal_ratings(survey_id)
            await supabase_client.delete_meal_comments(survey_id)
            
            update_message = "🔄 *Ваш опрос обновлен!*"
            
        else:
            # СОЗДАЕМ новую анкету
            survey_data = {
                "telegram_id": current_user_id,  # Используем сохраненный ID
                "eats_at_school": data['eats_at_school'],
                "overall_satisfaction": data.get('overall_satisfaction'),
                "overall_comment": data.get('overall_comment', '')
            }
            
            survey_response = await supabase_client.create_survey(survey_data)
            survey_id = survey_response.data[0]['id']
            update_message = "✅ *Спасибо за ваш отзыв!*"
        
        # Сохраняем оценки блюд
        for meal_rating in data['meal_ratings']:
            rating_data = {
                "survey_id": survey_id,
                "meal_type": meal_rating['type'],
                "rating": meal_rating['rating']
            }
            await supabase_client.add_meal_rating(rating_data)
        
        # Сохраняем комментарии к блюдам
        meal_comments = data.get('meal_comments', [])
        
        # Получаем типы блюд, которые были оценены
        rated_meal_types = [rating['type'] for rating in data['meal_ratings']]
        
        # Создаем комментарии ТОЛЬКО для оцененных блюд
        for meal_type in rated_meal_types:
            # Ищем комментарий для этого типа блюда
            comment_for_meal = next(
                (c for c in meal_comments if c['type'] == meal_type), 
                None
            )
            
            comment_data = {
                "survey_id": survey_id,
                "meal_type": meal_type,
                "reason_comment": comment_for_meal.get('comment', '') if comment_for_meal else "",
                "alternative_comment": ""
            }
            await supabase_client.add_meal_comment(comment_data)
        
        # Формируем итоговое сообщение
        result_text = f"{update_message}\n\n"
        result_text += "Ваши ответы сохранены и будут учтены для улучшения питания.\n\n"
        result_text += "📊 *Краткая статистика:*\n"
        
        # Добавляем общую оценку если есть
        if data.get('overall_satisfaction'):
            emoji_map = {1: "😠", 2: "😕", 3: "😐", 4: "😊", 5: "🤩"}
            result_text += f"• Общая оценка: {data['overall_satisfaction']} {emoji_map.get(data['overall_satisfaction'], '')}\n"
        
        result_text += f"• Оценено блюд: {len(data['meal_ratings'])}\n"
        
        # Добавляем смайлики к оценкам блюд
        emoji_map = {1: "😠", 2: "😕", 3: "😐", 4: "😊", 5: "🤩"}
        for rating in data['meal_ratings']:
            result_text += f"• {rating['type'].capitalize()}: {rating['rating']} {emoji_map.get(rating['rating'], '')}\n"
        
        low_rated_count = len(data.get('low_rated_meals', []))
        if low_rated_count > 0:
            result_text += f"• Комментариев: {low_rated_count}\n"
        
        result_text += "\nСпасибо за ваше время! 🍽️"
        
        await message.answer(result_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Ошибка сохранения опроса: {e}")
        await message.answer(
            "❌ Произошла ошибка при сохранении данных. "
            "Попробуйте начать заново с команды /mark"
        )
    
    finally:
        # Очищаем глобальную переменную
        current_user_id = None
        await state.clear()