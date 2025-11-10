from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict

async def create_dish_keyboard(dishes: List[Dict], current_dish: str = None) -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопками блюд"""
    buttons = []
    
    for dish in dishes:
        if dish["full_name"] != current_dish:
            buttons.append(
                InlineKeyboardButton(
                    text=dish["name"],
                    callback_data=f"dish:{dish['full_name']}"
                )
            )
    
    # Создаем клавиатуру с кнопками в 2 колонки
    keyboard = []
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        keyboard.append(row)
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)