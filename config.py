import os
import sys
from typing import List
from dotenv import load_dotenv

load_dotenv()

def get_env_flexible(key_name: str, default: str = "") -> str:
    # Try exact match
    val = os.getenv(key_name)
    if val:
        return val.strip().strip("'\"")
    # Try lowercase, uppercase, and common variants
    for k, v in os.environ.items():
        if k.upper() == key_name.upper():
            return v.strip().strip("'\"")
    return default

BOT_TOKEN: str = (
    get_env_flexible("BOT_TOKEN") 
    or get_env_flexible("TELEGRAM_BOT_TOKEN") 
    or get_env_flexible("TOKEN") 
    or get_env_flexible("TG_BOT_TOKEN")
)

raw_admin_ids = (
    get_env_flexible("ADMIN_IDS") 
    or get_env_flexible("ADMIN_ID") 
    or get_env_flexible("ADMINS")
)
ADMIN_IDS: List[int] = [
    int(x.strip()) for x in raw_admin_ids.split(",") if x.strip().isdigit()
]

SUPPORT_HANDLE: str = get_env_flexible("SUPPORT_HANDLE", "@AdminSupport")
DB_PATH: str = get_env_flexible("DB_PATH", "bot_database.sqlite")

