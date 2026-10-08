import os
from flask import Flask, jsonify
from config import MONGODB_URI, DB_NAME

app = Flask(__name__)


def check_database_health() -> str:
    """Verifies MongoDB connectivity without exposing credentials."""
    if not MONGODB_URI:
        return "local_sqlite_fallback"
    try:
        from pymongo import MongoClient
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=2500)
        client[DB_NAME or "sih26044"].command("ping")
        client.close()
        return "connected"
    except Exception as e:
        return f"unreachable ({type(e).__name__})"


@app.route("/")
@app.route("/health")
def health():
    db_status = check_database_health()
    is_ok = db_status in ("connected", "local_sqlite_fallback")
    return jsonify({
        "status": "ok" if is_ok else "degraded",
        "bot": "running",
        "database": db_status
    }), 200 if is_ok else 503


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
