import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Login feature: True enables /login inside bot; False requires STRING_SESSION
login_sys_str = os.environ.get('LOGIN_SYSTEM', 'True').strip().lower()
LOGIN_SYSTEM = login_sys_str in ('true', '1', 'yes')

if not LOGIN_SYSTEM:
    STRING_SESSION = os.environ.get("STRING_SESSION", "").strip()
else:
    STRING_SESSION = None

# Bot token from @BotFather
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

# Telegram API credentials from https://my.telegram.org
api_id_val = os.environ.get("API_ID", "").strip()
API_ID = int(api_id_val) if api_id_val.isdigit() else 0

API_HASH = os.environ.get("API_HASH", "").strip()

# Admin Username / ID (Configured for @No_MOORESINPS)
admins_val = os.environ.get("ADMINS", "No_MOORESINPS").strip()
if admins_val:
    if admins_val.isdigit():
        ADMINS = int(admins_val)
    else:
        ADMINS = admins_val.lstrip("@")
else:
    ADMINS = "No_MOORESINPS"

# Optional Channel ID to upload downloaded content to (leave blank to send directly to user)
CHANNEL_ID = os.environ.get("CHANNEL_ID", "").strip()

# Database Configuration (Supports both MongoDB Atlas and SQLite fallback)
MONGODB_URI = (os.environ.get("MONGODB_URI") or os.environ.get("DB_URI", "")).strip()
DB_URI = MONGODB_URI
DB_NAME = os.environ.get("DB_NAME", "sih26044").strip()
USERS_COLLECTION = os.environ.get("USERS_COLLECTION", "tg_users").strip()
BATCH_TASKS_COLLECTION = os.environ.get("BATCH_TASKS_COLLECTION", "tg_batch_tasks").strip()

# Delay in seconds to prevent Telegram flood wait limits
wait_time_val = os.environ.get("WAITING_TIME", "10").strip()
WAITING_TIME = int(wait_time_val) if wait_time_val.isdigit() else 10

# Send error messages in chat
err_msg_val = os.environ.get('ERROR_MESSAGE', 'True').strip().lower()
ERROR_MESSAGE = err_msg_val in ('true', '1', 'yes')


def mask_mongodb_uri(uri: str) -> str:
    """Masks credentials in MongoDB URI for safe logging."""
    if not uri:
        return "<not set>"
    import re
    return re.sub(r":([^@]+)@", r":****@", uri)


def validate_config():
    """Validates required environment variables for bot execution."""
    missing = []
    if not API_ID:
        missing.append("API_ID")
    if not API_HASH:
        missing.append("API_HASH")
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not LOGIN_SYSTEM and not STRING_SESSION:
        missing.append("STRING_SESSION (required when LOGIN_SYSTEM=False)")

    if missing:
        error_msg = (
            "\n" + "=" * 65 + "\n"
            " [!] MISSING REQUIRED CONFIGURATION!\n"
            f" Please set the following in your environment or .env file:\n"
            + "\n".join(f"   • {m}" for m in missing)
            + "\n" + "=" * 65 + "\n"
        )
        return False, error_msg
    return True, "Config valid"
