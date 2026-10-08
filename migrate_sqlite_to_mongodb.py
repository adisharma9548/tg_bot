"""
SQLite to MongoDB Migration Utility
Transfers all existing users, sessions, preferences, and batch task states from SQLite to MongoDB Atlas.
Idempotent and safe to run multiple times.
"""

import os
import sys
import sqlite3
import datetime
from config import MONGODB_URI, DB_NAME, USERS_COLLECTION, BATCH_TASKS_COLLECTION, mask_mongodb_uri

SQLITE_PATH = os.path.join("database", "bot.db")


def run_migration():
    print("\n" + "=" * 60)
    print("      TELEGRAM BOT: SQLITE TO MONGODB ATLAS MIGRATOR")
    print("=" * 60)

    if not os.path.exists(SQLITE_PATH):
        print(f"[-] No SQLite database found at '{SQLITE_PATH}'. Nothing to migrate.")
        return

    if not MONGODB_URI:
        print("[-] Error: MONGODB_URI (or DB_URI) is not configured in .env or environment.")
        sys.exit(1)

    print(f"[*] Target MongoDB: {mask_mongodb_uri(MONGODB_URI)}")
    print(f"[*] Database Name:  {DB_NAME}")
    print(f"[*] Users Target:   {USERS_COLLECTION}")
    print(f"[*] Tasks Target:   {BATCH_TASKS_COLLECTION}")
    print(f"[*] Reading SQLite: {SQLITE_PATH}\n")

    # 1. Connect to SQLite
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    # 2. Connect to MongoDB (using synchronous pymongo for CLI script)
    try:
        from pymongo import MongoClient
        mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        mongo_client[DB_NAME].command("ping")
        print("[+] Successfully connected to MongoDB Atlas!")
    except Exception as e:
        print(f"[-] Failed to connect to MongoDB Atlas: {e}")
        sys.exit(1)

    mongo_db = mongo_client[DB_NAME]
    users_col = mongo_db[USERS_COLLECTION]
    batch_col = mongo_db[BATCH_TASKS_COLLECTION]

    users_found = 0
    users_migrated = 0
    tasks_found = 0
    tasks_migrated = 0
    errors = 0

    # 3. Migrate Users Table
    try:
        sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if sqlite_cur.fetchone():
            sqlite_cur.execute("SELECT * FROM users")
            user_rows = sqlite_cur.fetchall()
            users_found = len(user_rows)

            for row in user_rows:
                try:
                    u_dict = dict(row)
                    user_id = int(u_dict["id"])

                    doc = {
                        "_id": user_id,
                        "id": user_id,
                        "name": u_dict.get("name") or "",
                        "session": u_dict.get("session"),
                        "api_id": u_dict.get("api_id"),
                        "api_hash": u_dict.get("api_hash"),
                        "thumb": u_dict.get("thumb"),
                        "caption": u_dict.get("caption"),
                        "upload_as_doc": int(u_dict.get("upload_as_doc") or 0),
                        "silent_mode": int(u_dict.get("silent_mode") or 0),
                        "to_saved": int(u_dict.get("to_saved") or 0),
                        "prefix": u_dict.get("prefix"),
                        "removals": u_dict.get("removals"),
                        "updated_at": datetime.datetime.now(datetime.timezone.utc)
                    }

                    users_col.update_one(
                        {"_id": user_id},
                        {"$set": doc},
                        upsert=True
                    )
                    users_migrated += 1
                except Exception as e:
                    print(f"[-] Error migrating user {u_dict.get('id')}: {e}")
                    errors += 1
    except Exception as e:
        print(f"[-] Error querying SQLite users: {e}")
        errors += 1

    # 4. Migrate Batch Tasks Table
    try:
        sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='batch_tasks'")
        if sqlite_cur.fetchone():
            sqlite_cur.execute("SELECT * FROM batch_tasks")
            task_rows = sqlite_cur.fetchall()
            tasks_found = len(task_rows)

            for row in task_rows:
                try:
                    t_dict = dict(row)
                    user_id = int(t_dict["user_id"])

                    doc = {
                        "_id": user_id,
                        "user_id": user_id,
                        "link_prefix": t_dict.get("link_prefix"),
                        "from_id": int(t_dict.get("from_id") or 0),
                        "to_id": int(t_dict.get("to_id") or 0),
                        "last_id": int(t_dict.get("last_id") or 0),
                        "chat_id": str(t_dict.get("chat_id") or ""),
                        "task_type": str(t_dict.get("task_type") or "batch"),
                        "updated_at": datetime.datetime.now(datetime.timezone.utc)
                    }

                    batch_col.update_one(
                        {"_id": user_id},
                        {"$set": doc},
                        upsert=True
                    )
                    tasks_migrated += 1
                except Exception as e:
                    print(f"[-] Error migrating task for user {t_dict.get('user_id')}: {e}")
                    errors += 1
    except Exception as e:
        print(f"[-] Error querying SQLite batch_tasks: {e}")
        errors += 1

    # 5. Create Indexes
    try:
        users_col.create_index([("id", 1)], unique=True)
        users_col.create_index([("session", 1)], sparse=True)
        batch_col.create_index([("user_id", 1)], unique=True)
        print("[+] Created MongoDB unique and sparse indexes successfully.")
    except Exception as e:
        print(f"[-] Note on indexes: {e}")

    sqlite_conn.close()
    mongo_client.close()

    # 6. Final Summary Report
    print("\n" + "=" * 60)
    print("                 MIGRATION SUMMARY")
    print("=" * 60)
    print(f"  • Users found in SQLite:        {users_found}")
    print(f"  • Users migrated to MongoDB:    {users_migrated}")
    print(f"  • Batch tasks found in SQLite:  {tasks_found}")
    print(f"  • Batch tasks migrated:         {tasks_migrated}")
    print(f"  • Errors encountered:           {errors}")
    print("=" * 60)
    if errors == 0:
        print("[SUCCESS] All data has been successfully synchronized to MongoDB Atlas!")
    else:
        print("[WARNING] Migration completed with some errors. Review logs above.")
    print(f"Original SQLite database preserved at '{SQLITE_PATH}'.\n")


if __name__ == "__main__":
    run_migration()
