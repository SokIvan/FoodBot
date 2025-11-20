from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging

router = Router()
logger = logging.getLogger(__name__)

class SurveyStates(StatesGroup):
    waiting_for_school_confirmation = State()
    waiting_for_user_info = State()
    waiting_for_overall_satisfaction = State()
    waiting_for_overall_comment = State()
    waiting_for_meal_rating = State()
    waiting_for_meal_comment = State()

# mark_handler.py - обновляем первый вопрос
@router.message(Command("mark"))
async def start_survey(message: types.Message, state: FSMContext):
    """Начало опроса"""
    from keyboards.survey_keyboards import get_school_confirmation_keyboard
    
    # Проверяем, не находится ли пользователь уже в процессе опроса
    current_state = await state.get_state()
    if current_state is not None:
        await message.answer(
            "⏳ *Вы уже начали оценку питания!*\n\n"
            "Завершите текущую оценку или используйте /reset чтобы начать заново.",
            parse_mode="Markdown"
        )
        return
    
    # Инициализируем глобальную переменную
    from callbacks.type_callback import current_user_id
    global current_user_id
    current_user_id = message.from_user.id
    logger.info(f"👤 Инициализирован user_id: {current_user_id}")
    
    await message.answer(
        "🏫 *Первый вопрос:*\n\n"
        "Вы питаетесь в школьной столовой?",  # Измененный текст
        reply_markup=get_school_confirmation_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(SurveyStates.waiting_for_school_confirmation)