# Don't Remove Credit Tg - @VJ_Bots
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN, STRING_SESSION, LOGIN_SYSTEM
from database.db import db

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
        try:
            await db.ping()
        except Exception as e:
            print(f"Database ping warning: {e}", flush=True)
        await super().start()
        print('Bot Started Successfully', flush=True)

    async def stop(self, *args):
        try:
            await db.close()
        except Exception:
            pass
        await super().stop()
        print('Bot Stopped Bye', flush=True)

if __name__ == "__main__":
    if not API_ID or not API_HASH or not BOT_TOKEN:
        print("\n" + "=" * 60)
        print(" [!] Missing required configuration!")
        print(" Please provide API_ID, API_HASH, and BOT_TOKEN in your .env file.")
        print("=" * 60 + "\n")
        exit(1)
    bot = Bot()
    bot.run()

# Don't Remove Credit Tg - @VJ_Bots
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01
