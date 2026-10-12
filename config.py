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

# AWS Cloud Infrastructure Configuration
AWS_DEFAULT_REGION = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION") or "ap-south-1"
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME") or os.environ.get("AWS_DYNAMODB_TABLE") or "tg_users"
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "").strip()

# Delay in seconds to prevent Telegram flood wait limits
wait_time_val = os.environ.get("WAITING_TIME", "10").strip()
WAITING_TIME = int(wait_time_val) if wait_time_val.isdigit() else 10

# Send error messages in chat
err_msg_val = os.environ.get('ERROR_MESSAGE', 'True').strip().lower()
ERROR_MESSAGE = err_msg_val in ('true', '1', 'yes')


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
