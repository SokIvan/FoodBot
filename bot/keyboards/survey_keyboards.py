from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

def get_school_confirmation_keyboard():
    """Клавиатура для подтверждения питания в школе"""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="✅ Да, питаюсь", callback_data="school_yes"),
        InlineKeyboardButton(text="❌ Нет, не питаюсь", callback_data="school_no")
    )
    return builder.as_markup()

def get_emoji_rating_keyboard(rating_type="meal"):
    """Смайликовая клавиатура для оценок"""
    builder = InlineKeyboardBuilder()
    
    # Смайлики с оценками
    ratings = [
        ("1 😠", f"rating_{rating_type}_1"),
        ("2 😕", f"rating_{rating_type}_2"), 
        ("3 😐", f"rating_{rating_type}_3"),
        ("4 😊", f"rating_{rating_type}_4"),
        ("5 🤩", f"rating_{rating_type}_5")
    ]
    
    for text, callback_data in ratings:
        builder.add(InlineKeyboardButton(text=text, callback_data=callback_data))
    
    builder.adjust(5)
    return builder.as_markup()

def get_comment_skip_keyboard(comment_type="overall"):
    """Клавиатура для пропуска комментария"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="🚫 Без комментариев", 
        callback_data=f"skip_comment_{comment_type}"
    ))
    return builder.as_markup()

def get_meal_comment_keyboard():
    """Клавиатура для комментариев к блюдам"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="🚫 Пропустить комментарий", 
        callback_data="skip_meal_comment"
    ))
    return builder.as_markup()