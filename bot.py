"""
Telegram Save Restricted Content Bot
Official Maintainer: @No_MOORESINPS
Official Bot: https://t.me/chessvideosbot (@chessvideosbot)
"""

import os
import sqlite3
from pyrogram import Client
import pyrogram.storage.file_storage as fs
from config import API_ID, API_HASH, BOT_TOKEN, STRING_SESSION, LOGIN_SYSTEM
from database.db import db
from guard import verify_environment

# =====================================================================
# High-Concurrency SQLite & Storage Protection Patch
# Fixes "database is locked" errors during pipelined lookahead transfers
# and high-worker parallel operations.
# =====================================================================
async def _patched_file_storage_open(self):
    path = self.database
    file_exists = path.is_file()

    # Use 60s timeout instead of Pyrogram's default 1s
    self.conn = sqlite3.connect(str(path), timeout=60, check_same_thread=False)
    try:
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA busy_timeout=60000;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
    except Exception:
        pass

    if not file_exists:
        self.create()
    else:
        self.update()

    try:
        with self.conn:
            self.conn.execute("VACUUM")
    except Exception:
        pass

fs.FileStorage.open = _patched_file_storage_open


def configure_sqlite_pragmas():
    """Ensures existing SQLite database files are initialized with WAL mode and busy timeouts."""
    for db_file in ["bot_session.session", "database/bot.db"]:
        if os.path.exists(db_file):
            try:
                conn = sqlite3.connect(db_file, timeout=60)
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout=60000;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                conn.close()
            except Exception:
                pass

configure_sqlite_pragmas()


if STRING_SESSION and LOGIN_SYSTEM == False:
    UserClient = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION, in_memory=True)
else:
    UserClient = None

# Global user client for single-session configuration
# (Multi-account sessions are managed dynamically via database/db.py)

class Bot(Client):

    def __init__(self):
        super().__init__(
            "bot_session",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            plugins=dict(root="plugins"),
            workers=20,
            sleep_threshold=60,
            max_concurrent_transmissions=2
        )

      
    async def start(self):
        verify_environment()
        try:
            await db.ping()
        except Exception as e:
            print(f"Database ping warning: {e}", flush=True)
        if UserClient and not UserClient.is_connected:
            try:
                await UserClient.start()
            except Exception as e:
                print(f"UserClient start error: {e}", flush=True)
        await super().start()
        print('Bot Started Successfully', flush=True)

    async def stop(self, *args):
        try:
            await db.close()
        except Exception:
            pass
        if UserClient and UserClient.is_connected:
            try:
                await UserClient.stop()
            except Exception:
                pass
        await super().stop()
        print('Bot Stopped Bye', flush=True)

if __name__ == "__main__":
    verify_environment()
    if not API_ID or not API_HASH or not BOT_TOKEN:
        print("\n" + "=" * 60)
        print(" [!] Missing required configuration!")
        print(" Please provide API_ID, API_HASH, and BOT_TOKEN in your .env file.")
        print("=" * 60 + "\n")
        exit(1)
    bot = Bot()
    bot.run()
