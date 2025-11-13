from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict

async def create_type_keyboard() -> InlineKeyboardMarkup:
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Завтрак",callback_data="type_zavtrak")],
        [InlineKeyboardButton(text="Обед",callback_data="type_obed")],
        [InlineKeyboardButton(text="Полдник",callback_data="type_poldnik")]
    ])
    
# Смайлики для оценок
rating_emojis = {
    1: "😠",
    2: "😕", 
    3: "😐",
    4: "🙂",
    5: "😊"
}

def get_rating_keyboard():
    """Создает клавиатуру с кнопками оценок"""
    builder = InlineKeyboardBuilder()
    for rating in range(1, 6):
        builder.button(
            text=f"{rating} {rating_emojis[rating]}", 
            callback_data=f"rating_{rating}"
        )
    builder.adjust(5)  # 5 кнопок в одном ряду
    return builder.as_markup()

def get_comment_keyboard():
    """Создает клавиатуру для комментария"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Без комментариев", callback_data="no_comment")
    return builder.as_markup()