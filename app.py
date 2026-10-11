"""
Web Health Check Service for AWS Elastic Beanstalk / Docker / Cloud Hosting
Official Maintainer: @No_MOORESINPS
Official Bot: https://t.me/chessvideosbot (@chessvideosbot)
"""

import os
import time
from flask import Flask, jsonify
from config import MONGODB_URI, DB_NAME

app = Flask(__name__)
BOOT_TIME = time.time()


def check_database_health() -> str:
    """Verifies MongoDB connectivity without exposing credentials."""
    if not MONGODB_URI:
        return "local_sqlite_fallback"
    try:
        from pymongo import MongoClient
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=2000)
        client[DB_NAME or "sih26044"].command("ping")
        client.close()
        return "connected"
    except Exception as e:
        return f"unreachable ({type(e).__name__})"


@app.route("/")
@app.route("/health")
def health():
    """AWS Elastic Beanstalk & ALB Health Check Endpoint."""
    db_status = check_database_health()
    uptime_sec = int(time.time() - BOOT_TIME)
    is_ok = db_status in ("connected", "local_sqlite_fallback")
    return jsonify({
        "status": "healthy" if is_ok else "degraded",
        "service": "Save Restricted Content Bot",
        "database": db_status,
        "official_bot": "@chessvideosbot",
        "maintainer": "@No_MOORESINPS",
        "uptime_seconds": uptime_sec
    }), 200 if is_ok else 503


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
