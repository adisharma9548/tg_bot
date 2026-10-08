import os
import sqlite3
import asyncio
import threading
import datetime
import logging
from config import (
    MONGODB_URI,
    DB_NAME,
    USERS_COLLECTION,
    BATCH_TASKS_COLLECTION,
    mask_mongodb_uri
)

logger = logging.getLogger("Database")


class MongoDatabase:
    """Production Asynchronous MongoDB Database for Telegram Bot."""

    def __init__(self, uri: str, database_name: str):
        import motor.motor_asyncio
        self.uri = uri
        self.database_name = database_name or "sih26044"
        self._client = motor.motor_asyncio.AsyncIOMotorClient(
            self.uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            maxPoolSize=50
        )
        self.db = self._client[self.database_name]
        self.users_col = self.db[USERS_COLLECTION]
        self.batch_tasks_col = self.db[BATCH_TASKS_COLLECTION]

    async def ping(self) -> bool:
        """Verifies MongoDB connectivity."""
        try:
            res = await self.db.command("ping")
            return bool(res and res.get("ok") == 1)
        except Exception as e:
            logger.error(f"MongoDB ping failed: {e}")
            raise

    async def create_indexes(self):
        """Creates indexes for fast queries and data uniqueness."""
        try:
            # Users indexes
            await self.users_col.create_index([("id", 1)], unique=True)
            await self.users_col.create_index([("session", 1)], sparse=True)
            # Batch tasks indexes
            await self.batch_tasks_col.create_index([("user_id", 1)], unique=True)
            logger.info("MongoDB indexes verified/created successfully.")
        except Exception as e:
            logger.warning(f"Error creating MongoDB indexes: {e}")

    async def close(self):
        """Gracefully closes MongoDB connections."""
        try:
            self._client.close()
            logger.info("MongoDB client connection closed.")
        except Exception:
            pass

    # ------------------ User Management ------------------

    async def add_user(self, id: int, name: str):
        """Idempotently adds a user or updates their name without overwriting settings."""
        await self.users_col.update_one(
            {"_id": int(id)},
            {
                "$set": {
                    "name": str(name or ""),
                    "updated_at": datetime.datetime.now(datetime.timezone.utc)
                },
                "$setOnInsert": {
                    "id": int(id),
                    "session": None,
                    "api_id": None,
                    "api_hash": None,
                    "thumb": None,
                    "caption": None,
                    "upload_as_doc": 0,
                    "silent_mode": 0,
                    "to_saved": 0,
                    "prefix": None,
                    "removals": None,
                    "created_at": datetime.datetime.now(datetime.timezone.utc)
                }
            },
            upsert=True
        )

    async def is_user_exist(self, id: int) -> bool:
        """Checks if a user exists in the database."""
        doc = await self.users_col.find_one({"_id": int(id)}, {"_id": 1})
        return doc is not None

    async def total_users_count(self) -> int:
        """Returns total registered bot users count."""
        return await self.users_col.count_documents({})

    async def get_all_users(self):
        """Asynchronous generator yielding all registered user documents."""
        cursor = self.users_col.find({})
        async for doc in cursor:
            if "id" not in doc:
                doc["id"] = doc["_id"]
            yield doc

    async def delete_user(self, user_id: int):
        """Deletes user record and associated batch tasks."""
        await self.users_col.delete_one({"_id": int(user_id)})
        await self.batch_tasks_col.delete_one({"_id": int(user_id)})

    async def _set_field(self, id: int, field: str, value):
        """Atomic upsert helper for updating a single field on a user document."""
        await self.users_col.update_one(
            {"_id": int(id)},
            {
                "$set": {
                    field: value,
                    "updated_at": datetime.datetime.now(datetime.timezone.utc)
                },
                "$setOnInsert": {
                    "id": int(id),
                    "created_at": datetime.datetime.now(datetime.timezone.utc)
                }
            },
            upsert=True
        )

    async def _get_field(self, id: int, field: str):
        """Helper to retrieve a single field value from a user document."""
        doc = await self.users_col.find_one({"_id": int(id)}, {field: 1})
        if doc and doc.get(field) is not None:
            return doc[field]
        return None

    # ------------------ Session Management ------------------

    async def set_session(self, id: int, session: str):
        await self._set_field(id, "session", session)

    async def get_session(self, id: int):
        return await self._get_field(id, "session")

    async def set_api_id(self, id: int, api_id):
        val = int(api_id) if api_id is not None and str(api_id).strip() != "" else None
        await self._set_field(id, "api_id", val)

    async def get_api_id(self, id: int):
        return await self._get_field(id, "api_id")

    async def set_api_hash(self, id: int, api_hash: str):
        await self._set_field(id, "api_hash", api_hash)

    async def get_api_hash(self, id: int):
        return await self._get_field(id, "api_hash")

    async def get_other_sessions(self, exclude_user_id: int = None):
        """
        Retrieves active sessions from all users except exclude_user_id.
        Enables multi-account session fallback without requiring SQLite.
        """
        query = {"session": {"$nin": [None, ""]}}
        if exclude_user_id:
            query["_id"] = {"$ne": int(exclude_user_id)}

        results = []
        cursor = self.users_col.find(query, {"id": 1, "_id": 1, "session": 1, "api_id": 1, "api_hash": 1})
        async for doc in cursor:
            uid = doc.get("id", doc.get("_id"))
            results.append((
                int(uid),
                doc.get("session"),
                doc.get("api_id"),
                doc.get("api_hash")
            ))
        return results

    # ------------------ Custom Thumbnail ------------------

    async def set_thumb(self, id: int, thumb_path: str):
        await self._set_field(id, "thumb", thumb_path)

    async def get_thumb(self, id: int):
        return await self._get_field(id, "thumb")

    async def del_thumb(self, id: int):
        await self._set_field(id, "thumb", None)

    # ------------------ Custom Caption ------------------

    async def set_caption(self, id: int, caption: str):
        await self._set_field(id, "caption", caption)

    async def get_caption(self, id: int):
        return await self._get_field(id, "caption")

    async def del_caption(self, id: int):
        await self._set_field(id, "caption", None)

    # ------------------ Mode Toggles ------------------

    async def set_upload_mode(self, id: int, as_doc: bool):
        await self._set_field(id, "upload_as_doc", 1 if as_doc else 0)

    async def get_upload_mode(self, id: int) -> bool:
        val = await self._get_field(id, "upload_as_doc")
        return bool(val)

    async def set_silent(self, id: int, silent: bool):
        await self._set_field(id, "silent_mode", 1 if silent else 0)

    async def get_silent(self, id: int) -> bool:
        val = await self._get_field(id, "silent_mode")
        return bool(val)

    async def set_to_saved(self, id: int, to_saved: bool):
        await self._set_field(id, "to_saved", 1 if to_saved else 0)

    async def get_to_saved(self, id: int) -> bool:
        val = await self._get_field(id, "to_saved")
        return bool(val)

    # ------------------ Filename Prefix & Cleaning ------------------

    async def set_prefix(self, id: int, prefix: str):
        await self._set_field(id, "prefix", prefix)

    async def get_prefix(self, id: int):
        return await self._get_field(id, "prefix")

    async def del_prefix(self, id: int):
        await self._set_field(id, "prefix", None)

    async def set_removals(self, id: int, removals: str):
        await self._set_field(id, "removals", removals)

    async def get_removals(self, id: int):
        raw = await self._get_field(id, "removals")
        if not raw:
            return []
        return [w.strip() for w in raw.split(",") if w.strip()]

    async def del_removals(self, id: int):
        await self._set_field(id, "removals", None)

    # ------------------ Batch Tasks (/resume) ------------------

    async def save_batch_task(self, user_id: int, link_prefix: str, from_id: int, to_id: int, last_id: int, chat_id, task_type: str):
        await self.batch_tasks_col.update_one(
            {"_id": int(user_id)},
            {
                "$set": {
                    "user_id": int(user_id),
                    "link_prefix": link_prefix,
                    "from_id": int(from_id),
                    "to_id": int(to_id),
                    "last_id": int(last_id),
                    "chat_id": str(chat_id),
                    "task_type": str(task_type),
                    "updated_at": datetime.datetime.now(datetime.timezone.utc)
                }
            },
            upsert=True
        )

    async def get_batch_task(self, user_id: int):
        doc = await self.batch_tasks_col.find_one({"_id": int(user_id)})
        if doc:
            doc["id"] = doc["_id"]
            return doc
        return None

    async def clear_batch_task(self, user_id: int):
        await self.batch_tasks_col.delete_one({"_id": int(user_id)})

    async def clear_all_user_settings(self, user_id: int):
        """Resets all custom settings for a user back to factory defaults."""
        await self.users_col.update_one(
            {"_id": int(user_id)},
            {
                "$set": {
                    "thumb": None,
                    "caption": None,
                    "upload_as_doc": 0,
                    "silent_mode": 0,
                    "to_saved": 0,
                    "prefix": None,
                    "removals": None,
                    "updated_at": datetime.datetime.now(datetime.timezone.utc)
                }
            }
        )
        await self.batch_tasks_col.delete_one({"_id": int(user_id)})


class SQLiteDatabase:
    """Local SQLite database fallback for offline local development only."""
    def __init__(self, db_path="database/bot.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY,
                            name TEXT,
                            session TEXT,
                            api_id INTEGER,
                            api_hash TEXT,
                            thumb TEXT,
                            caption TEXT,
                            upload_as_doc INTEGER DEFAULT 0,
                            silent_mode INTEGER DEFAULT 0,
                            to_saved INTEGER DEFAULT 0,
                            prefix TEXT,
                            removals TEXT
                        )
                    """)
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS batch_tasks (
                            user_id INTEGER PRIMARY KEY,
                            link_prefix TEXT,
                            from_id INTEGER,
                            to_id INTEGER,
                            last_id INTEGER,
                            chat_id TEXT,
                            task_type TEXT,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
            finally:
                conn.close()

    async def ping(self) -> bool:
        return True

    async def create_indexes(self):
        pass

    async def close(self):
        pass

    def _add_user(self, id, name):
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute(
                        "INSERT INTO users (id, name, session, api_id, api_hash, thumb, caption, upload_as_doc, silent_mode, to_saved, prefix, removals) "
                        "VALUES (?, ?, NULL, NULL, NULL, NULL, NULL, 0, 0, 0, NULL, NULL) "
                        "ON CONFLICT(id) DO UPDATE SET name = excluded.name",
                        (int(id), str(name or ""))
                    )
            finally:
                conn.close()

    async def add_user(self, id, name):
        await asyncio.to_thread(self._add_user, id, name)

    def _is_user_exist(self, id):
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM users WHERE id = ?", (int(id),))
                return cur.fetchone() is not None
            finally:
                conn.close()

    async def is_user_exist(self, id):
        return await asyncio.to_thread(self._is_user_exist, id)

    def _total_users_count(self):
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM users")
                row = cur.fetchone()
                return row[0] if row else 0
            finally:
                conn.close()

    async def total_users_count(self):
        return await asyncio.to_thread(self._total_users_count)

    def _get_all_users_list(self):
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute("SELECT * FROM users")
                rows = cur.fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    async def get_all_users(self):
        users_list = await asyncio.to_thread(self._get_all_users_list)
        for u in users_list:
            yield u

    def _delete_user(self, user_id):
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("DELETE FROM users WHERE id = ?", (int(user_id),))
            finally:
                conn.close()

    async def delete_user(self, user_id):
        await asyncio.to_thread(self._delete_user, user_id)

    def _set_field(self, id, field, value):
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (int(id),))
                    conn.execute(f"UPDATE users SET {field} = ? WHERE id = ?", (value, int(id)))
            finally:
                conn.close()

    def _get_field(self, id, field):
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute(f"SELECT {field} FROM users WHERE id = ?", (int(id),))
                row = cur.fetchone()
                if row and row[field] is not None:
                    return row[field]
                return None
            finally:
                conn.close()

    async def set_session(self, id, session):
        await asyncio.to_thread(self._set_field, id, "session", session)

    async def get_session(self, id):
        return await asyncio.to_thread(self._get_field, id, "session")

    async def set_api_id(self, id, api_id):
        val = int(api_id) if api_id is not None and str(api_id).strip() != "" else None
        await asyncio.to_thread(self._set_field, id, "api_id", val)

    async def get_api_id(self, id):
        return await asyncio.to_thread(self._get_field, id, "api_id")

    async def set_api_hash(self, id, api_hash):
        await asyncio.to_thread(self._set_field, id, "api_hash", api_hash)

    async def get_api_hash(self, id):
        return await asyncio.to_thread(self._get_field, id, "api_hash")

    def _get_other_sessions(self, exclude_user_id):
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute("SELECT id, session, api_id, api_hash FROM users WHERE session IS NOT NULL AND id != ?", (int(exclude_user_id),))
                return [(r["id"], r["session"], r["api_id"], r["api_hash"]) for r in cur.fetchall()]
            finally:
                conn.close()

    async def get_other_sessions(self, exclude_user_id: int):
        return await asyncio.to_thread(self._get_other_sessions, exclude_user_id)

    async def set_thumb(self, id, thumb_path):
        await asyncio.to_thread(self._set_field, id, "thumb", thumb_path)

    async def get_thumb(self, id):
        return await asyncio.to_thread(self._get_field, id, "thumb")

    async def del_thumb(self, id):
        await asyncio.to_thread(self._set_field, id, "thumb", None)

    async def set_caption(self, id, caption):
        await asyncio.to_thread(self._set_field, id, "caption", caption)

    async def get_caption(self, id):
        return await asyncio.to_thread(self._get_field, id, "caption")

    async def del_caption(self, id):
        await asyncio.to_thread(self._set_field, id, "caption", None)

    async def set_upload_mode(self, id, as_doc: bool):
        await asyncio.to_thread(self._set_field, id, "upload_as_doc", 1 if as_doc else 0)

    async def get_upload_mode(self, id) -> bool:
        val = await asyncio.to_thread(self._get_field, id, "upload_as_doc")
        return bool(val)

    async def set_silent(self, id, silent: bool):
        await asyncio.to_thread(self._set_field, id, "silent_mode", 1 if silent else 0)

    async def get_silent(self, id) -> bool:
        val = await asyncio.to_thread(self._get_field, id, "silent_mode")
        return bool(val)

    async def set_to_saved(self, id, to_saved: bool):
        await asyncio.to_thread(self._set_field, id, "to_saved", 1 if to_saved else 0)

    async def get_to_saved(self, id) -> bool:
        val = await asyncio.to_thread(self._get_field, id, "to_saved")
        return bool(val)

    async def set_prefix(self, id, prefix: str):
        await asyncio.to_thread(self._set_field, id, "prefix", prefix)

    async def get_prefix(self, id):
        return await asyncio.to_thread(self._get_field, id, "prefix")

    async def del_prefix(self, id):
        await asyncio.to_thread(self._set_field, id, "prefix", None)

    async def set_removals(self, id, removals: str):
        await asyncio.to_thread(self._set_field, id, "removals", removals)

    async def get_removals(self, id):
        raw = await asyncio.to_thread(self._get_field, id, "removals")
        if not raw:
            return []
        return [w.strip() for w in raw.split(",") if w.strip()]

    async def del_removals(self, id):
        await asyncio.to_thread(self._set_field, id, "removals", None)

    def _save_batch_task(self, user_id, link_prefix, from_id, to_id, last_id, chat_id, task_type):
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("""
                        INSERT INTO batch_tasks (user_id, link_prefix, from_id, to_id, last_id, chat_id, task_type, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(user_id) DO UPDATE SET
                            link_prefix = excluded.link_prefix,
                            from_id = excluded.from_id,
                            to_id = excluded.to_id,
                            last_id = excluded.last_id,
                            chat_id = excluded.chat_id,
                            task_type = excluded.task_type,
                            updated_at = CURRENT_TIMESTAMP
                    """, (int(user_id), link_prefix, int(from_id), int(to_id), int(last_id), str(chat_id), task_type))
            finally:
                conn.close()

    async def save_batch_task(self, user_id, link_prefix, from_id, to_id, last_id, chat_id, task_type):
        await asyncio.to_thread(self._save_batch_task, user_id, link_prefix, from_id, to_id, last_id, chat_id, task_type)

    def _get_batch_task(self, user_id):
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute("SELECT * FROM batch_tasks WHERE user_id = ?", (int(user_id),))
                row = cur.fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    async def get_batch_task(self, user_id):
        return await asyncio.to_thread(self._get_batch_task, user_id)

    def _clear_batch_task(self, user_id):
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("DELETE FROM batch_tasks WHERE user_id = ?", (int(user_id),))
            finally:
                conn.close()

    async def clear_batch_task(self, user_id):
        await asyncio.to_thread(self._clear_batch_task, user_id)

    def _clear_all_user_settings(self, user_id):
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("""
                        UPDATE users SET
                            thumb = NULL,
                            caption = NULL,
                            upload_as_doc = 0,
                            silent_mode = 0,
                            to_saved = 0,
                            prefix = NULL,
                            removals = NULL
                        WHERE id = ?
                    """, (int(user_id),))
                    conn.execute("DELETE FROM batch_tasks WHERE user_id = ?", (int(user_id),))
            finally:
                conn.close()

    async def clear_all_user_settings(self, user_id):
        await asyncio.to_thread(self._clear_all_user_settings, user_id)


# Primary Database Initialization
if MONGODB_URI and (MONGODB_URI.startswith("mongodb://") or MONGODB_URI.startswith("mongodb+srv://")):
    logger.info(f"Connecting to MongoDB Atlas at {mask_mongodb_uri(MONGODB_URI)} (DB: {DB_NAME})")
    db = MongoDatabase(MONGODB_URI, DB_NAME or "sih26044")
else:
    logger.warning(
        "[LOCAL DEVELOPMENT ONLY] MONGODB_URI not provided. Falling back to local SQLite database (database/bot.db).\n"
        "For production, please set MONGODB_URI=mongodb+srv://... in your environment."
    )
    db = SQLiteDatabase()
