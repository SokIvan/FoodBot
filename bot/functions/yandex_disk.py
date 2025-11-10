import yadisk
from datetime import datetime
from config import YANDEX_DISK_TOKEN
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class YandexDiskManager:
    def __init__(self):
        self.token = YANDEX_DISK_TOKEN
        self.y = yadisk.YaDisk(token=self.token)
        
        # Проверяем токен при инициализации
        if not self.y.check_token():
            raise Exception("❌ Невалидный токен Яндекс.Диска")
        
        logger.info("✅ Яндекс.Диск подключен")

    async def get_today_images(self) -> List[Dict]:
        """Получает все изображения из папки сегодняшнего дня"""
        today_str = datetime.now().strftime("%d.%m.%Y")
        logger.info(f"📅 Ищем сегодняшние изображения: {today_str}")
        return await self.get_images_from_date_folder(today_str)

    async def get_images_from_date_folder(self, date_str: str) -> List[Dict]:
        """
        Получает все изображения из папки конкретной даты
        """
        logger.info(f"🔍 Ищем папку с датой: '{date_str}'")
        
        try:
            # Ищем папку FoodSchool64 в корне
            root_items = list(self.y.listdir("/"))
            food_school_folder = None
            
            for item in root_items:
                if item.type == "dir" and item.name == "FoodSchool64":
                    food_school_folder = item
                    break
            
            if not food_school_folder:
                logger.error("❌ Папка FoodSchool64 не найдена")
                return []
            
            # Ищем папку с датой в FoodSchool64
            food_school_items = list(self.y.listdir(food_school_folder.path))
            target_folder = None
            
            for item in food_school_items:
                if item.type == "dir" and item.name == date_str:
                    target_folder = item
                    break
            
            if not target_folder:
                logger.error(f"❌ Папка с датой '{date_str}' не найдена")
                return []
            
            logger.info(f"✅ Найдена папка: {target_folder.path}")
            
            # Получаем все файлы из папки с датой
            folder_items = list(self.y.listdir(target_folder.path))
            images = []
            
            for item in folder_items:
                if item.type == "file" and self._is_image_file(item.name):
                    try:
                        download_url = self.y.get_download_link(item.path)
                        
                        images.append({
                            "name": item.name.rsplit('.', 1)[0],  # Без расширения
                            "full_name": item.name,
                            "download_url": download_url,
                            "size": item.size,
                            "date": date_str
                        })
                        logger.info(f"✅ Добавлено изображение: {item.name}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка получения ссылки для {item.name}: {e}")
            
            logger.info(f"📷 Найдено изображений: {len(images)}")
            return images
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения изображений: {e}")
            return []

    async def get_latest_images(self) -> List[Dict]:
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
            
            # Получаем все папки с датами в FoodSchool64
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
            
            logger.info(f"🆕 Используем самую свежую папку: {latest_folder['name']}")
            return await self.get_images_from_date_folder(latest_folder["name"])
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения последних изображений: {e}")
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

# Global instance
yandex_disk = YandexDiskManager()