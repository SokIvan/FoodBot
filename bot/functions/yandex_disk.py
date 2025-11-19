import yadisk
from datetime import datetime, timedelta
from config import YANDEX_DISK_TOKEN
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class YandexDiskManager:
    def __init__(self):
        self.token = YANDEX_DISK_TOKEN
        self.y = yadisk.YaDisk(token=self.token)
        
        # Кэш для меню
        self.cache = {}
        self.cache_timeout = 900  # 15 минут кэша
        
        if not self.y.check_token():
            raise Exception("❌ Невалидный токен Яндекс.Диска")

    async def get_today_meals(self) -> List[Dict]:
        """Получает все блюда за сегодня из новых папок"""
        today_str = datetime.now().strftime("%d.%m.%Y")
        cache_key = f"today_meals_{today_str}"
        
        # Проверяем кэш
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self.cache_timeout):
                logger.info("✅ Используем кэшированные блюда")
                return cached_data
        
        # Получаем свежие данные из всех папок
        logger.info("🔄 Обновляем блюда из Яндекс.Диска")
        all_meals = []
        meal_types = ["первое", "второе", "напиток"]
        
        for meal_type in meal_types:
            meal = await self._get_meal_from_folder(today_str, meal_type)
            if meal:
                all_meals.append(meal)
        
        self.cache[cache_key] = (all_meals, datetime.now())
        return all_meals

    async def _get_meal_from_folder(self, date_str: str, meal_type: str) -> Dict:
        """Получает блюдо из папки конкретного типа"""
        try:
            meal_folder_name = meal_type.capitalize()
            meal_folder_path = f"/FoodSchool64/{date_str}/{meal_folder_name}"
            
            # Проверяем существование папки
            try:
                self.y.get_meta(meal_folder_path)
            except yadisk.exceptions.PathNotFoundError:
                logger.info(f"Папка не найдена: {meal_folder_path}")
                return None
            
            # Получаем все файлы из папки
            folder_items = list(self.y.listdir(meal_folder_path))
            
            # Берем первое изображение
            for item in folder_items:
                if item.type == "file" and self._is_image_file(item.name):
                    try:
                        download_url = self.y.get_download_link(item.path)
                        
                        return {
                            "type": meal_type,
                            "name": meal_type.capitalize(),  # "Первое", "Второе", "Напиток"
                            "full_name": item.name,
                            "download_url": download_url,
                            "size": item.size,
                            "date": date_str
                        }
                    except Exception as e:
                        logger.error(f"Ошибка получения ссылки для {item.name}: {e}")
                        continue
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения блюда для {meal_type}: {e}")
            return None

    def _is_image_file(self, filename: str) -> bool:
        """Проверяет, является ли файл изображением"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.jfif'}
        filename_lower = filename.lower()
        return any(filename_lower.endswith(ext) for ext in image_extensions)

    def clear_cache(self):
        """Очищает кэш"""
        self.cache.clear()
        logger.info("🧹 Кэш очищен")

# Global instance
yandex_disk = YandexDiskManager()