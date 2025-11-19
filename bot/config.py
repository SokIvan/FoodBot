import os
from dotenv import load_dotenv

load_dotenv()

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Yandex Disk
YANDEX_DISK_TOKEN = os.getenv("YANDEX_DISK_TOKEN")

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

#Admins
admins = [2068329433,2051689878]
ADMINS = admins
BLOCKED_BOT_IDS = [8505284786]