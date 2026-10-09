"""
Web Health Check Service for AWS Elastic Beanstalk / Docker / Cloud Hosting
Maintained by @No_MOORESINPS
Official Bot: https://t.me/chessvideosbot (@chessvideosbot)
"""

import os
import time
from flask import Flask, jsonify, render_template_string
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
def index():
    """Root endpoint for AWS Elastic Beanstalk health check and visitor landing."""
    db_status = check_database_health()
    uptime_sec = int(time.time() - BOOT_TIME)
    uptime_str = f"{uptime_sec // 3600}h {(uptime_sec % 3600) // 60}m {uptime_sec % 60}s"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Save Restricted Content Bot — AWS Service Status</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: #0f172a;
            color: #f8fafc;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
            box-sizing: border-box;
        }}
        .card {{
            background: #1e293b;
            border-radius: 16px;
            padding: 32px;
            max-width: 500px;
            width: 100%;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
            border: 1px solid #334155;
            text-align: center;
        }}
        h1 {{
            font-size: 1.5rem;
            margin-bottom: 8px;
            color: #38bdf8;
        }}
        .badge {{
            display: inline-block;
            background: #059669;
            color: #ecfdf5;
            padding: 6px 14px;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 600;
            margin-bottom: 24px;
        }}
        .info-table {{
            width: 100%;
            text-align: left;
            margin-bottom: 24px;
            border-collapse: collapse;
        }}
        .info-table td {{
            padding: 10px 0;
            border-bottom: 1px solid #334155;
            font-size: 0.95rem;
        }}
        .info-table td:first-child {{
            color: #94a3b8;
        }}
        .info-table td:last-child {{
            font-weight: 600;
            text-align: right;
            color: #f1f5f9;
        }}
        .btn {{
            display: inline-block;
            background: #2563eb;
            color: #ffffff;
            text-decoration: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            transition: background 0.2s;
        }}
        .btn:hover {{
            background: #1d4ed8;
        }}
        .footer {{
            margin-top: 20px;
            font-size: 0.8rem;
            color: #64748b;
        }}
    </style>
</head>
<body>
    <div class="card">
        <h1>Save Restricted Content Bot</h1>
        <div class="badge">● AWS Production Active</div>
        <table class="info-table">
            <tr>
                <td>Service Status</td>
                <td><span style="color: #4ade80;">Healthy (200 OK)</span></td>
            </tr>
            <tr>
                <td>Database</td>
                <td>{db_status}</td>
            </tr>
            <tr>
                <td>Uptime</td>
                <td>{uptime_str}</td>
            </tr>
            <tr>
                <td>Official Bot</td>
                <td><a href="https://t.me/chessvideosbot" style="color: #38bdf8; text-decoration: none;">@chessvideosbot</a></td>
            </tr>
            <tr>
                <td>Maintainer</td>
                <td>@No_MOORESINPS</td>
            </tr>
        </table>
        <a href="https://t.me/chessvideosbot" class="btn" target="_blank">Open Official Bot on Telegram</a>
        <div class="footer">Proprietary build maintained by @No_MOORESINPS</div>
    </div>
</body>
</html>"""
    return render_template_string(html)


@app.route("/health")
def health():
    """AWS Elastic Beanstalk Target Group & ALB Health Check Endpoint."""
    db_status = check_database_health()
    is_ok = db_status in ("connected", "local_sqlite_fallback")
    return jsonify({
        "status": "healthy" if is_ok else "degraded",
        "service": "Save Restricted Content Bot",
        "database": db_status,
        "official_bot": "@chessvideosbot",
        "maintainer": "@No_MOORESINPS",
        "uptime_seconds": int(time.time() - BOOT_TIME)
    }), 200 if is_ok else 503


@app.route("/status")
def status():
    """Detailed operational metrics."""
    db_status = check_database_health()
    return jsonify({
        "bot": "running",
        "database": db_status,
        "environment": "aws_production",
        "official_bot": "https://t.me/chessvideosbot",
        "owner": "@No_MOORESINPS"
    }), 200


if __name__ == "__main__":
    # AWS Elastic Beanstalk default port is 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
