import os
from supabase import create_client, Client
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

class SupabaseClient:
    def __init__(self):
        self.client: Client = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )
    
    # Users methods
    async def create_user(self, user_data):
        """Создает нового пользователя"""
        try:
            return self.client.table("users").insert(user_data).execute()
        except Exception as e:
            logger.error(f"Ошибка создания пользователя: {e}")
            raise
    
    async def get_user(self, telegram_id):
        """Получает пользователя по telegram_id"""
        try:
            return self.client.table("users").select("*").eq("telegram_id", telegram_id).execute()
        except Exception as e:
            logger.error(f"Ошибка получения пользователя: {e}")
            raise
    
    async def user_exists(self, telegram_id):
        """Проверяет существует ли пользователь"""
        response = await self.get_user(telegram_id)
        return len(response.data) > 0
    
    async def update_user_info(self, telegram_id, full_name, class_name):
        """Обновляет информацию о пользователе"""
        try:
            return self.client.table("users").update({
                "full_name": full_name,
                "class": class_name,
                "has_profile": True
            }).eq("telegram_id", telegram_id).execute()
        except Exception as e:
            logger.error(f"Ошибка обновления пользователя: {e}")
            raise
    
    # Survey methods
    async def create_survey(self, survey_data):
        """Создает новую анкету"""
        try:
            return self.client.table("surveys").insert(survey_data).execute()
        except Exception as e:
            logger.error(f"Ошибка создания анкеты: {e}")
            raise
    
    async def get_user_surveys(self, telegram_id):
        """Получает анкеты пользователя"""
        try:
            return self.client.table("surveys").select("*").eq("telegram_id", telegram_id).execute()
        except Exception as e:
            logger.error(f"Ошибка получения анкет: {e}")
            raise
    
    # Meal ratings methods
    async def add_meal_rating(self, rating_data):
        """Добавляет оценку блюда"""
        try:
            return self.client.table("meal_ratings").insert(rating_data).execute()
        except Exception as e:
            logger.error(f"Ошибка добавления оценки блюда: {e}")
            raise
    
    async def get_meal_ratings_by_survey(self, survey_id):
        """Получает оценки блюд по ID анкеты"""
        try:
            return self.client.table("meal_ratings").select("*").eq("survey_id", survey_id).execute()
        except Exception as e:
            logger.error(f"Ошибка получения оценок блюд: {e}")
            raise
    
    # Comments methods
    async def add_meal_comment(self, comment_data):
        """Добавляет комментарий к блюду"""
        try:
            return self.client.table("meal_comments").insert(comment_data).execute()
        except Exception as e:
            logger.error(f"Ошибка добавления комментария: {e}")
            raise

    # Statistics methods
    async def get_all_surveys(self):
        """Получает все анкеты"""
        try:
            return self.client.table("surveys").select("*, users(*), meal_ratings(*), meal_comments(*)").execute()
        except Exception as e:
            logger.error(f"Ошибка получения анкет: {e}")
            raise
    
    async def get_daily_stats(self, date=None):
        """Получает статистику за день"""
        try:
            if not date:
                from datetime import datetime
                date = datetime.now().date().isoformat()
            
            return self.client.table("surveys").select("*, users(*), meal_ratings(*), meal_comments(*)").eq("date", date).execute()
        except Exception as e:
            logger.error(f"Ошибка получения дневной статистики: {e}")
            raise
        
    async def update_survey(self, survey_id, survey_data):
        """Обновляет существующую анкету"""
        try:
            return self.client.table("surveys").update(survey_data).eq("id", survey_id).execute()
        except Exception as e:
            logger.error(f"❌ Error updating survey: {e}")
            raise

    async def delete_meal_ratings(self, survey_id):
        """Удаляет все оценки блюд для анкеты"""
        try:
            return self.client.table("meal_ratings").delete().eq("survey_id", survey_id).execute()
        except Exception as e:
            logger.error(f"❌ Error deleting meal ratings: {e}")
            raise

    async def delete_meal_comments(self, survey_id):
        """Удаляет все комментарии для анкеты"""
        try:
            return self.client.table("meal_comments").delete().eq("survey_id", survey_id).execute()
        except Exception as e:
            logger.error(f"❌ Error deleting meal comments: {e}")
            raise
    async def get_user_survey(self, telegram_id):
        """Получает анкету пользователя по telegram_id"""
        try:
            return self.client.table("surveys").select("*").eq("telegram_id", telegram_id).execute()
        except Exception as e:
            logger.error(f"❌ Error getting user survey: {e}")
            raise
    async def get_surveys_with_details(self):
        """Получает анкеты с деталями (для статистики)"""
        try:
            # Получаем отдельно данные и соединяем в коде
            surveys_response = self.client.table("surveys").select("*").execute()
            users_response = self.client.table("users").select("*").execute()
            meal_ratings_response = self.client.table("meal_ratings").select("*").execute()
            meal_comments_response = self.client.table("meal_comments").select("*").execute()
            
            # Собираем данные вручную
            result_data = []
            for survey in surveys_response.data:
                # Находим пользователя
                user = next((u for u in users_response.data if u['telegram_id'] == survey['telegram_id']), {})
                
                # Находим оценки блюд для этой анкеты
                survey_ratings = [r for r in meal_ratings_response.data if r['survey_id'] == survey['id']]
                
                # Находим комментарии для этой анкеты
                survey_comments = [c for c in meal_comments_response.data if c['survey_id'] == survey['id']]
                
                survey_with_details = {
                    **survey,
                    'user': user,
                    'meal_ratings': survey_ratings,
                    'meal_comments': survey_comments
                }
                result_data.append(survey_with_details)
            
            # Создаем объект с атрибутом data для совместимости
            class Result:
                def __init__(self, data):
                    self.data = data
            
            return Result(result_data)
            
        except Exception as e:
            logger.error(f"❌ Error getting surveys with details: {e}")
            raise

    async def get_all_surveys(self):
        """Получает все анкеты"""
        try:
            return self.client.table("surveys").select("*").execute()
        except Exception as e:
            logger.error(f"❌ Error getting all surveys: {e}")
            raise

    async def get_all_users(self):
        """Получает всех пользователей"""
        try:
            return self.client.table("users").select("*").execute()
        except Exception as e:
            logger.error(f"❌ Error getting all users: {e}")
            raise

    async def get_all_meal_ratings(self):
        """Получает все оценки блюд"""
        try:
            return self.client.table("meal_ratings").select("*").execute()
        except Exception as e:
            logger.error(f"❌ Error getting all meal ratings: {e}")
            raise

    async def get_all_meal_comments(self):
        """Получает все комментарии к блюдам"""
        try:
            return self.client.table("meal_comments").select("*").execute()
        except Exception as e:
            logger.error(f"❌ Error getting all meal comments: {e}")
            raise
supabase_client = SupabaseClient()