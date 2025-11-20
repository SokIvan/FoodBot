from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import logging
from keyboards.survey_keyboards import get_school_confirmation_keyboard, get_comment_skip_keyboard

router = Router()
logger = logging.getLogger(__name__)

from keyboards.survey_keyboards import (
    get_school_confirmation_keyboard,
    get_emoji_rating_keyboard,
    get_comment_skip_keyboard,
    get_meal_comment_keyboard
)
from functions.yandex_disk import yandex_disk
from database.db_supabase import supabase_client


current_user_id = None

class SpecialSurveyStates(StatesGroup):
    waiting_for_date = State()
    waiting_for_school_confirmation = State()
    waiting_for_no_school_reason = State()  # Новое состояние для причины
    waiting_for_user_info = State()
    waiting_for_overall_satisfaction = State()
    waiting_for_overall_comment = State()
    waiting_for_meal_rating = State()
    waiting_for_meal_comment = State()

@router.message(Command("mark_special"))
async def start_special_survey(message: types.Message, state: FSMContext):
    """Начало специального опроса для произвольной даты"""
    global current_user_id
    
    # Проверяем, не находится ли пользователь уже в процессе опроса
    current_state = await state.get_state()
    if current_state is not None:
        await message.answer(
            "⏳ *Вы уже начали оценку питания!*\n\n"
            "Завершите текущую оценку или используйте /reset чтобы начать заново.",
            parse_mode="Markdown"
        )
        return
    
    # Сохраняем user_id в глобальную переменную
    current_user_id = message.from_user.id
    logger.info(f"👤 Инициализирован user_id для специального опроса: {current_user_id}")
    
    await message.answer(
        "📅 *Оценка питания за конкретный день*\n\n"
        "Введите дату в формате *ДД.ММ.ГГГГ*:\n"
        "*Пример:* 15.12.2024",
        parse_mode="Markdown"
    )
    await state.set_state(SpecialSurveyStates.waiting_for_date)

@router.message(SpecialSurveyStates.waiting_for_date)
async def process_special_date(message: types.Message, state: FSMContext):
    """Обработка введенной даты"""
    date_input = message.text.strip()
    
    try:
        # Парсим дату
        survey_date = datetime.strptime(date_input, "%d.%m.%Y").date()
        today = datetime.now().date()
        
        # Проверяем что дата не в будущем
        if survey_date > today:
            await message.answer(
                "❌ *Нельзя оценить питание за будущую дату!*\n\n"
                "Введите корректную дату в формате ДД.ММ.ГГГГ:",
                parse_mode="Markdown"
            )
            return
        
        # Сохраняем дату в состоянии
        await state.update_data(survey_date=survey_date.isoformat())
        
        # Удаляем сообщение с вводом даты
        await message.delete()
        
        # Переходим к первому вопросу
        await message.answer(
            "🏫 *Первый вопрос:*\n\n"
            "Вы питаетесь в школьной столовой?",
            reply_markup=get_school_confirmation_keyboard(),
            parse_mode="Markdown"
        )
        await state.set_state(SpecialSurveyStates.waiting_for_school_confirmation)
        
    except ValueError:
        await message.answer(
            "❌ *Неверный формат даты!*\n\n"
            "Введите дату в формате *ДД.ММ.ГГГГ*:\n"
            "*Пример:* 15.12.2024",
            parse_mode="Markdown"
        )

@router.callback_query(SpecialSurveyStates.waiting_for_school_confirmation, F.data.startswith("school_"))
async def process_special_school_confirmation(callback: types.CallbackQuery, state: FSMContext):
    """Обработка подтверждения питания в школе для специальной даты"""
    global current_user_id
    
    # Обновляем user_id из callback
    current_user_id = callback.from_user.id
    
    eats_at_school = callback.data == "school_yes"
    
    # Сохраняем в состоянии
    await state.update_data(eats_at_school=eats_at_school)
    
    # Удаляем сообщение с вопросом
    await callback.message.delete()
    
    if not eats_at_school:
        # Если не питается в школе - запрашиваем причину
        reason_message = await callback.message.answer(
            "💬 *Почему вы не питаетесь в школьной столовой?*\n\n"
            "Напишите причину:\n"
            "• Не нравится еда?\n" 
            "• Приносите еду с собой?\n"
            "• Другая причина?",
            reply_markup=get_comment_skip_keyboard("no_school_reason"),
            parse_mode="Markdown"
        )
        await state.update_data(no_school_reason_message_id=reason_message.message_id)
        await state.set_state(SpecialSurveyStates.waiting_for_no_school_reason)
    else:
        # Если питается - переходим к запросу ФИО и класса
        new_message = await callback.message.answer(
            "📝 *Отлично! Теперь расскажите о себе:*\n\n"
            "Напишите ваши *полные Фамилию и Имя* и *класс* в формате:\n"
            "`Иванов Иван 5А`\n\n"
            "*Пример:* Иванова Мария 8Б",
            parse_mode="Markdown"
        )
        await state.update_data(user_info_message_id=new_message.message_id)
        await state.set_state(SpecialSurveyStates.waiting_for_user_info)
    
    await callback.answer()

# special_mark_handler.py - добавляем обработчик для ФИО
@router.message(SpecialSurveyStates.waiting_for_user_info)
async def process_special_user_info(message: types.Message, state: FSMContext):
    """Обработка ФИО и класса пользователя для специальной даты"""
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
        from database.db_supabase import supabase_client
        
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
    await state.set_state(SpecialSurveyStates.waiting_for_overall_satisfaction)

@router.callback_query(SpecialSurveyStates.waiting_for_no_school_reason, F.data == "skip_comment_no_school_reason")
async def skip_no_school_reason(callback: types.CallbackQuery, state: FSMContext):
    """Пропуск причины непосещения столовой"""
    global current_user_id
    
    # Обновляем user_id
    current_user_id = callback.from_user.id
    
    await callback.answer("Причина пропущена")
    await callback.message.delete()
    
    # Сохраняем пользователя в БД даже если он не питается в столовой
    try:
        user_data = {
            "telegram_id": current_user_id,
            "full_name": "",
            "class": "",
            "has_profile": False
        }
        
        if not await supabase_client.user_exists(current_user_id):
            await supabase_client.create_user(user_data)
            logger.info(f"✅ Создан пользователь для специальной анкеты (не питается): {current_user_id}")
        
        # Создаем анкету с пустой причиной
        data = await state.get_data()
        survey_date = data.get('survey_date', 'Неизвестная дата')
        
        survey_data = {
            "eats_at_school": False,
            "no_school_reason": "",
            "overall_satisfaction": None,
            "overall_comment": ""
        }
        
        await supabase_client.create_or_update_survey_for_date(
            current_user_id,
            survey_date,
            survey_data
        )
        logger.info(f"✅ Создана специальная анкета с пустой причиной для {current_user_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения специальной анкеты с пустой причиной: {e}")
    
    # Завершаем опрос так как пользователь не питается в школе
    data = await state.get_data()
    survey_date = data.get('survey_date', 'Неизвестная дата')
    formatted_date = datetime.strptime(survey_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    
    await callback.message.answer(
        f"❌ *Оценка питания за {formatted_date} отменена*\n\n"
        "Этот бот предназначен только для учащихся, которые питаются в школьной столовой.",
        parse_mode="Markdown"
    )
    await state.clear()

@router.message(SpecialSurveyStates.waiting_for_no_school_reason)
async def process_no_school_reason(message: types.Message, state: FSMContext):
    """Обработка причины непосещения столовой"""
    global current_user_id
    
    # Обновляем user_id
    current_user_id = message.from_user.id
    
    reason = message.text.strip()
    
    # Удаляем сообщение с комментарием пользователя
    await message.delete()
    
    # Удаляем сообщение с запросом причины
    data = await state.get_data()
    if 'no_school_reason_message_id' in data:
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=data['no_school_reason_message_id']
            )
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")
    
    # Сохраняем причину
    await state.update_data(no_school_reason=reason)
    
    # Завершаем опрос с информацией о причине
    survey_date = data.get('survey_date', 'Неизвестная дата')
    formatted_date = datetime.strptime(survey_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    
    await message.answer(
        f"📝 *Ваш отзыв за {formatted_date} сохранен*\n\n"
        f"*Причина непосещения столовой:* {reason}\n\n"
        "Спасибо за обратную связь! Эта информация поможет улучшить школьное питание.",
        parse_mode="Markdown"
    )
    
    # Сохраняем в БД
    try:
        # Сохраняем пользователя даже если он не питается в столовой
        user_data = {
            "telegram_id": current_user_id,
            "full_name": "",
            "class": "",
            "has_profile": False
        }
        
        if not await supabase_client.user_exists(current_user_id):
            await supabase_client.create_user(user_data)
            logger.info(f"✅ Создан пользователь для специальной анкеты (не питается): {current_user_id}")
        
        # Создаем анкету с причиной
        survey_data = {
            "eats_at_school": False,
            "no_school_reason": reason,
            "overall_satisfaction": None,
            "overall_comment": ""
        }
        
        await supabase_client.create_or_update_survey_for_date(
            current_user_id,
            survey_date,
            survey_data
        )
        logger.info(f"✅ Создана специальная анкета с причиной для {current_user_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения специальной анкеты с причиной: {e}")
    
    await state.clear()

# Добавляем обработчики для остальных состояний (аналогично type_callback.py но с учетом даты)
@router.callback_query(SpecialSurveyStates.waiting_for_overall_satisfaction, F.data.startswith("rating_overall_"))
async def process_special_overall_rating(callback: types.CallbackQuery, state: FSMContext):
    """Обработка общей оценки питания для специальной даты"""
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
        await state.set_state(SpecialSurveyStates.waiting_for_overall_comment)
    else:
        # Если высокая оценка - переходим к оценке блюд
        await start_special_meal_rating(callback.message, state)
    
    await callback.answer(f"Оценка {rating} принята!")

@router.callback_query(SpecialSurveyStates.waiting_for_overall_comment, F.data == "skip_comment_overall")
async def skip_special_overall_comment(callback: types.CallbackQuery, state: FSMContext):
    """Пропуск комментария к общей оценке для специальной даты"""
    await callback.answer("Комментарий пропущен")
    await callback.message.delete()
    await start_special_meal_rating(callback.message, state)

@router.message(SpecialSurveyStates.waiting_for_overall_comment)
async def process_special_overall_comment(message: types.Message, state: FSMContext):
    """Обработка комментария к общей оценке для специальной даты"""
    comment = message.text.strip()
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
    await start_special_meal_rating(message, state)

async def start_special_meal_rating(message: types.Message, state: FSMContext):
    """Начинает оценку блюд для специальной даты"""
    data = await state.get_data()
    survey_date = data.get('survey_date')
    
    if not survey_date:
        await message.answer("❌ Ошибка: дата не найдена. Начните заново.")
        await state.clear()
        return
    
    # Получаем блюда для указанной даты
    formatted_date = datetime.strptime(survey_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    meals = await yandex_disk.get_meals_for_date(formatted_date)
    
    if not meals:
        await message.answer(
            "❌ *На выбранную дату фотографии блюд не найдены.*\n\n"
            "Попробуйте другую дату или обратитесь к администратору.",
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
    await show_special_next_meal(message, state)

async def show_special_next_meal(message: types.Message, state: FSMContext):
    """Показывает следующее блюдо для оценки для специальной даты"""
    data = await state.get_data()
    meals = data['meals']
    current_index = data['current_meal_index']
    
    if current_index >= len(meals):
        # Все блюда оценены
        await process_special_meal_comments(message, state)
        return
    
    current_meal = meals[current_index]
    
    # КРАСИВЫЕ ТЕКСТЫ в зависимости от наличия фото
    if current_meal.get('has_image', True) and current_meal.get('download_url'):
        caption = (f"🍽 *{current_meal['name']}*\n\n"
                   f"Оцените это блюдо:")
    else:
        meal_type = current_meal['type']
        if meal_type == "первое":
            caption = "🍵 *Первое блюдо*\n\nКак вы оцените сегодняшний суп?"
        elif meal_type == "второе":
            caption = "🍛 *Второе блюдо*\n\nНасколько вам понравилось основное блюдо?"
        elif meal_type == "напиток":
            caption = "🥤 *Напиток*\n\nКак вам сегодняшний напиток?"
        else:
            caption = f"🍽 *{current_meal['name']}*\n\nКак вы оцените это блюдо?"
    
    # Проверяем есть ли изображение у блюда
    has_image = current_meal.get('has_image', True) and current_meal.get('download_url')
    
    try:
        if has_image:
            # Отправляем с фото
            meal_message = await message.answer_photo(
                photo=current_meal['download_url'],
                caption=caption,
                reply_markup=get_emoji_rating_keyboard("meal"),
                parse_mode="Markdown"
            )
        else:
            # Отправляем только текст
            meal_message = await message.answer(
                caption,
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
    
    await state.set_state(SpecialSurveyStates.waiting_for_meal_rating)

@router.callback_query(SpecialSurveyStates.waiting_for_meal_rating, F.data.startswith("rating_meal_"))
async def process_special_meal_rating(callback: types.CallbackQuery, state: FSMContext):
    """Обработка оценки блюда для специальной даты"""
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
    await show_special_next_meal(callback.message, state)

async def process_special_meal_comments(message: types.Message, state: FSMContext):
    """Обработка комментариев к блюдам с низкими оценками для специальной даты"""
    data = await state.get_data()
    low_rated_meals = data['low_rated_meals']
    
    if not low_rated_meals:
        # Нет низких оценок - завершаем опрос
        await finish_special_survey(message, state)
        return
    
    # Начинаем сбор комментариев для низкооцененных блюд
    await state.update_data(
        current_comment_meal_index=0,
        meal_comments=[]
    )
    
    await show_special_next_comment_request(message, state)

async def show_special_next_comment_request(message: types.Message, state: FSMContext):
    """Запрашивает комментарий для следующего низкооцененного блюда для специальной даты"""
    data = await state.get_data()
    low_rated_meals = data['low_rated_meals']
    current_index = data['current_comment_meal_index']
    
    if current_index >= len(low_rated_meals):
        # Все комментарии собраны
        await finish_special_survey(message, state)
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
    await state.set_state(SpecialSurveyStates.waiting_for_meal_comment)

@router.callback_query(SpecialSurveyStates.waiting_for_meal_comment, F.data == "skip_meal_comment")
async def skip_special_meal_comment(callback: types.CallbackQuery, state: FSMContext):
    """Пропуск комментария к блюду для специальной даты"""
    await callback.answer("Комментарий пропущен")
    await callback.message.delete()
    
    data = await state.get_data()
    current_index = data['current_comment_meal_index']
    await state.update_data(current_comment_meal_index=current_index + 1)
    
    await show_special_next_comment_request(callback.message, state)

@router.message(SpecialSurveyStates.waiting_for_meal_comment)
async def process_special_meal_comment(message: types.Message, state: FSMContext):
    """Обработка комментария к блюду для специальной даты"""
    comment = message.text.strip()
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
    
    await show_special_next_comment_request(message, state)

async def finish_special_survey(message: types.Message, state: FSMContext):
    """Завершение специального опроса и сохранение данных"""
    global current_user_id
    
    data = await state.get_data()
    survey_date = data.get('survey_date')
    
    try:
        # Используем глобальную переменную current_user_id
        user_id = current_user_id
        
        # ПЕРВОЕ: Убедимся, что пользователь существует в таблице users
        user_exists = await supabase_client.user_exists(user_id)
        if not user_exists:
            # Создаем базового пользователя
            user_data = {
                "telegram_id": user_id,
                "full_name": data.get('full_name', 'Не указано'),
                "class": data.get('class_name', 'Не указан'),
                "has_profile": True
            }
            await supabase_client.create_user(user_data)
            logger.info(f"✅ Создан пользователь для специальной анкеты: {user_id}")
        
        # ВТОРОЕ: Создаем/обновляем анкету для указанной даты
        survey_data = {
            "telegram_id": user_id,  # ИСПРАВЛЕНО: используем user_id, а не message.from_user.id
            "eats_at_school": True,
            "overall_satisfaction": data.get('overall_satisfaction'),
            "overall_comment": data.get('overall_comment', ''),
            "no_school_reason": "",  # Пустая строка так как питается в школе
            "date": survey_date  # Добавляем дату
        }
        
        # Проверяем существующую анкету для этой даты
        existing_survey = await supabase_client.get_user_survey_for_date(user_id, survey_date)  # ИСПРАВЛЕНО
        
        if existing_survey.data:
            # Обновляем существующую анкету
            survey_id = existing_survey.data[0]['id']
            await supabase_client.update_survey(survey_id, survey_data)
            
            # Удаляем старые оценки и комментарии
            await supabase_client.delete_meal_ratings(survey_id)
            await supabase_client.delete_meal_comments(survey_id)
            
            update_message = "🔄 Ваш опрос обновлен!"
        else:
            # Создаем новую анкету
            survey_response = await supabase_client.create_survey(survey_data)
            survey_id = survey_response.data[0]['id']
            update_message = "✅ Спасибо за ваш отзыв!"
        
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
        rated_meal_types = [rating['type'] for rating in data['meal_ratings']]
        
        for meal_type in rated_meal_types:
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
        
        # ТРЕТЬЕ: Формируем сообщение
        formatted_date = datetime.strptime(survey_date, "%Y-%m-%d").strftime("%d.%m.%Y")
        
        result_text = f"{update_message}\n\n"
        result_text += f"Ваши ответы за {formatted_date} сохранены и будут учтены для улучшения питания.\n\n"
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
        logger.error(f"Ошибка сохранения специального опроса: {e}")
        await message.answer(
            "❌ Произошла ошибка при сохранении данных. "
            "Попробуйте начать заново с команды /mark_special"
        )
    
    finally:
        await state.clear()