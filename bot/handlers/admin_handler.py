import os
import tempfile
from aiogram import Router, types
from aiogram.filters import Command
from config import ADMINS
import pandas as pd
import io
import logging
from datetime import datetime
from database.db_supabase import supabase_client
from aiogram.fsm.context import FSMContext

router = Router()
logger = logging.getLogger(__name__)

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMINS

# admin_handler.py - обновляем функцию get_statistics

@router.message(Command("stats"))
async def get_statistics(message: types.Message, state: FSMContext):
    """Генерация статистики в Excel для администраторов"""
    # Проверяем, не находится ли пользователь в процессе опроса
    current_state = await state.get_state()
    if current_state is not None:
        await message.answer(
            "⏳ *Вы находитесь в процессе оценки питания!*\n\n"
            "Завершите опрос или используйте /reset чтобы получить доступ к статистике.",
            parse_mode="Markdown"
        )
        return
    
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    if not supabase_client:
        await message.answer("❌ База данных не доступна.")
        return
    
    # Создаем временный файл
    temp_file = None
    
    try:
        await message.answer("📊 Формирую отчет... Это может занять некоторое время.")
        
        # Получаем данные отдельными запросами
        surveys_response = await supabase_client.get_all_surveys()
        users_response = await supabase_client.get_all_users()
        meal_ratings_response = await supabase_client.get_all_meal_ratings()
        meal_comments_response = await supabase_client.get_all_meal_comments()
        
        surveys_data = surveys_response.data
        users_data = users_response.data
        meal_ratings_data = meal_ratings_response.data
        meal_comments_data = meal_comments_response.data
        
        if not surveys_data:
            await message.answer("📭 Нет данных для отчета.")
            return
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.xlsx', delete=False) as tmp:
            temp_file = tmp.name
            
            with pd.ExcelWriter(temp_file, engine='xlsxwriter') as writer:
                workbook = writer.book
                
                # Лист с основными данными опросов
                basic_data = []
                for survey in surveys_data:
                    user = next((u for u in users_data if u['telegram_id'] == survey['telegram_id']), {})
                    
                    # Определяем статус питания
                    eats_at_school = survey.get('eats_at_school', False)
                    status = "Да" if eats_at_school else "Нет"
                    
                    # Формируем причину если не питается
                    reason = ""
                    if not eats_at_school:
                        reason = survey.get('no_school_reason', 'Причина не указана')
                        if not reason:
                            reason = "Причина не указана"
                    
                    basic_data.append({
                        'ID анкеты': survey.get('id'),
                        'Дата': survey.get('date'),
                        'Telegram ID': survey.get('telegram_id'),
                        'ФИО': user.get('full_name', 'Не указано'),
                        'Класс': user.get('class', 'Не указан'),
                        'Питается в школе': status,
                        'Причина непосещения': reason,
                        'Общая оценка': survey.get('overall_satisfaction', 'Не оценено'),
                        'Общий комментарий': survey.get('overall_comment', '')[:100] + '...' if survey.get('overall_comment') else ''
                    })
                
                basic_df = pd.DataFrame(basic_data)
                basic_df.to_excel(writer, sheet_name='Опросы', index=False)
                
                # Лист с пользователями
                users_df = pd.DataFrame(users_data)
                if not users_df.empty:
                    users_df.to_excel(writer, sheet_name='Пользователи', index=False)
                
                # Лист с оценками блюд
                if meal_ratings_data:
                    ratings_data = []
                    for rating in meal_ratings_data:
                        # Находим анкету для этой оценки
                        survey = next((s for s in surveys_data if s['id'] == rating['survey_id']), {})
                        ratings_data.append({
                            'ID анкеты': rating.get('survey_id'),
                            'Дата': survey.get('date', 'Неизвестно'),
                            'Тип блюда': rating.get('meal_type'),
                            'Оценка': rating.get('rating')
                        })
                    
                    ratings_df = pd.DataFrame(ratings_data)
                    ratings_df.to_excel(writer, sheet_name='Оценки блюд', index=False)
                    
                    # Сводка по оценкам блюд
                    if not ratings_df.empty:
                        pivot_df = ratings_df.groupby('Тип блюда').agg({
                            'Оценка': ['mean', 'count', 'min', 'max']
                        }).round(2)
                        pivot_df.to_excel(writer, sheet_name='Сводка по блюдам')
                
                # Лист с комментариями
                if meal_comments_data:
                    comments_data = []
                    for comment in meal_comments_data:
                        # Находим анкету для этого комментария
                        survey = next((s for s in surveys_data if s['id'] == comment['survey_id']), {})
                        comments_data.append({
                            'ID анкеты': comment.get('survey_id'),
                            'Дата': survey.get('date', 'Неизвестно'),
                            'Тип блюда': comment.get('meal_type'),
                            'Причина': comment.get('reason_comment', '')[:200] + '...',
                            'Альтернатива': comment.get('alternative_comment', '')[:200] + '...'
                        })
                    
                    comments_df = pd.DataFrame(comments_data)
                    comments_df.to_excel(writer, sheet_name='Комментарии', index=False)
                
                # НОВЫЙ ЛИСТ: Статистика по непосещающим столовую
                non_eaters_data = []
                for survey in surveys_data:
                    if not survey.get('eats_at_school', True):
                        user = next((u for u in users_data if u['telegram_id'] == survey['telegram_id']), {})
                        reason = survey.get('no_school_reason', '')
                        
                        non_eaters_data.append({
                            'Дата': survey.get('date'),
                            'Telegram ID': survey.get('telegram_id'),
                            'ФИО': user.get('full_name', 'Не указано'),
                            'Класс': user.get('class', 'Не указан'),
                            'Причина': reason,
                            'Длина причины': len(reason) if reason else 0
                        })
                
                if non_eaters_data:
                    non_eaters_df = pd.DataFrame(non_eaters_data)
                    non_eaters_df.to_excel(writer, sheet_name='Непосещающие столовую', index=False)
                    
                    # Анализ причин
                    reasons_analysis = non_eaters_df['Причина'].value_counts().head(10)
                    reasons_df = pd.DataFrame({
                        'Причина': reasons_analysis.index,
                        'Количество': reasons_analysis.values
                    })
                    reasons_df.to_excel(writer, sheet_name='Анализ причин', index=False)
                
                # Статистика и графики
                worksheet = workbook.add_worksheet('Статистика')
                
                # Базовая статистика
                total_surveys = len(surveys_data)
                total_users = len(users_data)
                eaters_count = sum(1 for s in surveys_data if s.get('eats_at_school', True))
                non_eaters_count = total_surveys - eaters_count
                
                stats_data = {
                    'Метрика': [
                        'Всего опросов',
                        'Всего пользователей', 
                        'Всего оценок блюд',
                        'Всего комментариев',
                        'Питаются в столовой',
                        'Не питаются в столовой',
                        'Процент непосещающих',
                        'Средняя общая оценка',
                        'Дата отчета'
                    ],
                    'Значение': [
                        total_surveys,
                        total_users,
                        len(meal_ratings_data),
                        len(meal_comments_data),
                        eaters_count,
                        non_eaters_count,
                        f"{(non_eaters_count/total_surveys*100):.1f}%" if total_surveys > 0 else "0%",
                        basic_df[basic_df['Общая оценка'] != 'Не оценено']['Общая оценка'].mean() if not basic_df.empty else 0,
                        datetime.now().strftime('%d.%m.%Y %H:%M')
                    ]
                }
                
                stats_df = pd.DataFrame(stats_data)
                stats_df.to_excel(writer, sheet_name='Статистика', index=False)
                
                # Простые графики
                if not basic_df.empty and 'Общая оценка' in basic_df.columns:
                    chart_sheet = workbook.add_worksheet('Графики')
                    
                    # Распределение общих оценок
                    rating_counts = basic_df[basic_df['Общая оценка'] != 'Не оценено']['Общая оценка'].value_counts().sort_index()
                    
                    if not rating_counts.empty:
                        chart = workbook.add_chart({'type': 'column'})
                        chart.add_series({
                            'name': 'Количество оценок',
                            'categories': f'=Опросы!$H$2:$H${len(rating_counts)+1}',
                            'values': f'=Опросы!$H$2:$H${len(rating_counts)+1}',
                        })
                        chart.set_title({'name': 'Распределение общих оценок'})
                        chart_sheet.insert_chart('A1', chart)
                    
                    # Распределение по питанию в столовой
                    nutrition_counts = basic_df['Питается в школе'].value_counts()
                    if not nutrition_counts.empty:
                        chart2 = workbook.add_chart({'type': 'pie'})
                        chart2.add_series({
                            'name': 'Питание в столовой',
                            'categories': f'=Статистика!$A$6:$A$7',
                            'values': f'=Статистика!$B$6:$B$7',
                        })
                        chart2.set_title({'name': 'Распределение по питанию в столовой'})
                        chart_sheet.insert_chart('A20', chart2)
        
        # Читаем файл для отправки
        with open(temp_file, 'rb') as file:
            file_data = file.read()
        
        # Отправляем файл
        await message.answer_document(
            document=types.BufferedInputFile(
                file_data,
                filename=f"school_food_stats_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            ),
            caption="📊 *Статистика опросов школьного питания*\n\n"
                   "Файл содержит:\n"
                   "• Все опросы (с причинами непосещения)\n" 
                   "• Пользователей\n"
                   "• Оценки блюд\n"
                   "• Комментарии\n"
                   "• Непосещающих столовую\n"
                   "• Анализ причин\n"
                   "• Сводные таблицы\n"
                   "• Статистику и графики",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации статистики: {e}")
        await message.answer("❌ Произошла ошибка при генерации отчета.")
    
    finally:
        # УДАЛЯЕМ временный файл после отправки
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
                logger.info(f"🧹 Удален временный файл: {temp_file}")
            except Exception as e:
                logger.warning(f"Не удалось удалить временный файл {temp_file}: {e}")

# Обновляем также функцию get_daily_stats
@router.message(Command("daily_stats"))
async def get_daily_stats(message: types.Message, state: FSMContext):
    """Статистика за сегодня"""
    # Проверяем, не находится ли пользователь в процессе опроса
    current_state = await state.get_state()
    if current_state is not None:
        await message.answer(
            "⏳ *Вы находитесь в процессе оценки питания!*\n\n"
            "Завершите опрос или используйте /reset чтобы получить доступ к статистике.",
            parse_mode="Markdown"
        )
        return
    
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    if not supabase_client:
        await message.answer("❌ База данных не доступна.")
        return
    
    try:
        today = datetime.now().date().isoformat()
        today_stats = await supabase_client.get_daily_stats(today)
        stats_data = today_stats.data
        
        if not stats_data:
            await message.answer("📭 На сегодня нет данных.")
            return
        
        # Получаем дополнительные данные для расчетов
        all_ratings = await supabase_client.get_all_meal_ratings()
        today_ratings = [r for r in all_ratings.data if any(s['id'] == r['survey_id'] for s in stats_data)]
        
        total_surveys = len(stats_data)
        
        # Статистика по питанию в столовой
        eaters_count = sum(1 for s in stats_data if s.get('eats_at_school', True))
        non_eaters_count = total_surveys - eaters_count
        
        # Средняя общая оценка (только у тех, кто питается)
        overall_ratings = [s.get('overall_satisfaction', 0) for s in stats_data if s.get('overall_satisfaction') and s.get('eats_at_school', True)]
        avg_overall = sum(overall_ratings) / len(overall_ratings) if overall_ratings else 0
        
        # Средняя оценка блюд
        avg_meal = sum(r.get('rating', 0) for r in today_ratings) / len(today_ratings) if today_ratings else 0
        
        stats_text = (
            f"📊 *Статистика за сегодня* ({datetime.now().strftime('%d.%m.%Y')})\n\n"
            f"• Всего опросов: {total_surveys}\n"
            f"• Питаются в столовой: {eaters_count}\n"
            f"• Не питаются в столовой: {non_eaters_count}\n"
            f"• Средняя общая оценка: {avg_overall:.1f}/5\n"
            f"• Средняя оценка блюд: {avg_meal:.1f}/5\n"
            f"• Оценено блюд: {len(today_ratings)}\n\n"
            f"Для полного отчета используйте /stats"
        )
        
        await message.answer(stats_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Ошибка получения дневной статистики: {e}")
        await message.answer("❌ Ошибка получения статистики.")

# admin_handler.py - обновляем команду refresh_meals
@router.message(Command("refresh_meals"))
async def refresh_meals_cache(message: types.Message, state: FSMContext):
    """Принудительное обновление кэша блюд"""
    # Проверяем, не находится ли пользователь в процессе опроса
    current_state = await state.get_state()
    if current_state is not None:
        await message.answer(
            "⏳ *Вы находитесь в процессе оценки питания!*\n\n"
            "Завершите опрос или используйте /reset чтобы получить доступ к командам.",
            parse_mode="Markdown"
        )
        return
    
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    try:
        # Принудительно обновляем кэш и получаем АКТУАЛЬНЫЕ данные
        from functions.yandex_disk import yandex_disk
        meals = await yandex_disk.refresh_and_get_meals()
        
        # Формируем отчет
        meals_with_photos = [meal for meal in meals if meal.get('has_image')]
        meals_without_photos = [meal for meal in meals if not meal.get('has_image')]
        
        response_text = (
            "🔄 *Кэш блюд обновлен!*\n\n"
            f"• Всего блюд: {len(meals)}\n"
            f"• С фотографиями: {len(meals_with_photos)}\n"
            f"• Без фотографий: {len(meals_without_photos)}\n\n"
        )
        
        if meals_with_photos:
            response_text += "*Блюда с фото:*\n"
            for meal in meals_with_photos:
                response_text += f"  - {meal['name']}\n"
        
        if meals_without_photos:
            response_text += "\n*Блюда без фото:*\n"
            for meal in meals_without_photos:
                response_text += f"  - {meal['name']}\n"
        
        await message.answer(response_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"❌ Ошибка обновления кэша: {e}")
        await message.answer("❌ Произошла ошибка при обновлении кэша.")
