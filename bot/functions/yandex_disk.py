# yandex_disk.py
import yadisk
from datetime import datetime, timezone, timedelta
from config import YANDEX_DISK_TOKEN
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class YandexDiskManager:
    def __init__(self):
        self.token = YANDEX_DISK_TOKEN
        self.y = yadisk.YaDisk(token=self.token)
        
        # Храним только дату последней проверки, а не все данные
        self.last_check_date = None
        self.cached_meals = None  # Только текущие блюда, не накапливаем
        
        if not self.y.check_token():
            raise Exception("❌ Невалидный токен Яндекс.Диска")

    def _get_moscow_time(self):
        """Получает текущее время по Москве"""
        msk_offset = timedelta(hours=3)  # UTC+3
        utc_now = datetime.now(timezone.utc)
        return utc_now.astimezone(timezone(msk_offset))

    def _is_new_day(self):
        """Проверяет, наступил ли новый день (после 8:00 МСК)"""
        moscow_time = self._get_moscow_time()
        current_date = moscow_time.date()
        
        # Если сегодня еще не проверяли И сейчас после 8:00
        if self.last_check_date != current_date and moscow_time.hour >= 8:
            logger.info(f"🔄 Новый день! Текущее время МСК: {moscow_time.strftime('%d.%m.%Y %H:%M')}")
            return True
        
        return False

    async def get_today_meals(self) -> List[Dict]:
        """Получает блюда за сегодня с минимальным использованием памяти"""
        # Проверяем, нужно ли обновить данные (новый день после 8:00 МСК)
        if self._is_new_day() or self.cached_meals is None:
            logger.info("🔄 Проверяем Яндекс.Диск (первая проверка дня)")
            self.cached_meals = await self._fetch_actual_meals()
            self.last_check_date = self._get_moscow_time().date()
            logger.info(f"✅ Данные обновлены для {self.last_check_date}")
        else:
            logger.info("✅ Используем кэшированные данные (одна запись в памяти)")
        
        return self.cached_meals

    async def _fetch_actual_meals(self) -> List[Dict]:
        """Получает актуальные данные с Яндекс.Диска"""
        today_str = self._get_moscow_time().strftime("%d.%m.%Y")
        return await self._get_meals_for_date_internal(today_str)

    async def get_meals_for_date(self, date_str: str) -> List[Dict]:
        """Получает блюда для конкретной даты (без кэширования)"""
        logger.info(f"🔄 Получаем блюда для даты: {date_str}")
        return await self._get_meals_for_date_internal(date_str)

    async def _get_meals_for_date_internal(self, date_str: str) -> List[Dict]:
        """Внутренний метод для получения блюд для даты"""
        meal_types = ["первое", "второе", "напиток"]
        all_meals = []
        
        # Проверяем существует ли папка для указанной даты
        date_folder_path = f"/FoodSchool64/{date_str}"
        try:
            self.y.get_meta(date_folder_path)
            folder_exists = True
            logger.info(f"✅ Папка для даты {date_str} найдена")
        except yadisk.exceptions.PathNotFoundError:
            logger.info(f"❌ Папка для даты {date_str} не найдена")
            folder_exists = False
        
        if folder_exists:
            for meal_type in meal_types:
                meal = await self._get_meal_from_folder(date_str, meal_type)
                if meal:
                    all_meals.append(meal)
                    logger.info(f"✅ Найдено фото для {meal_type}")
                else:
                    # Добавляем тип блюда даже если фото нет
                    all_meals.append({
                        "type": meal_type,
                        "name": meal_type.capitalize(),
                        "full_name": f"{meal_type}.jpg",
                        "download_url": None,
                        "size": 0,
                        "date": date_str,
                        "has_image": False
                    })
                    logger.info(f"✅ Добавлен тип блюда без фото: {meal_type}")
        else:
            # Только типы блюд без фото
            logger.info(f"📝 Создаем стандартные типы блюд без фото для {date_str}")
            for meal_type in meal_types:
                all_meals.append({
                    "type": meal_type,
                    "name": meal_type.capitalize(),
                    "full_name": f"{meal_type}.jpg",
                    "download_url": None,
                    "size": 0,
                    "date": date_str,
                    "has_image": False
                })
                
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
                logger.info(f"Папка типа блюда не найдена: {meal_folder_path}")
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
                            "name": meal_type.capitalize(),
                            "full_name": item.name,
                            "download_url": download_url,
                            "size": item.size,
                            "date": date_str,
                            "has_image": True
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

    def force_refresh(self):
        """Принудительное обновление кэша - полностью сбрасываем"""
        logger.info("🔄 Принудительное обновление кэша - полный сброс")
        self.cached_meals = None
        self.last_check_date = None

    async def refresh_and_get_meals(self) -> List[Dict]:
        """Принудительное обновление и получение актуальных данных"""
        logger.info("🔄 Принудительное обновление и получение актуальных данных")
        self.force_refresh()
        # Получаем актуальные данные, игнорируя кэш
        meals = await self._fetch_actual_meals()
        self.cached_meals = meals
        self.last_check_date = self._get_moscow_time().date()
        logger.info(f"✅ Данные принудительно обновлены для {self.last_check_date}")
        return meals

# Global instance
yandex_disk = YandexDiskManager()