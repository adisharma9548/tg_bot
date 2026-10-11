"""
WSGI Application Entry Point for AWS Elastic Beanstalk
Points to the Flask application in app.py and supervises the Telegram Bot background worker.
Author: @No_MOORESINPS
Official Bot: https://t.me/chessvideosbot (@chessvideosbot)
"""

import os
import sys
import threading
import socket
from app import app as application

_bot_started = False
_lock_socket = None

def _start_bot_singleton():
    """
    Starts the Telegram Bot in a background thread with loopback socket mutex lock.
    Prevents multiple Gunicorn workers from spawning duplicate bot instances.
    """
    global _bot_started, _lock_socket
    if _bot_started:
        return

    # Check if required environment variables are present
    bot_token = os.environ.get("BOT_TOKEN")
    if not bot_token:
        print("[AWS application.py] Note: BOT_TOKEN not found in environment yet. Waiting for configuration.", flush=True)
        return

    try:
        # Acquire loopback socket lock on port 40498
        _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _lock_socket.bind(('127.0.0.1', 40498))
        _lock_socket.listen(1)
        print("[AWS application.py] Acquired bot singleton lock on 127.0.0.1:40498", flush=True)
    except socket.error:
        # Another worker process already acquired the lock and is running the bot!
        print("[AWS application.py] Bot worker already active in another process. Skipping.", flush=True)
        return

    def _worker():
        try:
            print("[AWS application.py] Launching Pyrogram Telegram Bot in background worker...", flush=True)
            from bot import Bot
            bot = Bot()
            bot.run()
        except Exception as e:
            print(f"[AWS application.py] Fatal bot worker exception: {e}", file=sys.stderr, flush=True)

    t = threading.Thread(target=_worker, daemon=True, name="TelegramBotSingleton")
    t.start()
    _bot_started = True

# Automatically attempt to launch bot when application module is loaded by Gunicorn/WSGI
if os.environ.get("BOT_TOKEN"):
    _start_bot_singleton()

if __name__ == "__main__":
    application.run()
