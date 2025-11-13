import asyncio
from datetime import datetime
import pandas as pd
from io import BytesIO
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.filters import Command
from config import admins
from database.db_supabase import supabase_client
import logging
from keyboards.type_keyboard import rating_emojis

logger = logging.getLogger(__name__)
sheets_created = False
router = Router()

# Система оценок
rating_emojis = {
    1: "😠",
    2: "😕", 
    3: "😐",
    4: "🙂",
    5: "😊"
}

# Фильтр для админов
def admin_filter(message: Message):
    return message.from_user.id in admins

# Класс для пагинации по блюдам
class FoodPagination:
    def __init__(self):
        self.current_food_index = 0
        self.foods = []
        self.message_id = None

food_pagination = {}

# 1) Показать все данные
@router.message(Command("show"), F.from_user.id.in_(admins))
async def show_all_data(message: Message):
    try:
        # Получаем все отзывы о еде
        food_response = await supabase_client.get_all_food_reviews()
        food_data = food_response.data
        
        # Получаем все отзывы о меню
        menu_response = await supabase_client.get_all_food_menu_reviews()
        menu_data = menu_response.data
        
        if not food_data and not menu_data:
            await message.answer("Нет данных для отображения")
            return
        
        # Создаем Excel файл
        with BytesIO() as output:
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                sheets_created = False
                
                # Анализ блюд (таблица food)
                if food_data:
                    df_food = pd.DataFrame(food_data)
                    
                    # Преобразуем mark в число
                    df_food['mark'] = pd.to_numeric(df_food['mark'], errors='coerce')
                    
                    # Средняя оценка по блюдам по дням
                    food_daily_avg = df_food.groupby(['date', 'name'])['mark'].mean().round(2).reset_index()
                    food_daily_avg.to_excel(writer, sheet_name='Блюда по дням', index=False)
                    
                    # Общая средняя оценка по блюдам
                    food_overall_avg = df_food.groupby('name')['mark'].agg(['mean', 'count']).round(2)
                    food_overall_avg.columns = ['Средняя оценка', 'Количество оценок']
                    food_overall_avg.to_excel(writer, sheet_name='Общая статистика блюд')
                    
                    sheets_created = True
                
                # Анализ меню (таблица food_menu)
                if menu_data:
                    df_menu = pd.DataFrame(menu_data)
                    
                    # Преобразуем mark в число (так как в food_menu mark - text)
                    df_menu['mark'] = pd.to_numeric(df_menu['mark'], errors='coerce')
                    
                    # Средняя оценка по типам меню по дням
                    menu_daily_avg = df_menu.groupby(['date', 'type'])['mark'].mean().round(2).reset_index()
                    menu_daily_avg.to_excel(writer, sheet_name='Меню по дням', index=False)
                    
                    # Общая средняя оценка по типам меню
                    menu_overall_avg = df_menu.groupby('type')['mark'].agg(['mean', 'count']).round(2)
                    menu_overall_avg.columns = ['Средняя оценка', 'Количество оценок']
                    menu_overall_avg.to_excel(writer, sheet_name='Общая статистика меню')
                    
                    sheets_created = True
            
            output.seek(0)
            # Используем BufferedInputFile для отправки документа
            document = BufferedInputFile(output.getvalue(), filename="food_statistics.xlsx")
            await message.answer_document(
                document=document,
                caption="Статистика по всем данным"
            )
            
    except Exception as e:
        error_msg = f"Ошибка при получении данных: {str(e)}"
        # Убираем разметку для сообщений об ошибках
        await message.answer(error_msg)

# 2) Показать данные за сегодня
@router.message(Command("show_today"), F.from_user.id.in_(admins))
async def show_today_data(message: Message):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Получаем отзывы о еде за сегодня
        food_response = await supabase_client.get_all_food_reviews()
        food_today = [item for item in food_response.data if item.get('date') == today]
        
        # Получаем отзывы о меню за сегодня
        menu_response = await supabase_client.get_all_food_menu_reviews()
        menu_today = [item for item in menu_response.data if item.get('date') == today]
        
        if not food_today and not menu_today:
            await message.answer("Нет данных за сегодня")
            return
        
        response_text = f"📊 Статистика за {today}:\n\n"
        
        # Статистика по блюдам
        if food_today:
            response_text += "🍽️ Блюда:\n"
            food_df = pd.DataFrame(food_today)
            food_df['mark'] = pd.to_numeric(food_df['mark'], errors='coerce')
            food_stats = food_df.groupby('name')['mark'].agg(['mean', 'count']).round(2)
            
            for food_name, stats in food_stats.iterrows():
                response_text += f"• {food_name}: {stats['mean']}⭐ ({int(stats['count'])} оценок)\n"
            response_text += "\n"
        
        # Статистика по меню
        if menu_today:
            response_text += "📋 Типы меню:\n"
            menu_df = pd.DataFrame(menu_today)
            menu_df['mark'] = pd.to_numeric(menu_df['mark'], errors='coerce')
            menu_stats = menu_df.groupby('type')['mark'].agg(['mean', 'count']).round(2)
            
            for menu_type, stats in menu_stats.iterrows():
                response_text += f"• {menu_type}: {stats['mean']}⭐ ({int(stats['count'])} оценок)\n"
        
        # Разбиваем длинное сообщение на части
        if len(response_text) > 4096:
            parts = [response_text[i:i+4096] for i in range(0, len(response_text), 4096)]
            for part in parts:
                await message.answer(part)
        else:
            await message.answer(response_text)
        
    except Exception as e:
        error_msg = f"Ошибка при получении данных: {str(e)}"
        await message.answer(error_msg)

# Вспомогательные функции для показа блюд
async def get_food_distribution(food_name):
    """Получает распределение оценок для блюда в процентах"""
    response = await supabase_client.get_food_reviews_by_name(food_name)
    reviews = response.data
    
    if not reviews:
        return {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    
    total = len(reviews)
    distribution = {}
    
    for rating in range(1, 6):
        count = len([r for r in reviews if int(r['mark']) == rating])
        percentage = round((count / total) * 100) if total > 0 else 0
        distribution[rating] = percentage
    
    return distribution

def create_food_keyboard(user_id, current_index, total_foods):
    """Создает клавиатуру для навигации по блюдам"""
    keyboard = []
    
    # Кнопки навигации
    nav_buttons = []
    if current_index > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"food_prev_{user_id}"))
    
    nav_buttons.append(InlineKeyboardButton(text=f"{current_index + 1}/{total_foods}", callback_data="no_action"))
    
    if current_index < total_foods - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"food_next_{user_id}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Кнопка выхода
    keyboard.append([InlineKeyboardButton(text="❌ Выйти", callback_data=f"food_exit_{user_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def show_food_page(message: Message, user_id: int, index: int):
    """Показывает страницу с информацией о блюде"""
    foods = food_pagination[user_id].foods
    food_name = foods[index]
    food_pagination[user_id].current_food_index = index
    
    distribution = await get_food_distribution(food_name)
    
    # Формируем текст с распределением оценок (без разметки)
    text = f"🍽️ {food_name}:\n\n"
    for rating in range(5, 0, -1):
        emoji = rating_emojis[rating]
        percentage = distribution[rating]
        text += f"{emoji} - {percentage}%\n"
    
    # Добавляем среднюю оценку
    total_reviews = sum([count for count in distribution.values()])
    if total_reviews > 0:
        avg_rating = sum(rating * count for rating, count in distribution.items()) / total_reviews
        text += f"\n📊 Средняя оценка: {avg_rating:.2f}⭐"
        text += f"\n👥 Всего оценок: {total_reviews}"
    
    keyboard = create_food_keyboard(user_id, index, len(foods))
    
    if food_pagination[user_id].message_id:
        # Обновляем существующее сообщение
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=food_pagination[user_id].message_id,
            text=text,
            reply_markup=keyboard
        )
    else:
        # Отправляем новое сообщение
        sent_message = await message.answer(text, reply_markup=keyboard)
        food_pagination[user_id].message_id = sent_message.message_id

# 3) Показать блюда с инлайн кнопками
@router.message(Command("show_food"), F.from_user.id.in_(admins))
async def show_food_handler(message: Message):
    try:
        user_id = message.from_user.id
        
        # Получаем список всех уникальных блюд
        response = await supabase_client.get_all_food_reviews()
        foods = list(set([item['name'] for item in response.data]))
        
        if not foods:
            await message.answer("Нет данных о блюдах")
            return
        
        food_pagination[user_id] = FoodPagination()
        food_pagination[user_id].foods = foods
        
        # Показываем первое блюдо
        await show_food_page(message, user_id, 0)
        
    except Exception as e:
        error_msg = f"Ошибка: {str(e)}"
        await message.answer(error_msg)

# Обработчик инлайн кнопок для навигации по блюдам
@router.callback_query(F.data.startswith("food_"))
async def handle_food_callback(callback: CallbackQuery):
    try:
        user_id = callback.from_user.id
        data = callback.data
        
        if user_id not in food_pagination:
            await callback.answer("Сессия истекла")
            return
        
        if data == f"food_exit_{user_id}":
            # Удаляем сообщение
            await callback.message.delete()
            # Удаляем данные пагинации
            if user_id in food_pagination:
                del food_pagination[user_id]
            return
        
        current_index = food_pagination[user_id].current_food_index
        total_foods = len(food_pagination[user_id].foods)
        
        if data == f"food_prev_{user_id}" and current_index > 0:
            new_index = current_index - 1
        elif data == f"food_next_{user_id}" and current_index < total_foods - 1:
            new_index = current_index + 1
        else:
            await callback.answer()
            return
        
        await show_food_page(callback.message, user_id, new_index)
        await callback.answer()
        
    except Exception as e:
        await callback.answer(f"Ошибка: {str(e)}")

# 4) Топ 5 блюд
@router.message(Command("rating"), F.from_user.id.in_(admins))
async def show_top_food(message: Message):
    try:
        response = await supabase_client.get_all_food_reviews()
        food_data = response.data
        
        if not food_data:
            await message.answer("Нет данных о блюдах")
            return
        
        # Группируем по блюдам и считаем статистику
        food_stats = {}
        for item in food_data:
            food_name = item['name']
            mark = int(item['mark'])  # Преобразуем в число
            
            if food_name not in food_stats:
                food_stats[food_name] = {'marks': [], 'count': 0}
            
            food_stats[food_name]['marks'].append(mark)
            food_stats[food_name]['count'] += 1
        
        # Вычисляем средние оценки
        top_foods = []
        for food_name, stats in food_stats.items():
            avg_mark = sum(stats['marks']) / len(stats['marks'])
            top_foods.append({
                'name': food_name,
                'avg_mark': round(avg_mark, 2),
                'count': stats['count']
            })
        
        # Сортируем по убыванию средней оценки
        top_foods.sort(key=lambda x: x['avg_mark'], reverse=True)
        top_5 = top_foods[:5]
        
        # Формируем ответ (без разметки)
        response_text = "🏆 Топ-5 блюд по средней оценке:\n\n"
        
        for i, food in enumerate(top_5, 1):
            stars = "⭐" * int(food['avg_mark'])
            response_text += f"{i}. {food['name']}\n"
            response_text += f"   Оценка: {food['avg_mark']} {stars}\n"
            response_text += f"   Количество оценок: {food['count']}\n\n"
        
        await message.answer(response_text)
        
    except Exception as e:
        error_msg = f"Ошибка при получении рейтинга: {str(e)}"
        await message.answer(error_msg)

# Обработчик для кнопок без действия
@router.callback_query(F.data == "no_action")
async def handle_no_action(callback: CallbackQuery):
    await callback.answer()