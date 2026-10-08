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

SUPPORT_HANDLE: str = get_env_flexible("SUPPORT_HANDLE", "@LALAJIIIIIIIIII")

def resolve_db_path() -> str:
    raw = get_env_flexible("DB_PATH")
    if raw:
        path = os.path.abspath(raw) if not os.path.isabs(raw) else raw
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except Exception:
            pass
        return path

    # Check explicit volume environment variables first and create dir
    for env_var in ["RAILWAY_VOLUME_MOUNT_PATH", "DATA_DIR"]:
        val = os.getenv(env_var)
        if val:
            try:
                os.makedirs(val, exist_ok=True)
                target = os.path.abspath(os.path.join(val, "bot_database.sqlite"))
                return target
            except Exception:
                pass

    # Check common mounted volume paths if they exist and are writable
    for mount in ["/data", "/app/data", "/mnt/data"]:
        if os.path.exists(mount) and os.path.isdir(mount):
            try:
                # Test write access
                test_file = os.path.join(mount, ".perm_test")
                with open(test_file, "w") as f:
                    f.write("ok")
                os.remove(test_file)
                return os.path.abspath(os.path.join(mount, "bot_database.sqlite"))
            except Exception:
                pass

    # Local directory default
    local_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "bot_database.sqlite"))
    return local_path

DB_PATH: str = resolve_db_path()
REQUIRED_CHANNEL: str = get_env_flexible("REQUIRED_CHANNEL", "https://t.me/LALAJIIIIIIIIII")
TUTORIAL_VIDEO_URL: str = get_env_flexible("TUTORIAL_VIDEO_URL", "https://t.me/LALAJIIIIIIIIII")


