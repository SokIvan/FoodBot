import os
from dotenv import load_dotenv

load_dotenv()

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Yandex Disk
YANDEX_DISK_TOKEN = os.getenv("YANDEX_DISK_TOKEN")
YANDEX_DISK_FOLDER_URL = os.getenv("YANDEX_DISK_FOLDER_URL")

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")