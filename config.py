import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()

# Admin IDs separated by comma in .env: e.g. "12345678,87654321"
raw_admin_ids = os.getenv("ADMIN_IDS", "").strip()
ADMIN_IDS: List[int] = [
    int(x.strip()) for x in raw_admin_ids.split(",") if x.strip().isdigit()
]

# Support username or contact link, e.g. "@YourSupportUser" or "https://t.me/YourSupportUser"
SUPPORT_HANDLE: str = os.getenv("SUPPORT_HANDLE", "@AdminSupport").strip()

# Database path
DB_PATH: str = os.getenv("DB_PATH", "bot_database.sqlite").strip()
