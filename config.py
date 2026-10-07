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

# Database: Leave DB_URI blank to use local SQLite database on your device (database/bot.db)
DB_URI = os.environ.get("DB_URI", "").strip()
DB_NAME = os.environ.get("DB_NAME", "theaditya_db").strip()

# Delay in seconds to prevent Telegram flood wait limits
wait_time_val = os.environ.get("WAITING_TIME", "10").strip()
WAITING_TIME = int(wait_time_val) if wait_time_val.isdigit() else 10

# Send error messages in chat
err_msg_val = os.environ.get('ERROR_MESSAGE', 'True').strip().lower()
ERROR_MESSAGE = err_msg_val in ('true', '1', 'yes')
