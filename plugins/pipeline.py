import os
import time
import math
import shutil
import asyncio
from pyrogram import Client, enums
from pyrogram.types import Message
from pyrogram.errors import FloodWait, MessageNotModified

from plugins.progress import humanbytes, time_formatter
from plugins.organizer import (
    parse_course_metadata,
    format_organized_filename,
    format_organized_caption,
    AuditTracker
)
from plugins.cleaner import rename_file_clean
from database.db import db
from config import (
    WAITING_TIME,
    ERROR_MESSAGE,
    CHANNEL_ID,
    LOGIN_SYSTEM
)

DOWNLOAD_DIR = "downloads"
DEFAULT_THUMB = "database/thumbs/default.jpg"
THUMB_DIR = "database/thumbs"


def get_message_type(msg: Message):
    """Detects content type of a message, including Text, Video, Document, etc."""
    if not msg or getattr(msg, "empty", False):
        return None
    for t in ["document", "video", "audio", "photo", "animation", "sticker", "voice", "video_note"]:
        if hasattr(msg, t) and getattr(msg, t) is not None:
            return t.capitalize()
    if hasattr(msg, "text") and msg.text is not None and msg.text.strip():
        return "Text"
    return None


class DashboardManager:
    """Manages a single auto-updating Telegram message showing real-time queue & transfer progress."""
    def __init__(self, client: Client, status_msg: Message, total_items: int, title: str):
        self.client = client
        self.status_msg = status_msg
        self.total_items = max(1, total_items)
        self.title = title
        self.sent_count = 0
        self.failed_count = 0
        self.current_upload_title = ""
        self.current_upload_stats = ""
        self.current_download_title = ""
        self.prefetched_queue_items = []  # Names of files currently ready on local disk
        self.last_edit_time = 0
        self.lock = asyncio.Lock()
        self._is_active = True

    async def update(self, force=False):
        if not self._is_active:
            return
        now = time.time()
        if not force and (now - self.last_edit_time < 3.2):
            return

        async with self.lock:
            now = time.time()
            if not force and (now - self.last_edit_time < 3.2):
                return
            self.last_edit_time = now

            pct = min(100.0, (self.sent_count / self.total_items) * 100.0)
            filled = int(pct / 100.0 * 12)
            bar = "■" * filled + "□" * (12 - filled)
            remaining = max(0, self.total_items - self.sent_count)

            # Upload indicator
            if self.current_upload_title:
                up_str = f"`{self.current_upload_title}`"
                if self.current_upload_stats:
                    up_str += f"\n   ↳ ⚡ {self.current_upload_stats}"
            else:
                up_str = "_Idle / Preparing..._"

            # Queue visibility indicator
            q_cnt = len(self.prefetched_queue_items)
            if q_cnt > 0:
                first_name = self.prefetched_queue_items[0]
                q_str = f"**{q_cnt}** (`{first_name}` [Ready on Disk])"
            else:
                if self.current_download_title:
                    q_str = f"**0** (📥 Pre-fetching `{self.current_download_title}`...)"
                else:
                    q_str = "**0**"

            text = (
                f"📚 **{self.title} Transfer**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 **Total Discovered:** `{self.total_items}` items\n"
                f"✅ **Delivered to Chat:** `{self.sent_count} / {self.total_items}`\n"
                f"📤 **Currently Uploading:**\n   {up_str}\n"
                f"📦 **Pre-fetched in Queue:** {q_str}\n"
                f"⏳ **Remaining:** `{remaining}` items\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Progress: [{bar}] `{pct:.1f}%`"
            )

            try:
                await self.status_msg.edit_text(text)
            except FloodWait as e:
                await asyncio.sleep(e.value + 1)
            except MessageNotModified:
                pass
            except Exception:
                pass

    def stop(self):
        self._is_active = False


def make_upload_progress_callback(dashboard: DashboardManager, start_time: float):
    async def upload_cb(current, total):
        diff = max(0.001, time.time() - start_time)
        pct = (current * 100 / total) if total > 0 else 0
        speed = current / diff
        eta_sec = round((total - current) / speed) if speed > 0 else 0
        eta = time_formatter(eta_sec)
        dashboard.current_upload_stats = f"`{pct:.1f}%` ({humanbytes(current)}/{humanbytes(total)}) | `{humanbytes(speed)}/s` | ETA: `{eta}`"
        await dashboard.update(force=False)
    return upload_cb


def make_download_progress_callback(dashboard: DashboardManager, start_time: float):
    async def download_cb(current, total):
        diff = max(0.001, time.time() - start_time)
        pct = (current * 100 / total) if total > 0 else 0
        speed = current / diff
        dashboard.current_download_title = f"{humanbytes(current)}/{humanbytes(total)} ({pct:.0f}%)"
        await dashboard.update(force=False)
    return download_cb


async def run_pipelined_transfer(
    client: Client,
    acc: Client,
    user_message: Message,
    dest: int,
    messages_list: list,
    title: str,
    status_msg: Message,
    batch_temp_dict: dict
):
    """
    High-Performance Pipelined Lookahead Transfer Engine.
    - Concurrently downloads video N+1 while bot uploads video N.
    - Delivers all content strictly in chronological sequence (FIFO).
    - Supports all message types: Pure Text (with preserved formatting), Videos,
      Documents, Photos, Audio, Voice notes, Animations, and Stickers.
    - Real-time queue status monitor with pre-fetch indicators.
    - Automatic per-item disk cleanup so local storage is never exhausted.
    """
    user_id = user_message.from_user.id
    batch_temp_dict[user_id] = False

    # Fetch user configuration preferences
    prefix = await db.get_prefix(user_id)
    removals = await db.get_removals(user_id)
    user_caption_tmpl = await db.get_caption(user_id)
    user_thumb = await db.get_thumb(user_id)
    upload_as_doc = await db.get_upload_mode(user_id)
    silent = await db.get_silent(user_id)

    tracker = AuditTracker(topic_title=title)
    dashboard = DashboardManager(client, status_msg, len(messages_list), title)

    # Bounded lookahead pre-fetch queue: maxsize=1 ensures at most 1 item waiting in queue
    queue = asyncio.Queue(maxsize=1)
    prefetch_sem = asyncio.Semaphore(1)

    async def producer():
        """Producer coroutine: Pre-fetches media in background while consumer uploads."""
        for msg in messages_list:
            if batch_temp_dict.get(user_id):
                break

            m_type = get_message_type(msg)
            if not m_type:
                continue

            # 1. Pure text messages: zero disk cost, queued immediately
            if m_type == "Text":
                text_preview = (msg.text[:40].replace("\n", " ") + "...") if len(msg.text) > 40 else msg.text.replace("\n", " ")
                await queue.put({
                    "kind": "text",
                    "msg": msg,
                    "text": msg.text,
                    "entities": msg.entities,
                    "title": text_preview
                })
                continue

            # 2. Media messages: acquire prefetch semaphore slot
            await prefetch_sem.acquire()
            if batch_temp_dict.get(user_id):
                break

            msg_temp_dir = os.path.join(DOWNLOAD_DIR, f"task_{msg.id}_{int(time.time()*1000)%100000}")
            os.makedirs(msg_temp_dir, exist_ok=True)

            dl_start = time.time()
            dashboard.current_download_title = f"Post #{msg.id}"
            await dashboard.update(force=False)

            try:
                file_path = await acc.download_media(
                    msg,
                    file_name=f"{msg_temp_dir}/",
                    progress=make_download_progress_callback(dashboard, dl_start)
                )

                if not file_path or not os.path.exists(file_path):
                    prefetch_sem.release()
                    shutil.rmtree(msg_temp_dir, ignore_errors=True)
                    await queue.put({"kind": "error", "msg": msg, "error": "Download failed or empty"})
                    continue

                orig_basename = os.path.basename(file_path)
                orig_caption = msg.caption or msg.text or ""
                serial, item_title, part = parse_course_metadata(orig_caption, orig_basename)
                organized_name = format_organized_filename(orig_caption, orig_basename, prefix=prefix, custom_removals=removals)

                if organized_name != orig_basename:
                    new_path = os.path.join(msg_temp_dir, organized_name)
                    try:
                        if os.path.exists(new_path) and new_path != file_path:
                            os.remove(new_path)
                        os.rename(file_path, new_path)
                        file_path = new_path
                    except Exception:
                        file_path = rename_file_clean(file_path, prefix=prefix, custom_removals=removals)
                else:
                    file_path = rename_file_clean(file_path, prefix=prefix, custom_removals=removals)

                filename = os.path.basename(file_path)
                filesize = humanbytes(os.path.getsize(file_path))
                caption = format_organized_caption(orig_caption, filename, filesize, custom_tmpl=user_caption_tmpl)

                # Thumbnail resolution
                ph_path = None
                if user_thumb and os.path.exists(user_thumb):
                    ph_path = user_thumb
                else:
                    try:
                        media_obj = getattr(msg, m_type.lower(), None)
                        if media_obj and hasattr(media_obj, 'thumbs') and media_obj.thumbs:
                            ph_path = await acc.download_media(media_obj.thumbs[0].file_id, file_name=f"{msg_temp_dir}/")
                    except Exception:
                        ph_path = None
                    if not ph_path and os.path.exists(DEFAULT_THUMB):
                        ph_path = DEFAULT_THUMB

                item = {
                    "kind": "media",
                    "msg": msg,
                    "msg_type": m_type,
                    "temp_dir": msg_temp_dir,
                    "file_path": file_path,
                    "thumb_path": ph_path,
                    "filename": filename,
                    "caption": caption,
                    "serial": serial,
                    "title": item_title or filename,
                    "part": part,
                    "filesize": filesize
                }

                dashboard.prefetched_queue_items.append(filename)
                dashboard.current_download_title = ""
                await dashboard.update(force=True)
                await queue.put(item)

            except Exception as e:
                prefetch_sem.release()
                shutil.rmtree(msg_temp_dir, ignore_errors=True)
                await queue.put({"kind": "error", "msg": msg, "error": str(e)})

        # Sentinel to signal producer finished
        await queue.put(None)

    async def consumer():
        """Consumer coroutine: Sequentially uploads and sends content in exact chronological sequence."""
        while True:
            item = await queue.get()
            if item is None:
                break

            if batch_temp_dict.get(user_id):
                if item.get("temp_dir"):
                    shutil.rmtree(item["temp_dir"], ignore_errors=True)
                break

            kind = item.get("kind")
            msg = item.get("msg")

            # 1. Deliver pure text message
            if kind == "text":
                dashboard.current_upload_title = f"💬 Text: {item['title']}"
                dashboard.current_upload_stats = ""
                await dashboard.update(force=False)
                text = item["text"]
                entities = item.get("entities")
                try:
                    if len(text) > 4000:
                        for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
                            await client.send_message(dest, chunk, disable_notification=silent)
                    else:
                        if entities:
                            try:
                                await client.send_message(dest, text, entities=entities, disable_notification=silent)
                            except Exception:
                                await client.send_message(dest, text, disable_notification=silent)
                        else:
                            await client.send_message(dest, text, disable_notification=silent)
                    tracker.record_item(msg.id, "", item["title"], "", "Text Message", "success")
                    dashboard.sent_count += 1
                except Exception as e:
                    tracker.record_item(msg.id, "", item["title"], "", "Text Message", "error")
                    dashboard.failed_count += 1

                await dashboard.update(force=True)
                queue.task_done()
                await asyncio.sleep(min(WAITING_TIME, 2))
                continue

            # 2. Error item
            if kind == "error":
                tracker.record_item(msg.id, "", "", "", f"post_{msg.id}", "error")
                dashboard.failed_count += 1
                await dashboard.update(force=True)
                queue.task_done()
                continue

            # 3. Media upload
            if kind == "media":
                fn = item["filename"]
                if fn in dashboard.prefetched_queue_items:
                    dashboard.prefetched_queue_items.remove(fn)
                dashboard.current_upload_title = fn
                dashboard.current_upload_stats = "Initiating upload..."
                await dashboard.update(force=True)

                # 🔥 RELEASE PREFETCH SEMAPHORE: Lets producer pre-fetch next item during this upload!
                prefetch_sem.release()

                up_start = time.time()
                progress_cb = make_upload_progress_callback(dashboard, up_start)
                m_type = item["msg_type"]
                f_path = item["file_path"]
                thumb = item["thumb_path"]
                caption = item["caption"]

                success = False
                try:
                    # Video stream
                    if m_type == "Video" and not upload_as_doc:
                        vid = getattr(msg, "video", None)
                        await client.send_video(
                            dest,
                            f_path,
                            duration=getattr(vid, "duration", 0) if vid else 0,
                            width=getattr(vid, "width", 0) if vid else 0,
                            height=getattr(vid, "height", 0) if vid else 0,
                            thumb=thumb,
                            caption=caption,
                            parse_mode=enums.ParseMode.HTML,
                            disable_notification=silent,
                            progress=progress_cb
                        )
                        success = True

                    # Document or Video in Document mode
                    elif m_type == "Document" or (m_type == "Video" and upload_as_doc):
                        await client.send_document(
                            dest,
                            f_path,
                            thumb=thumb,
                            caption=caption,
                            parse_mode=enums.ParseMode.HTML,
                            disable_notification=silent,
                            progress=progress_cb
                        )
                        success = True

                    # Audio
                    elif m_type == "Audio":
                        aud = getattr(msg, "audio", None)
                        await client.send_audio(
                            dest,
                            f_path,
                            duration=getattr(aud, "duration", 0) if aud else 0,
                            performer=getattr(aud, "performer", None) if aud else None,
                            title=getattr(aud, "title", None) if aud else None,
                            thumb=thumb,
                            caption=caption,
                            parse_mode=enums.ParseMode.HTML,
                            disable_notification=silent,
                            progress=progress_cb
                        )
                        success = True

                    # Photo
                    elif m_type == "Photo":
                        await client.send_photo(
                            dest,
                            f_path,
                            caption=caption,
                            parse_mode=enums.ParseMode.HTML,
                            disable_notification=silent
                        )
                        success = True

                    # Voice note
                    elif m_type == "Voice":
                        await client.send_voice(
                            dest,
                            f_path,
                            caption=caption,
                            parse_mode=enums.ParseMode.HTML,
                            disable_notification=silent,
                            progress=progress_cb
                        )
                        success = True

                    # Animation / GIF
                    elif m_type == "Animation":
                        await client.send_animation(
                            dest,
                            f_path,
                            caption=caption,
                            parse_mode=enums.ParseMode.HTML,
                            disable_notification=silent
                        )
                        success = True

                    # Sticker
                    elif m_type == "Sticker":
                        await client.send_sticker(
                            dest,
                            f_path,
                            disable_notification=silent
                        )
                        success = True

                    # Video note
                    elif m_type == "Video_note":
                        await client.send_video_note(
                            dest,
                            f_path,
                            disable_notification=silent
                        )
                        success = True

                except FloodWait as e:
                    await client.send_message(user_message.chat.id, f"⚠️ **Telegram FloodWait:** Waiting `{e.value}` seconds...")
                    await asyncio.sleep(e.value + 1)
                except Exception as e:
                    if ERROR_MESSAGE:
                        await client.send_message(user_message.chat.id, f"❌ Upload error on `{fn}`: {e}")
                finally:
                    # Clean up local temporary file immediately
                    shutil.rmtree(item["temp_dir"], ignore_errors=True)

                if success:
                    tracker.record_item(msg.id, item["serial"], item["title"], item["part"], fn, "success")
                    dashboard.sent_count += 1
                else:
                    tracker.record_item(msg.id, item["serial"], item["title"], item["part"], fn, "error")
                    dashboard.failed_count += 1

                dashboard.current_upload_title = ""
                dashboard.current_upload_stats = ""
                await dashboard.update(force=True)
                queue.task_done()
                await asyncio.sleep(min(WAITING_TIME, 2))

    try:
        producer_task = asyncio.create_task(producer())
        consumer_task = asyncio.create_task(consumer())
        await asyncio.gather(producer_task, consumer_task)
    except Exception as e:
        await client.send_message(user_message.chat.id, f"❌ Transfer exception: `{e}`")
    finally:
        dashboard.stop()
        # Clean up any leftover items in the queue
        while not queue.empty():
            try:
                leftover = queue.get_nowait()
                if leftover and leftover.get("temp_dir"):
                    shutil.rmtree(leftover["temp_dir"], ignore_errors=True)
            except Exception:
                break

        batch_temp_dict[user_id] = True
        try:
            await status_msg.delete()
        except Exception:
            pass

        # Send final verification report
        await client.send_message(user_message.chat.id, tracker.generate_report())
