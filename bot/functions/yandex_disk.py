import requests
from datetime import datetime, timedelta
from config import YANDEX_DISK_TOKEN, YANDEX_DISK_FOLDER_URL
from typing import List, Dict, Optional

class YandexDiskManager:
    def __init__(self):
        self.token = YANDEX_DISK_TOKEN
        self.base_url = "https://cloud-api.yandex.net/v1/disk/resources"
        self.headers = {"Authorization": f"OAuth {self.token}"}
    
    async def get_folder_contents(self, folder_path: str = "") -> Optional[Dict]:
        """Получает содержимое папки (публичной или приватной)"""
        try:
            if folder_path.startswith('http'):  # Публичная папка
                response = requests.get(
                    "https://cloud-api.yandex.net/v1/disk/public/resources",
                    params={"public_key": folder_path}
                )
            else:  # Приватная папка
                response = requests.get(
                    f"{self.base_url}",
                    params={"path": folder_path},
                    headers=self.headers
                )
            
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Error getting folder contents: {e}")
            return None
    
    async def get_date_folders(self) -> List[Dict]:
        """Получает список всех папок с датами из корневой папки"""
        root_data = await self.get_folder_contents(YANDEX_DISK_FOLDER_URL)
        date_folders = []
        
        if root_data and "_embedded" in root_data:
            for item in root_data["_embedded"]["items"]:
                if item["type"] == "dir" and self._is_date_folder(item["name"]):
                    date_folders.append({
                        "name": item["name"],
                        "path": item["path"],
                        "date": self._parse_date(item["name"])
                    })
        
        # Сортируем по дате (новые сверху)
        return sorted(date_folders, key=lambda x: x["date"], reverse=True)
    
    async def get_images_from_date_folder(self, date_str: str = None) -> List[Dict]:
        """
        Получает все изображения из папки конкретной даты
        
        Args:
            date_str: Дата в формате "DD.MM.YYYY". Если None - берет сегодняшнюю дату
        """
        if date_str is None:
            date_str = datetime.now().strftime("%d.%m.%Y")
        
        # Ищем папку с указанной датой
        date_folders = await self.get_date_folders()
        target_folder = next((f for f in date_folders if f["name"] == date_str), None)
        
        if not target_folder:
            print(f"Папка с датой {date_str} не найдена")
            return []
        
        # Получаем содержимое папки с датой
        folder_data = await self.get_folder_contents(target_folder["path"])
        return await self._extract_images_from_folder(folder_data)
    
    async def get_today_images(self) -> List[Dict]:
        """Получает все изображения из папки сегодняшнего дня"""
        today_str = datetime.now().strftime("%d.%m.%Y")
        return await self.get_images_from_date_folder(today_str)
    
    async def get_latest_images(self) -> List[Dict]:
        """Получает изображения из самой свежей папки (на случай если сегодняшней нет)"""
        date_folders = await self.get_date_folders()
        
        if not date_folders:
            return []
        
        # Берем самую свежую папку
        latest_folder = date_folders[0]
        folder_data = await self.get_folder_contents(latest_folder["path"])
        images = await self._extract_images_from_folder(folder_data)
        
        # Добавляем информацию о дате к каждому изображению
        for img in images:
            img["date"] = latest_folder["name"]
        
        return images
    
    async def _extract_images_from_folder(self, folder_data: Dict) -> List[Dict]:
        """Извлекает изображения из данных папки"""
        images = []
        
        if folder_data and "_embedded" in folder_data:
            for item in folder_data["_embedded"]["items"]:
                if (item["type"] == "file" and 
                    item.get("mime_type", "").startswith("image/")):
                    
                    # Убираем расширение для красивого отображения
                    name = item["name"].rsplit('.', 1)[0]
                    
                    images.append({
                        "name": name,
                        "full_name": item["name"],
                        "preview_url": item.get("preview"),
                        "download_url": await self._get_direct_download_url(item["path"]),
                        "size": item.get("size", 0)
                    })
        
        return images
    
    async def _get_direct_download_url(self, file_path: str) -> str:
        """Получает прямую ссылку для скачивания файла"""
        try:
            if file_path.startswith('disk:'):  # Приватный файл
                response = requests.get(
                    f"{self.base_url}/download",
                    params={"path": file_path},
                    headers=self.headers
                )
            else:  # Публичный файл
                response = requests.get(
                    f"https://cloud-api.yandex.net/v1/disk/public/resources/download",
                    params={
                        "public_key": YANDEX_DISK_FOLDER_URL,
                        "path": file_path
                    }
                )
            
            if response.status_code == 200:
                return response.json()["href"]
        except Exception as e:
            print(f"Error getting download URL: {e}")
        
        return ""
    
    def _is_date_folder(self, folder_name: str) -> bool:
        """Проверяет, является ли имя папки датой в формате DD.MM.YYYY"""
        try:
            datetime.strptime(folder_name, "%d.%m.%Y")
            return True
        except ValueError:
            return False
    
    def _parse_date(self, date_str: str) -> datetime:
        """Парсит строку даты в datetime объект"""
        return datetime.strptime(date_str, "%d.%m.%Y")
    
    async def get_available_dates(self) -> List[str]:
        """Возвращает список доступных дат (для будущего использования)"""
        date_folders = await self.get_date_folders()
        return [folder["name"] for folder in date_folders]

# Global instance
yandex_disk = YandexDiskManager()