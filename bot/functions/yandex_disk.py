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

    async def get_today_images(self) -> List[Dict]:
        """Кэшированное получение сегодняшних изображений"""
        today_str = datetime.now().strftime("%d.%m.%Y")
        cache_key = f"today_{today_str}"
        
        # Проверяем кэш
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self.cache_timeout):
                logger.info("✅ Используем кэшированное меню")
                return cached_data
        
        # Получаем свежие данные
        logger.info("🔄 Обновляем меню из Яндекс.Диска")
        images = await self._get_images_from_date_folder(today_str)
        self.cache[cache_key] = (images, datetime.now())
        return images

    async def get_latest_images(self) -> List[Dict]:
        """Кэшированное получение последних изображений"""
        cache_key = "latest_images"
        
        # Проверяем кэш
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self.cache_timeout):
                return cached_data
        
        # Получаем свежие данные
        images = await self._get_latest_images_actual()
        self.cache[cache_key] = (images, datetime.now())
        return images

    async def _get_images_from_date_folder(self, date_str: str) -> List[Dict]:
        """Получает изображения из папки с датой (оптимизированно)"""
        try:
            # Всего 3 запроса к API независимо от количества фото!
            
            # 1. Проверяем существование папки с датой
            date_folder_path = f"/FoodSchool64/{date_str}"
            try:
                self.y.get_meta(date_folder_path)
            except yadisk.exceptions.PathNotFoundError:
                return []
            
            # 2. Получаем все файлы из папки
            folder_items = list(self.y.listdir(date_folder_path))
            
            images = []
            for item in folder_items:
                if item.type == "file" and self._is_image_file(item.name):
                    try:
                        # 3. Получаем ссылку для каждого файла
                        download_url = self.y.get_download_link(item.path)
                        
                        images.append({
                            "name": item.name.rsplit('.', 1)[0],
                            "full_name": item.name,
                            "download_url": download_url,
                            "size": item.size,
                            "date": date_str
                        })
                    except Exception:
                        continue
            
            return images
            
        except Exception as e:
            logger.error(f"Ошибка получения изображений: {e}")
            return []

    async def _get_latest_images_actual(self) -> List[Dict]:
        """Получает изображения из самой свежей папки"""
        try:
            # Ищем папку FoodSchool64
            root_items = list(self.y.listdir("/"))
            food_school_folder = None
            
            for item in root_items:
                if item.type == "dir" and item.name == "FoodSchool64":
                    food_school_folder = item
                    break
            
            if not food_school_folder:
                return []
            
            # Получаем все папки с датами
            food_school_items = list(self.y.listdir(food_school_folder.path))
            date_folders = []
            
            for item in food_school_items:
                if item.type == "dir" and self._is_date_folder(item.name):
                    date_folders.append({
                        "name": item.name,
                        "path": item.path,
                        "date": self._parse_date(item.name)
                    })
            
            if not date_folders:
                return []
            
            # Сортируем по дате и берем самую свежую
            date_folders.sort(key=lambda x: x["date"], reverse=True)
            latest_folder = date_folders[0]
            
            return await self._get_images_from_date_folder(latest_folder["name"])
            
        except Exception as e:
            logger.error(f"Ошибка получения последних изображений: {e}")
            return []

    def _is_date_folder(self, folder_name: str) -> bool:
        """Проверяет, является ли имя папки датой"""
        try:
            folder_name = folder_name.strip()
            datetime.strptime(folder_name, "%d.%m.%Y")
            return True
        except ValueError:
            return False

    def _is_image_file(self, filename: str) -> bool:
        """Проверяет, является ли файл изображением"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.jfif'}
        filename_lower = filename.lower()
        return any(filename_lower.endswith(ext) for ext in image_extensions)

    def _parse_date(self, date_str: str) -> datetime:
        """Парсит строку даты в datetime объект"""
        return datetime.strptime(date_str.strip(), "%d.%m.%Y")

    def clear_cache(self):
        """Очищает кэш (можно вызывать при смене дня)"""
        self.cache.clear()
        logger.info("🧹 Кэш очищен")

# Global instance
yandex_disk = YandexDiskManager()