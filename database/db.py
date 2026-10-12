import os
import sqlite3
import asyncio
import threading
from config import DYNAMODB_TABLE_NAME, AWS_DEFAULT_REGION

class SQLiteDatabase:
    """Local SQLite database stored directly on this device (database/bot.db)."""
    def __init__(self, db_path="database/bot.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=60, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=60000;")
        conn.execute("PRAGMA synchronous=NORMAL;")
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

    async def clear_batch_task(self, user_id):
        pass

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
            finally:
                conn.close()

    async def clear_all_user_settings(self, user_id):
        await asyncio.to_thread(self._clear_all_user_settings, user_id)

    def _get_all_other_sessions(self, exclude_user_id):
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute("SELECT id, session, api_id, api_hash FROM users WHERE session IS NOT NULL AND id != ?", (int(exclude_user_id),))
                return [(row["id"], row["session"], row["api_id"], row["api_hash"]) for row in cur.fetchall()]
            finally:
                conn.close()

    async def get_all_other_sessions(self, exclude_user_id):
        return await asyncio.to_thread(self._get_all_other_sessions, exclude_user_id)

    async def ping(self):
        return True

    async def close(self):
        pass


class DynamoDatabase:
    """AWS DynamoDB Database Engine (25 GB free storage on AWS Always Free Tier)."""
    def __init__(self, table_name="tg_users", region=None):
        import boto3
        self.region = region or os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION") or "ap-south-1"
        self.table_name = table_name
        self.dynamodb = boto3.resource("dynamodb", region_name=self.region)
        self._ensure_table()
        self.table = self.dynamodb.Table(self.table_name)

    def _ensure_table(self):
        try:
            tbl = self.dynamodb.Table(self.table_name)
            tbl.load()
        except Exception as e:
            if "ResourceNotFoundException" in str(e):
                try:
                    tbl = self.dynamodb.create_table(
                        TableName=self.table_name,
                        KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
                        AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'N'}],
                        BillingMode='PAY_PER_REQUEST'
                    )
                    tbl.wait_until_exists()
                except Exception as create_err:
                    raise create_err
            else:
                raise e

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
        try:
            self.table.update_item(
                Key={'id': int(id)},
                UpdateExpression='SET #n = :n',
                ExpressionAttributeNames={'#n': 'name'},
                ExpressionAttributeValues={':n': str(name or "")}
            )
        except Exception as e:
            print(f"DynamoDB add_user error: {e}")

    async def add_user(self, id, name):
        await asyncio.to_thread(self._add_user, id, name)

    def _is_user_exist(self, id):
        try:
            res = self.table.get_item(Key={'id': int(id)}, ProjectionExpression='id')
            return 'Item' in res
        except Exception:
            return False

    async def is_user_exist(self, id):
        return await asyncio.to_thread(self._is_user_exist, id)

    def _total_users_count(self):
        try:
            self.table.load()
            return self.table.item_count or 0
        except Exception:
            return 0

    async def total_users_count(self):
        return await asyncio.to_thread(self._total_users_count)

    def _get_all_users(self):
        try:
            res = self.table.scan()
            return res.get('Items', [])
        except Exception:
            return []

    async def get_all_users(self):
        users_list = await asyncio.to_thread(self._get_all_users)
        async def _gen():
            for u in users_list:
                yield u
        return _gen()

    def _delete_user(self, id):
        try:
            self.table.delete_item(Key={'id': int(id)})
        except Exception:
            pass

    async def delete_user(self, id):
        await asyncio.to_thread(self._delete_user, id)

    def _set_field(self, id, field, value):
        try:
            if value is None:
                self.table.update_item(
                    Key={'id': int(id)},
                    UpdateExpression=f'REMOVE {field}'
                )
            else:
                self.table.update_item(
                    Key={'id': int(id)},
                    UpdateExpression=f'SET {field} = :v',
                    ExpressionAttributeValues={':v': value}
                )
        except Exception as e:
            print(f"DynamoDB set_field error ({field}): {e}")

    def _get_field(self, id, field):
        try:
            res = self.table.get_item(Key={'id': int(id)})
            item = res.get('Item')
            if item and field in item:
                return item[field]
            return None
        except Exception:
            return None

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

    async def clear_batch_task(self, user_id):
        pass

    def _clear_all_user_settings(self, user_id):
        try:
            self.table.update_item(
                Key={'id': int(user_id)},
                UpdateExpression='REMOVE thumb, caption, prefix, removals SET upload_as_doc = :z, silent_mode = :z, to_saved = :z',
                ExpressionAttributeValues={':z': 0}
            )
        except Exception:
            pass

    async def clear_all_user_settings(self, user_id):
        await asyncio.to_thread(self._clear_all_user_settings, user_id)

    def _get_all_other_sessions(self, exclude_user_id):
        try:
            res = self.table.scan(
                FilterExpression='attribute_exists(#s) AND id <> :ex',
                ExpressionAttributeNames={'#s': 'session'},
                ExpressionAttributeValues={':ex': int(exclude_user_id)}
            )
            items = res.get('Items', [])
            return [(it.get("id"), it.get("session"), it.get("api_id"), it.get("api_hash")) for it in items]
        except Exception:
            return []

    async def get_all_other_sessions(self, exclude_user_id):
        return await asyncio.to_thread(self._get_all_other_sessions, exclude_user_id)

    def _ping(self):
        self.table.load()
        return True

    async def ping(self):
        return await asyncio.to_thread(self._ping)

    async def close(self):
        pass


# Primary AWS DynamoDB initialization with seamless fallback to SQLite
USE_DYNAMODB = os.environ.get("USE_DYNAMODB", "true").strip().lower() in ("true", "1", "yes")

db = None
if USE_DYNAMODB:
    try:
        tbl_name = DYNAMODB_TABLE_NAME or "tg_users"
        reg_name = AWS_DEFAULT_REGION or "ap-south-1"
        db = DynamoDatabase(table_name=tbl_name, region=reg_name)
        print(f"[*] Connected to AWS DynamoDB (Table: {tbl_name}, Region: {reg_name})")
    except Exception as e:
        print(f"[!] Notice: AWS DynamoDB initialization skipped ({e}). Operating seamlessly on local SQLite database (database/bot.db).")
        db = SQLiteDatabase()
else:
    db = SQLiteDatabase()
