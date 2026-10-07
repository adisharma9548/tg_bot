import os
import sqlite3
import asyncio
import threading
from config import DB_NAME, DB_URI

class SQLiteDatabase:
    """Local SQLite database stored directly on this device."""
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
                    for col_name, col_type in [
                        ("thumb", "TEXT"),
                        ("caption", "TEXT"),
                        ("upload_as_doc", "INTEGER DEFAULT 0"),
                        ("silent_mode", "INTEGER DEFAULT 0"),
                        ("to_saved", "INTEGER DEFAULT 0"),
                        ("prefix", "TEXT"),
                        ("removals", "TEXT")
                    ]:
                        try:
                            conn.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                        except sqlite3.OperationalError:
                            pass

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

    def new_user(self, id, name):
        return dict(
            id=id,
            name=name,
            session=None,
            api_id=None,
            api_hash=None,
            thumb=None,
            caption=None,
            upload_as_doc=0,
            silent_mode=0,
            to_saved=0,
            prefix=None,
            removals=None
        )

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
        async def _async_gen():
            for u in users_list:
                yield u
        return _async_gen()

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

    # Custom Thumbnail
    async def set_thumb(self, id, thumb_path):
        await asyncio.to_thread(self._set_field, id, "thumb", thumb_path)

    async def get_thumb(self, id):
        return await asyncio.to_thread(self._get_field, id, "thumb")

    async def del_thumb(self, id):
        await asyncio.to_thread(self._set_field, id, "thumb", None)

    # Custom Caption
    async def set_caption(self, id, caption):
        await asyncio.to_thread(self._set_field, id, "caption", caption)

    async def get_caption(self, id):
        return await asyncio.to_thread(self._get_field, id, "caption")

    async def del_caption(self, id):
        await asyncio.to_thread(self._set_field, id, "caption", None)

    # Upload Mode (0 = Video, 1 = Document)
    async def set_upload_mode(self, id, as_doc: bool):
        await asyncio.to_thread(self._set_field, id, "upload_as_doc", 1 if as_doc else 0)

    async def get_upload_mode(self, id) -> bool:
        val = await asyncio.to_thread(self._get_field, id, "upload_as_doc")
        return bool(val)

    # Silent Mode (0 = Sound, 1 = Silent)
    async def set_silent(self, id, silent: bool):
        await asyncio.to_thread(self._set_field, id, "silent_mode", 1 if silent else 0)

    async def get_silent(self, id) -> bool:
        val = await asyncio.to_thread(self._get_field, id, "silent_mode")
        return bool(val)

    # Send to Saved Messages (0 = Bot Chat, 1 = Saved Messages)
    async def set_to_saved(self, id, to_saved: bool):
        await asyncio.to_thread(self._set_field, id, "to_saved", 1 if to_saved else 0)

    async def get_to_saved(self, id) -> bool:
        val = await asyncio.to_thread(self._get_field, id, "to_saved")
        return bool(val)

    # Custom Filename Prefix
    async def set_prefix(self, id, prefix: str):
        await asyncio.to_thread(self._set_field, id, "prefix", prefix)

    async def get_prefix(self, id):
        return await asyncio.to_thread(self._get_field, id, "prefix")

    async def del_prefix(self, id):
        await asyncio.to_thread(self._set_field, id, "prefix", None)

    # Custom Word Removals
    async def set_removals(self, id, removals: str):
        await asyncio.to_thread(self._set_field, id, "removals", removals)

    async def get_removals(self, id):
        raw = await asyncio.to_thread(self._get_field, id, "removals")
        if not raw:
            return []
        return [w.strip() for w in raw.split(",") if w.strip()]

    async def del_removals(self, id):
        await asyncio.to_thread(self._set_field, id, "removals", None)

    # Batch Tasks (Auto-Resume)
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


if DB_URI and (DB_URI.startswith("mongodb://") or DB_URI.startswith("mongodb+srv://")):
    try:
        import motor.motor_asyncio
        class MongoDatabase:
            def __init__(self, uri, database_name):
                self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
                self.db = self._client[database_name]
                self.col = self.db.users

            def new_user(self, id, name):
                return dict(
                    id=id,
                    name=name,
                    session=None,
                    api_id=None,
                    api_hash=None,
                    thumb=None,
                    caption=None,
                    upload_as_doc=0,
                    silent_mode=0,
                    to_saved=0,
                    prefix=None,
                    removals=None
                )
            
            async def add_user(self, id, name):
                user = self.new_user(id, name)
                await self.col.insert_one(user)
            
            async def is_user_exist(self, id):
                user = await self.col.find_one({'id': int(id)})
                return bool(user)
            
            async def total_users_count(self):
                count = await self.col.count_documents({})
                return count

            async def get_all_users(self):
                return self.col.find({})

            async def delete_user(self, user_id):
                await self.col.delete_many({'id': int(user_id)})

            async def set_session(self, id, session):
                await self.col.update_one({'id': int(id)}, {'$set': {'session': session}})

            async def get_session(self, id):
                user = await self.col.find_one({'id': int(id)})
                return user.get('session') if user else None

            async def set_api_id(self, id, api_id):
                await self.col.update_one({'id': int(id)}, {'$set': {'api_id': api_id}})

            async def get_api_id(self, id):
                user = await self.col.find_one({'id': int(id)})
                return user.get('api_id') if user else None

            async def set_api_hash(self, id, api_hash):
                await self.col.update_one({'id': int(id)}, {'$set': {'api_hash': api_hash}})

            async def get_api_hash(self, id):
                user = await self.col.find_one({'id': int(id)})
                return user.get('api_hash') if user else None

            async def set_thumb(self, id, thumb_path):
                await self.col.update_one({'id': int(id)}, {'$set': {'thumb': thumb_path}})

            async def get_thumb(self, id):
                user = await self.col.find_one({'id': int(id)})
                return user.get('thumb') if user else None

            async def del_thumb(self, id):
                await self.col.update_one({'id': int(id)}, {'$set': {'thumb': None}})

            async def set_caption(self, id, caption):
                await self.col.update_one({'id': int(id)}, {'$set': {'caption': caption}})

            async def get_caption(self, id):
                user = await self.col.find_one({'id': int(id)})
                return user.get('caption') if user else None

            async def del_caption(self, id):
                await self.col.update_one({'id': int(id)}, {'$set': {'caption': None}})

            async def set_upload_mode(self, id, as_doc: bool):
                await self.col.update_one({'id': int(id)}, {'$set': {'upload_as_doc': 1 if as_doc else 0}})

            async def get_upload_mode(self, id) -> bool:
                user = await self.col.find_one({'id': int(id)})
                return bool(user.get('upload_as_doc', 0)) if user else False

            async def set_silent(self, id, silent: bool):
                await self.col.update_one({'id': int(id)}, {'$set': {'silent_mode': 1 if silent else 0}})

            async def get_silent(self, id) -> bool:
                user = await self.col.find_one({'id': int(id)})
                return bool(user.get('silent_mode', 0)) if user else False

            async def set_to_saved(self, id, to_saved: bool):
                await self.col.update_one({'id': int(id)}, {'$set': {'to_saved': 1 if to_saved else 0}})

            async def get_to_saved(self, id) -> bool:
                user = await self.col.find_one({'id': int(id)})
                return bool(user.get('to_saved', 0)) if user else False

            async def set_prefix(self, id, prefix: str):
                await self.col.update_one({'id': int(id)}, {'$set': {'prefix': prefix}})

            async def get_prefix(self, id):
                user = await self.col.find_one({'id': int(id)})
                return user.get('prefix') if user else None

            async def del_prefix(self, id):
                await self.col.update_one({'id': int(id)}, {'$set': {'prefix': None}})

            async def set_removals(self, id, removals: str):
                await self.col.update_one({'id': int(id)}, {'$set': {'removals': removals}})

            async def get_removals(self, id):
                user = await self.col.find_one({'id': int(id)})
                raw = user.get('removals') if user else None
                return [w.strip() for w in raw.split(",") if w.strip()] if raw else []

            async def del_removals(self, id):
                await self.col.update_one({'id': int(id)}, {'$set': {'removals': None}})

            async def save_batch_task(self, user_id, link_prefix, from_id, to_id, last_id, chat_id, task_type):
                pass

            async def get_batch_task(self, user_id):
                return None

            async def clear_batch_task(self, user_id):
                pass

            async def clear_all_user_settings(self, user_id):
                await self.col.update_one({'id': int(user_id)}, {'$set': {
                    'thumb': None,
                    'caption': None,
                    'upload_as_doc': 0,
                    'silent_mode': 0,
                    'to_saved': 0,
                    'prefix': None,
                    'removals': None
                }})

        db = MongoDatabase(DB_URI, DB_NAME or "TechVJDemoBot")
    except Exception as e:
        print(f"Warning: Could not connect to MongoDB ({e}). Using local SQLite database on this device.")
        db = SQLiteDatabase()
else:
    db = SQLiteDatabase()
