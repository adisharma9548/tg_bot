# Don't Remove Credit Tg - @VJ_Bots
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

import logging
from pyrogram import Client
from config import (
    API_ID,
    API_HASH,
    BOT_TOKEN,
    STRING_SESSION,
    LOGIN_SYSTEM,
    MONGODB_URI,
    mask_mongodb_uri,
    validate_config
)
from database.db import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Bot")

if STRING_SESSION is not None and LOGIN_SYSTEM == False:
    TechVJUser = Client("TechVJ", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)
    TechVJUser.start()
else:
    TechVJUser = None


class Bot(Client):

    def __init__(self):
        super().__init__(
            "techvj login",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            plugins=dict(root="TechVJ"),
            workers=150,
            sleep_threshold=5
        )

    async def start(self):
        logger.info(f"Verifying Database connection to {mask_mongodb_uri(MONGODB_URI)}...")
        try:
            await db.ping()
            await db.create_indexes()
            logger.info("Database Connected & Indexes Verified Successfully")
        except Exception as e:
            logger.critical(f"FATAL: Database connection failed: {e}")
            raise SystemExit(1)

        await super().start()
        print('Bot Started Successfully', flush=True)
        logger.info("Telegram Bot Started and Listening for Events")

    async def stop(self, *args):
        await db.close()
        await super().stop()
        print('Bot Stopped Bye', flush=True)
        logger.info("Bot Stopped Gracefully")


if __name__ == "__main__":
    is_valid, err_msg = validate_config()
    if not is_valid:
        print(err_msg, flush=True)
        exit(1)

    bot = Bot()
    bot.run()

# Don't Remove Credit Tg - @VJ_Bots
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01
