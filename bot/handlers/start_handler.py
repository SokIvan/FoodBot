from aiogram import Router, types
from aiogram.filters import Command
from functions.yandex_disk import yandex_disk
from keyboards.food_keyboard import create_dish_keyboard
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command("start"))
async def start_command(message: types.Message):
    """Обработчик команды /start"""
    await message.answer(text="""
                         Я могу оценивать блюда в столовой!\n
                         Вводи команду /mark и помоги мне собрать статистику!
                         """)