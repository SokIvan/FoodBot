from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict

async def create_type_keyboard() -> InlineKeyboardMarkup:
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Завтрак",callback_data="type_zavtrak")],
        [InlineKeyboardButton(text="Обед",callback_data="type_obed")],
        [InlineKeyboardButton(text="Полдник",callback_data="type_poldnik")]
    ])