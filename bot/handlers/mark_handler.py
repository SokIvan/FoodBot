from aiogram import Router, types
from aiogram.filters import Command
from keyboards.type_keyboard import create_type_keyboard
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command("mark"))
async def start_command(message: types.Message):
    """Обработчик команды /mark"""
    await message.answer(text="Какое меню вы хотели бы оценить?",reply_markup=await create_type_keyboard())