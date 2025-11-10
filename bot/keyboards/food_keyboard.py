from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict

async def create_dish_keyboard(dishes: List[Dict], current_dish: str = None) -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопками блюд"""
    keyboard = []
    
    for dish in dishes:
        if dish["full_name"] != current_dish:
            keyboard.append([
                InlineKeyboardButton(
                    text=dish["name"],
                    callback_data=f"dish:{dish['full_name']}"
                )
            ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)