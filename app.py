"""
Web Health Check Service for AWS Elastic Beanstalk / Docker / Cloud Hosting
Official Maintainer: @No_MOORESINPS
Official Bot: https://t.me/chessvideosbot (@chessvideosbot)
"""

import os
import time
from flask import Flask, jsonify
from config import DYNAMODB_TABLE_NAME, AWS_DEFAULT_REGION

app = Flask(__name__)
BOOT_TIME = time.time()


def check_database_health() -> str:
    """Verifies AWS DynamoDB or local storage connectivity."""
    try:
        import boto3
        client = boto3.client("dynamodb", region_name=AWS_DEFAULT_REGION)
        client.describe_table(TableName=DYNAMODB_TABLE_NAME)
        return "aws_dynamodb_connected"
    except Exception as e:
        err_str = str(e)
        if "ResourceNotFoundException" in err_str:
            return "aws_dynamodb_ready"
        elif "AccessDenied" in err_str:
            return "local_sqlite_fallback (aws_iam_policy_pending)"
        elif os.path.exists("database/bot.db"):
            return "local_sqlite_fallback"
        return f"storage_status ({type(e).__name__})"


@app.route("/")
@app.route("/health")
def health():
    """AWS Elastic Beanstalk & ALB Health Check Endpoint."""
    db_status = check_database_health()
    uptime_sec = int(time.time() - BOOT_TIME)
    is_ok = ("connected" in db_status) or ("sqlite" in db_status) or ("ready" in db_status)
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
