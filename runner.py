"""
Unified AWS Production Process Supervisor
Runs both the Flask ALB Health Check Service and the Telegram MTProto Bot.
Author: @No_MOORESINPS
Official Bot: @chessvideosbot (https://t.me/chessvideosbot)
"""

import os
import sys
import threading
import signal
import time
from guard import verify_environment, print_banner
from config import validate_config, mask_mongodb_uri, MONGODB_URI
from app import app
from bot import Bot


def run_web_server(port: int):
    """Runs the Flask health check server on the specified port."""
    print(f"[AWS Web Server] Starting HTTP Health Check server on 0.0.0.0:{port}...", flush=True)
    try:
        # Run Flask WSGI server without debugger / reloader in background thread
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"[AWS Web Server] Error: {e}", file=sys.stderr, flush=True)


def main():
    print_banner()

    # 1. Validate configuration
    is_valid, msg = validate_config()
    if not is_valid:
        print(msg, file=sys.stderr, flush=True)
        sys.exit(1)

    # 2. Determine Web Port (AWS Elastic Beanstalk defaults to 5000)
    web_port = int(os.environ.get("PORT", 5000))

    # 3. Start HTTP Health Check Web Service in daemon thread
    web_thread = threading.Thread(target=run_web_server, args=(web_port,), daemon=True)
    web_thread.start()

    # Small pause to ensure web server socket is bound
    time.sleep(1)
    print(f"[AWS Runner] Web health endpoint active at http://0.0.0.0:{web_port}/health", flush=True)
    print(f"[AWS Runner] Database target: {mask_mongodb_uri(MONGODB_URI)}", flush=True)
    print("[AWS Runner] Launching Pyrogram Telegram Bot Client...", flush=True)

    # 4. Initialize and run Pyrogram Bot Client
    bot = Bot()

    def handle_signal(sig, frame):
        print(f"\n[AWS Runner] Received termination signal ({sig}). Gracefully shutting down...", flush=True)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        bot.run()
    except (KeyboardInterrupt, SystemExit):
        print("[AWS Runner] Bot process stopped.", flush=True)
    except Exception as e:
        print(f"[AWS Runner] Fatal bot error: {e}", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
