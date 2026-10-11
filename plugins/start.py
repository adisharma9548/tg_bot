import os
import time
import shutil
import asyncio 
import pyrogram
from pyrogram import Client, filters, enums
from pyrogram.errors import (
    FloodWait, 
    UserIsBlocked, 
    InputUserDeactivated, 
    UserAlreadyParticipant, 
    InviteHashExpired, 
    UsernameNotOccupied
)
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import API_ID, API_HASH, ERROR_MESSAGE, LOGIN_SYSTEM, STRING_SESSION, CHANNEL_ID, WAITING_TIME
from database.db import db
from plugins.strings import (
    HELP_MAIN_TXT, 
    HELP_DOWNLOAD_TXT, 
    HELP_CLEANER_TXT, 
    HELP_SETTINGS_TXT, 
    HELP_WEB_TXT, 
    HELP_COMMANDS_TXT, 
    get_help_main_markup, 
    get_help_back_markup
)
from plugins.progress import progress_for_pyrogram, humanbytes
from plugins.cleaner import rename_file_clean, clean_filename
from plugins.organizer import (
    parse_tg_link, 
    parse_course_metadata, 
    format_organized_filename, 
    format_organized_caption, 
    AuditTracker,
    get_message_type
)
from plugins.ytdl import is_web_url, download_web_media
from bot import UserClient

DOWNLOAD_DIR = "downloads"
THUMB_DIR = "database/thumbs"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(THUMB_DIR, exist_ok=True)

class TaskManager:
    """
    Industry-standard concurrent task execution & security manager.
    Enforces strict single-task execution per user and provides immediate file purge on cancellation.
    """
    _active_tasks = {}

    @classmethod
    def is_user_busy(cls, user_id: int) -> bool:
        task = cls._active_tasks.get(user_id)
        return bool(task and not task.get("cancelled", False))

    @classmethod
    def get_start_time(cls, user_id: int) -> float:
        task = cls._active_tasks.get(user_id, {})
        return task.get("start_time", time.time())

    @classmethod
    def start_task(cls, user_id: int, task_type: str = "transfer"):
        cls._active_tasks[user_id] = {
            "type": task_type,
            "start_time": time.time(),
            "cancelled": False,
            "files": set()
        }

    @classmethod
    def register_file(cls, user_id: int, file_path: str):
        if user_id in cls._active_tasks and file_path:
            cls._active_tasks[user_id]["files"].add(file_path)

    @classmethod
    def is_cancelled(cls, user_id: int) -> bool:
        task = cls._active_tasks.get(user_id)
        if not task:
            return False
        return bool(task.get("cancelled", False))

    @classmethod
    def cancel_task(cls, user_id: int):
        task = cls._active_tasks.get(user_id)
        if task:
            task["cancelled"] = True
        cls.purge_user_files(user_id)

    @classmethod
    def purge_user_files(cls, user_id: int):
        """Immediately deletes any files associated with the user from backend downloads/ directory."""
        task = cls._active_tasks.get(user_id)
        if task:
            for f in list(task.get("files", [])):
                try:
                    if os.path.isfile(f):
                        os.remove(f)
                    elif os.path.isdir(f):
                        shutil.rmtree(f, ignore_errors=True)
                except Exception:
                    pass
            task["files"].clear()

        # Also search downloads directory for any matching user ID files
        try:
            if os.path.exists(DOWNLOAD_DIR):
                for fname in os.listdir(DOWNLOAD_DIR):
                    if str(user_id) in fname:
                        fpath = os.path.join(DOWNLOAD_DIR, fname)
                        try:
                            if os.path.isfile(fpath):
                                os.remove(fpath)
                            elif os.path.isdir(fpath):
                                shutil.rmtree(fpath, ignore_errors=True)
                        except Exception:
                            pass
        except Exception:
            pass

    @classmethod
    def finish_task(cls, user_id: int):
        cls.purge_user_files(user_id)
        cls._active_tasks.pop(user_id, None)


async def get_destination(client: Client, message: Message):
    """Determines delivery chat based on settings and CHANNEL_ID."""
    if CHANNEL_ID:
        try:
            return int(CHANNEL_ID)
        except:
            pass
    to_saved = await db.get_to_saved(message.from_user.id)
    if to_saved:
        return message.from_user.id
    return message.chat.id


LOGO_PATH = "logo.jpg"
DEFAULT_THUMB = "database/thumbs/default.jpg"

def get_start_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📥 How to Download", callback_data="help_download"),
            InlineKeyboardButton("⚙️ Settings", callback_data="set_menu_main")
        ],
        [
            InlineKeyboardButton("🔑 Connect Account", callback_data="ui_login_info"),
            InlineKeyboardButton("📊 System Status", callback_data="ui_status_info")
        ],
        [
            InlineKeyboardButton("📚 Topic Transfer", callback_data="ui_topic_info"),
            InlineKeyboardButton("🧹 Clear Chat", callback_data="ui_clear_prompt")
        ],
        [
            InlineKeyboardButton("🌐 Web Downloader", callback_data="help_web"),
            InlineKeyboardButton("🏷️ Custom Renamer", callback_data="help_cleaner")
        ]
    ])


async def build_settings_panel(user_id: int):
    upload_doc = await db.get_upload_mode(user_id)
    silent_on = await db.get_silent(user_id)
    to_saved = await db.get_to_saved(user_id)
    thumb_path = await db.get_thumb(user_id)
    has_thumb = bool(thumb_path and os.path.exists(thumb_path))
    caption = await db.get_caption(user_id)
    has_caption = bool(caption)
    prefix = await db.get_prefix(user_id)
    removals = await db.get_removals(user_id)
    rem_count = len(removals) if removals else 0

    mode_label = "📁 Document" if upload_doc else "🎥 Video"
    silent_label = "🔕 Muted" if silent_on else "🔔 Sound ON"
    dest_label = "📥 Saved Messages" if to_saved else "💬 Bot Chat"
    thumb_label = "✅ Custom Set" if has_thumb else "❌ Default Logo"
    cap_label = "✅ Custom Active" if has_caption else "❌ Original Post"
    pfx_label = f"`{prefix}`" if prefix else "_None_"
    rem_label = f"`{rem_count} active`" if rem_count else "_None_"

    text = (
        "⚙️ **Personal Settings & Delivery Preferences**\n\n"
        f"> 🎬 **Upload Format** • {mode_label}\n"
        f"> 🔔 **Notification** • {silent_label}\n"
        f"> 📍 **Destination** • {dest_label}\n"
        f"> 🖼️ **Thumbnail** • {thumb_label}\n"
        f"> 📝 **Caption** • {cap_label}\n"
        f"> 🏷️ **Filename Prefix** • {pfx_label}\n"
        f"> 🚫 **Word Removals** • {rem_label}\n\n"
        "💡 *Tap the buttons below to toggle options or manage customizations:*"
    )

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"🎬 Mode: {mode_label}", callback_data="set_mode_toggle"),
            InlineKeyboardButton(f"🔔 {silent_label}", callback_data="set_silent_toggle")
        ],
        [
            InlineKeyboardButton(f"📍 Dest: {dest_label}", callback_data="set_dest_toggle")
        ],
        [
            InlineKeyboardButton("🖼️ Thumbnail Menu", callback_data="set_thumb_menu"),
            InlineKeyboardButton("📝 Caption Menu", callback_data="set_caption_menu")
        ],
        [
            InlineKeyboardButton("🏷️ Prefix & Filter Menu", callback_data="set_tags_menu")
        ],
        [
            InlineKeyboardButton("🔄 Reset All to Defaults", callback_data="set_reset_confirm")
        ],
        [
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data="help_main"),
            InlineKeyboardButton("❌ Close", callback_data="help_close")
        ]
    ])
    return text, markup


# Start command with Rich Interactive Buttons
@Client.on_message(filters.command(["start"]) & filters.private)
async def send_start(client: Client, message: Message):
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
    start_text = (
        f"👋 **Hi {message.from_user.mention}**, I am **Aditya's Save Restricted Content Bot**.\n\n"
        f"• High-speed pipelined lookahead engine with live queue monitor.\n"
        f"• Auto-cleaner is **always active** for all files (PDF, ZIP, APK, MP4, MP3, etc.).\n"
        f"• Single-task concurrency protection with instant file purging.\n\n"
        f"Select an option below to get started:"
    )
    if os.path.exists(LOGO_PATH):
        await client.send_photo(
            chat_id=message.chat.id,
            photo=LOGO_PATH,
            caption=start_text,
            reply_markup=get_start_keyboard(),
            reply_to_message_id=message.id
        )
    else:
        await client.send_message(
            chat_id=message.chat.id,
            text=start_text,
            reply_markup=get_start_keyboard(),
            reply_to_message_id=message.id
        )


# Interactive Settings command
@Client.on_message(filters.command(["settings"]) & filters.private)
async def send_settings_command(client: Client, message: Message):
    text, markup = await build_settings_panel(message.from_user.id)
    await message.reply(text=text, reply_markup=markup)


# Interactive Help command
@Client.on_message(filters.command(["help"]) & filters.private)
async def send_help(client: Client, message: Message):
    await client.send_message(
        chat_id=message.chat.id, 
        text=HELP_MAIN_TXT,
        reply_markup=get_help_main_markup(),
        reply_to_message_id=message.id
    )


# Task Cancellation Callback (from progress cards or busy prompts)
@Client.on_callback_query(filters.regex(r"^task_cancel$"))
async def cb_task_cancel(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    if not TaskManager.is_user_busy(user_id):
        await query.answer("ℹ️ You have no active task running.", show_alert=True)
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    TaskManager.cancel_task(user_id)
    TaskManager.purge_user_files(user_id)
    try:
        await db.clear_batch_task(user_id)
    except Exception:
        pass

    await query.answer("🛑 Task cancelled & files purged!", show_alert=True)
    try:
        await query.message.edit_text(
            "🛑 **Task cancelled successfully.**\n\n"
            "All downloaded temporary files and cache have been purged from the backend server to prevent disk clutter.\n"
            "You can start a new transfer anytime."
        )
    except Exception:
        pass


# Settings & Interactive UI Callback Handlers
@Client.on_callback_query(filters.regex(r"^(set_|ui_|help_)"))
async def general_ui_callback(client: Client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id

    # 1. Close buttons
    if data in ("help_close", "set_close"):
        await query.message.delete()
        return

    # 2. Main settings panel
    if data == "set_menu_main":
        text, markup = await build_settings_panel(user_id)
        try:
            await query.message.edit_text(text=text, reply_markup=markup)
        except Exception:
            pass
        return

    # 3. Settings Toggles
    if data == "set_mode_toggle":
        curr = await db.get_upload_mode(user_id)
        await db.set_upload_mode(user_id, not curr)
        text, markup = await build_settings_panel(user_id)
        await query.answer(f"Switched to {'Document' if not curr else 'Video'} mode!")
        try:
            await query.message.edit_text(text=text, reply_markup=markup)
        except Exception:
            pass
        return

    if data == "set_silent_toggle":
        curr = await db.get_silent(user_id)
        await db.set_silent(user_id, not curr)
        text, markup = await build_settings_panel(user_id)
        await query.answer(f"Silent delivery: {'Muted (ON)' if not curr else 'Sound (OFF)'}!")
        try:
            await query.message.edit_text(text=text, reply_markup=markup)
        except Exception:
            pass
        return

    if data == "set_dest_toggle":
        curr = await db.get_to_saved(user_id)
        await db.set_to_saved(user_id, not curr)
        text, markup = await build_settings_panel(user_id)
        await query.answer(f"Destination: {'Saved Messages' if not curr else 'Bot Chat'}!")
        try:
            await query.message.edit_text(text=text, reply_markup=markup)
        except Exception:
            pass
        return

    # 4. Thumbnail Sub-menu
    if data == "set_thumb_menu":
        thumb_path = await db.get_thumb(user_id)
        has_thumb = bool(thumb_path and os.path.exists(thumb_path))
        text = (
            "🖼️ **Custom Thumbnail Settings**\n\n"
            f"> Status: {'✅ Active custom thumbnail' if has_thumb else '❌ Default logo thumbnail'}\n\n"
            "• To set a new thumbnail: Send or reply to any photo with `/set_thumb`.\n"
            "• Tap below to preview or delete your current thumbnail:"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("👁️ View Thumbnail", callback_data="set_thumb_view"),
                InlineKeyboardButton("🗑️ Delete Thumbnail", callback_data="set_thumb_del")
            ],
            [
                InlineKeyboardButton("🔙 Back to Settings", callback_data="set_menu_main")
            ]
        ])
        try:
            await query.message.edit_text(text=text, reply_markup=markup)
        except Exception:
            pass
        return

    if data == "set_thumb_view":
        thumb_path = await db.get_thumb(user_id)
        if thumb_path and os.path.exists(thumb_path):
            await client.send_photo(chat_id=user_id, photo=thumb_path, caption="🖼️ **Your current custom thumbnail.**")
            await query.answer("Thumbnail sent to chat!")
        else:
            await query.answer("❌ No custom thumbnail set! Reply to a photo with /set_thumb.", show_alert=True)
        return

    if data == "set_thumb_del":
        thumb_path = await db.get_thumb(user_id)
        if thumb_path and os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except Exception:
                pass
        await db.del_thumb(user_id)
        await query.answer("🗑️ Custom thumbnail deleted!", show_alert=True)
        text, markup = await build_settings_panel(user_id)
        try:
            await query.message.edit_text(text=text, reply_markup=markup)
        except Exception:
            pass
        return

    # 5. Caption Sub-menu
    if data == "set_caption_menu":
        caption = await db.get_caption(user_id)
        has_caption = bool(caption)
        cap_preview = f"`{caption}`" if has_caption else "_Using original post caption_"
        text = (
            "📝 **Custom Caption Settings**\n\n"
            f"> Current: {cap_preview}\n\n"
            "• To set custom template: Send `/set_caption <text>`\n"
            "• Dynamic tags supported: `{filename}`, `{size}`, `{caption}`\n"
            "• Tap below to manage:"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("👁️ View Caption", callback_data="set_caption_view"),
                InlineKeyboardButton("🗑️ Reset to Original", callback_data="set_caption_del")
            ],
            [
                InlineKeyboardButton("🔙 Back to Settings", callback_data="set_menu_main")
            ]
        ])
        try:
            await query.message.edit_text(text=text, reply_markup=markup)
        except Exception:
            pass
        return

    if data == "set_caption_view":
        caption = await db.get_caption(user_id)
        if caption:
            await query.answer("Caption sent to chat!")
            await client.send_message(chat_id=user_id, text=f"📝 **Your current custom caption:**\n\n`{caption}`")
        else:
            await query.answer("❌ No custom caption template set.", show_alert=True)
        return

    if data == "set_caption_del":
        await db.del_caption(user_id)
        await query.answer("🗑️ Caption reset to original post caption!", show_alert=True)
        text, markup = await build_settings_panel(user_id)
        try:
            await query.message.edit_text(text=text, reply_markup=markup)
        except Exception:
            pass
        return

    # 6. Prefix & Tag Filter Sub-menu
    if data == "set_tags_menu":
        prefix = await db.get_prefix(user_id)
        removals = await db.get_removals(user_id)
        rem_str = ", ".join(removals) if removals else "None"
        text = (
            "🏷️ **Prefix & Filename Cleaner Settings**\n\n"
            f"> 🏷️ Custom Prefix: `{prefix or 'None'}`\n"
            f"> 🚫 Custom Word Removals: `{rem_str}`\n\n"
            "• Set Prefix: `/set_prefix <text>`\n"
            "• Add Removal Words: `/replace <word1, word2, ...>`\n"
            "• Auto-cleaner for ads and promo tags is **always active**!"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🗑️ Clear Prefix", callback_data="set_prefix_del"),
                InlineKeyboardButton("🗑️ Clear Word Filters", callback_data="set_replace_del")
            ],
            [
                InlineKeyboardButton("🔙 Back to Settings", callback_data="set_menu_main")
            ]
        ])
        try:
            await query.message.edit_text(text=text, reply_markup=markup)
        except Exception:
            pass
        return

    if data == "set_prefix_del":
        await db.del_prefix(user_id)
        await query.answer("🗑️ Custom prefix cleared!", show_alert=True)
        text, markup = await build_settings_panel(user_id)
        try:
            await query.message.edit_text(text=text, reply_markup=markup)
        except Exception:
            pass
        return

    if data == "set_replace_del":
        await db.del_removals(user_id)
        await query.answer("🗑️ Custom word removals cleared!", show_alert=True)
        text, markup = await build_settings_panel(user_id)
        try:
            await query.message.edit_text(text=text, reply_markup=markup)
        except Exception:
            pass
        return

    # 7. Reset Confirm & Execute
    if data == "set_reset_confirm":
        text = (
            "⚠️ **Reset All Settings to Defaults?**\n\n"
            "This will revert:\n"
            "• Thumbnail ➔ Default logo\n"
            "• Caption ➔ Original post caption\n"
            "• Format ➔ Video streamable player\n"
            "• Silent Delivery ➔ Sound (ON)\n"
            "• Destination ➔ Bot Chat\n"
            "• Prefix & Word Filters ➔ Cleared\n\n"
            "Are you sure you want to proceed?"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚠️ Yes, Reset Everything", callback_data="set_reset_execute"),
                InlineKeyboardButton("🔙 Cancel", callback_data="set_menu_main")
            ]
        ])
        try:
            await query.message.edit_text(text=text, reply_markup=markup)
        except Exception:
            pass
        return

    if data == "set_reset_execute":
        TaskManager.cancel_task(user_id)
        TaskManager.purge_user_files(user_id)
        thumb_path = f"{THUMB_DIR}/{user_id}.jpg"
        if os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except Exception:
                pass
        await db.clear_all_user_settings(user_id)
        await query.answer("⚙️ All settings reset to default!", show_alert=True)
        text, markup = await build_settings_panel(user_id)
        try:
            await query.message.edit_text(text=text, reply_markup=markup)
        except Exception:
            pass
        return

    # 8. Start Menu UI Callbacks
    if data == "ui_login_info":
        is_logged_in = bool(await db.get_session(user_id))
        status_str = "✅ **Account Connected & Active**" if is_logged_in else "❌ **No Account Connected**"
        text = (
            f"🔑 **Telegram User Account Connection**\n\n"
            f"> Status: {status_str}\n\n"
            "**Why connect your account?**\n"
            "Connecting your account lets you download files from private channels and closed forum topics that your account has joined.\n\n"
            "• **To Connect:** Send `/login` and follow the instructions.\n"
            "• **To Disconnect:** Send `/logout` anytime."
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔙 Back to Main Menu", callback_data="help_main"),
                InlineKeyboardButton("❌ Close", callback_data="help_close")
            ]
        ])
        try:
            await query.message.edit_text(text=text, reply_markup=markup)
        except Exception:
            pass
        return

    if data == "ui_topic_info":
        text = (
            "📚 **Forum Topic Transfer Guide**\n\n"
            "Transfer an entire Forum Topic / Thread in one command!\n\n"
            "**Syntax:**\n"
            "`/topic https://t.me/c/<chat_id>/<topic_id>/<msg_id>`\n"
            "Or:\n"
            "`/topic https://t.me/c/<chat_id>/<topic_id>`\n\n"
            "**Key Features:**\n"
            "• Scans every message, lecture video, and PDF in the thread.\n"
            "• Preserves sequence with organized file numbers and parts.\n"
            "• Concurrently pre-fetches next item while current item uploads.\n"
            "• Generates full Verification Checklist on completion!"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔙 Back to Main Menu", callback_data="help_main"),
                InlineKeyboardButton("❌ Close", callback_data="help_close")
            ]
        ])
        try:
            await query.message.edit_text(text=text, reply_markup=markup)
        except Exception:
            pass
        return

    if data == "ui_clear_prompt":
        text = (
            "🧹 **Clear Entire Chat History?**\n\n"
            "This will delete conversation messages from both your side and the bot's side, purge any leftover downloads, and reset your workspace.\n\n"
            "Tap below to confirm:"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🧹 Confirm & Clear Now", callback_data="ui_clear_execute"),
                InlineKeyboardButton("🔙 Cancel", callback_data="help_main")
            ]
        ])
        try:
            await query.message.edit_text(text=text, reply_markup=markup)
        except Exception:
            pass
        return

    if data == "ui_clear_execute":
        await query.answer("🧹 Cleaning conversation history...")
        TaskManager.cancel_task(user_id)
        TaskManager.purge_user_files(user_id)
        try:
            await query.message.delete()
        except Exception:
            pass
        await clear_chat_history(client, query.message)
        return

    if data == "ui_status_info":
        total, used, free = shutil.disk_usage(".")
        total_gb = total / (1024 ** 3)
        free_gb = free / (1024 ** 3)
        is_logged_in = bool(await db.get_session(user_id))
        upload_mode = "📁 Document" if await db.get_upload_mode(user_id) else "🎥 Video"
        silent = "🔕 ON" if await db.get_silent(user_id) else "🔔 OFF"
        to_saved = "📥 Saved Messages" if await db.get_to_saved(user_id) else "💬 Bot Chat"

        text = (
            "📊 **Operational System & Profile Status**\n\n"
            f"> 👤 **Account** • {'✅ Connected' if is_logged_in else '❌ Not Connected (/login)'}\n"
            f"> 🎬 **Upload Mode** • `{upload_mode}`\n"
            f"> 🔔 **Silent Mode** • `{silent}`\n"
            f"> 📍 **Destination** • `{to_saved}`\n"
            f"> 💾 **Disk Free** • `{free_gb:.1f} GB` / `{total_gb:.1f} GB`\n"
            f"> 🛑 **Single Task Policy** • `Active`\n"
            f"> 🧹 **Auto-Cleaner** • `Active`"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚙️ Open Settings", callback_data="set_menu_main"),
                InlineKeyboardButton("🔙 Back", callback_data="help_main")
            ],
            [
                InlineKeyboardButton("❌ Close", callback_data="help_close")
            ]
        ])
        try:
            await query.message.edit_text(text=text, reply_markup=markup)
        except Exception:
            pass
        return

    # 9. Standard Help Pages
    pages = {
        "help_main": (HELP_MAIN_TXT, get_help_main_markup()),
        "help_download": (HELP_DOWNLOAD_TXT, get_help_back_markup()),
        "help_cleaner": (HELP_CLEANER_TXT, get_help_back_markup()),
        "help_settings": (HELP_SETTINGS_TXT, get_help_back_markup()),
        "help_web": (HELP_WEB_TXT, get_help_back_markup()),
        "help_commands": (HELP_COMMANDS_TXT, get_help_back_markup())
    }

    if data in pages:
        text, markup = pages[data]
        try:
            await query.message.edit_text(text=text, reply_markup=markup, disable_web_page_preview=True)
        except Exception:
            pass


# Cancel command: stops active task and purges backend temporary files immediately
@Client.on_message(filters.command(["cancel"]) & filters.private)
async def handle_cancel_command(client: Client, message: Message):
    user_id = message.from_user.id
    if not TaskManager.is_user_busy(user_id):
        return await message.reply("ℹ️ **You do not have any active task running.**")

    TaskManager.cancel_task(user_id)
    TaskManager.purge_user_files(user_id)
    try:
        await db.clear_batch_task(user_id)
    except Exception:
        pass

    await client.send_message(
        chat_id=message.chat.id, 
        text="🛑 **Task cancelled.**\nAll downloaded files and cache have been purged from the backend server to prevent storage clutter."
    )


# Clear command: clears chats from both sides in one click
@Client.on_message(filters.command(["clear"]) & filters.private)
async def clear_chat_history(client: Client, message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    current_msg_id = message.id

    # 1. Stop any ongoing task for this user and purge files
    TaskManager.cancel_task(user_id)
    TaskManager.purge_user_files(user_id)

    # 2. If user is logged in, use their user account session to wipe chat history for both sides
    if LOGIN_SYSTEM == True:
        try:
            user_data = await db.get_session(user_id)
            if user_data:
                api_id = int(await db.get_api_id(user_id) or API_ID)
                api_hash = await db.get_api_hash(user_id) or API_HASH
                acc = Client(f"clear_{user_id}", session_string=user_data, api_hash=api_hash, api_id=api_id, in_memory=True)
                await asyncio.wait_for(acc.connect(), timeout=5.0)
                try:
                    bot_id = client.me.id if client.me else (await client.get_me()).id
                    await acc.delete_chat_history(chat_id=bot_id, revoke=True)
                finally:
                    try:
                        await acc.disconnect()
                    except:
                        pass
        except Exception:
            pass

    # 3. Bot-side bulk deletion backwards up to current_msg_id
    # Deletes bot messages and user messages with revoke=True (both sides)
    try:
        max_check = min(current_msg_id, 3000)
        for start_id in range(current_msg_id, max(0, current_msg_id - max_check), -100):
            end_id = max(1, start_id - 99)
            chunk = list(range(end_id, start_id + 1))
            try:
                await client.delete_messages(chat_id=chat_id, message_ids=chunk, revoke=True)
            except Exception:
                pass
            await asyncio.sleep(0.03)
    except Exception:
        pass

    # 4. Clean leftover temporary files in downloads/
    if os.path.exists(DOWNLOAD_DIR):
        for f in os.listdir(DOWNLOAD_DIR):
            fpath = os.path.join(DOWNLOAD_DIR, f)
            try:
                if os.path.isfile(fpath):
                    os.remove(fpath)
            except:
                pass

    # 5. Send clean confirmation with a Dismiss button
    try:
        await client.send_message(
            chat_id=chat_id,
            text=(
                "🧹 **Chat cleared from both sides!**\n\n"
                "All conversation messages have been removed.\n"
                "Send /start whenever you want to begin again."
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑️ Dismiss", callback_data="clear_dismiss")]
            ])
        )
    except Exception:
        pass


# Callback Query Handler for Dismissing the clear message
@Client.on_callback_query(filters.regex(r"^clear_dismiss$"))
async def dismiss_clear_msg(client: Client, query: CallbackQuery):
    try:
        await query.message.delete()
    except Exception:
        pass


# Reset command (Reset custom settings and preferences)
@Client.on_message(filters.command(["reset", "reset_settings"]) & filters.private)
async def reset_settings(client: Client, message: Message):
    user_id = message.from_user.id
    TaskManager.cancel_task(user_id)
    TaskManager.purge_user_files(user_id)
    thumb_path = f"{THUMB_DIR}/{user_id}.jpg"
    if os.path.exists(thumb_path):
        try:
            os.remove(thumb_path)
        except:
            pass
    await db.clear_all_user_settings(user_id)
    await message.reply(
        "⚙️ **All custom settings have been reset to default:**\n\n"
        "• 🖼️ **Thumbnail:** Reverted to default logo\n"
        "• 📝 **Caption:** Reverted to original post caption\n"
        "• 🏷️ **Prefix & Words:** Cleared\n"
        "• 🎬 **Upload Mode:** Reset to Video player\n"
        "• 🔔 **Silent Mode:** Reset to Sound (ON)\n"
        "• 💬 **Destination:** Reset to Bot Chat\n"
        "• 🛑 **Batch Queue:** Wiped"
    )


# Status command
@Client.on_message(filters.command(["status"]) & filters.private)
async def send_status(client: Client, message: Message):
    total, used, free = shutil.disk_usage(".")
    total_gb = total / (1024 ** 3)
    used_gb = used / (1024 ** 3)
    free_gb = free / (1024 ** 3)

    is_logged_in = bool(await db.get_session(message.from_user.id))
    has_thumb = bool(await db.get_thumb(message.from_user.id))
    custom_caption = await db.get_caption(message.from_user.id)
    upload_mode = "📁 Document" if await db.get_upload_mode(message.from_user.id) else "🎥 Video"
    silent = "🔕 ON" if await db.get_silent(message.from_user.id) else "🔔 OFF"
    to_saved = "📥 Saved Messages" if await db.get_to_saved(message.from_user.id) else "💬 Bot Chat"
    prefix = await db.get_prefix(message.from_user.id)
    removals = await db.get_removals(message.from_user.id)
    batch_task = await db.get_batch_task(message.from_user.id)

    status_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚙️ Open Settings", callback_data="set_menu_main"),
            InlineKeyboardButton("🧹 Clear Chat", callback_data="ui_clear_prompt")
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="help_close")
        ]
    ])

    text = (
        "📊 **Bot Status & Settings Dashboard**\n\n"
        f"> 👤 **Account** • {'✅ Connected' if is_logged_in else '❌ Not Logged In (/login)'}\n"
        f"> 🎬 **Upload Mode** • `{upload_mode}` (/mode)\n"
        f"> 🔔 **Silent Upload** • `{silent}` (/silent)\n"
        f"> 📍 **Destination** • `{to_saved}` (/to_saved)\n"
        f"> 🧹 **Filename Cleaner** • `✅ Always Active`\n"
        f"> 🏷️ **Prefix** • `{prefix or 'None'}` (/set_prefix)\n"
        f"> 🚫 **Custom Removals** • `{', '.join(removals) if removals else 'None'}` (/replace)\n"
        f"> 🖼️ **Thumbnail** • {'✅ Active' if has_thumb else '❌ Default Logo'}\n"
        f"> 📝 **Caption** • {'✅ Custom Template' if custom_caption else '❌ Original Post'}\n\n"
        f"💾 **Host PC Storage:**\n"
        f"• Free: `{free_gb:.1f} GB` / `{total_gb:.1f} GB`\n"
        f"• Used: `{used_gb:.1f} GB`"
    )
    await message.reply(text, reply_markup=status_markup)


# Upload Mode toggle command
@Client.on_message(filters.command(["mode"]) & filters.private)
async def toggle_mode(client: Client, message: Message):
    curr = await db.get_upload_mode(message.from_user.id)
    new_mode = not curr
    await db.set_upload_mode(message.from_user.id, new_mode)
    if new_mode:
        await message.reply("📁 **Upload Mode changed to: Document**\nVideos will now be sent as uncompressed documents preserving original quality.")
    else:
        await message.reply("🎥 **Upload Mode changed to: Video**\nVideos will now be sent as streamable media for Telegram's inline player.")


# Silent Mode toggle
@Client.on_message(filters.command(["silent"]) & filters.private)
async def toggle_silent(client: Client, message: Message):
    curr = await db.get_silent(message.from_user.id)
    new_val = not curr
    await db.set_silent(message.from_user.id, new_val)
    if new_val:
        await message.reply("🔕 **Silent Mode: ON**\nAll uploads will be delivered quietly without triggering notification rings.")
    else:
        await message.reply("🔔 **Silent Mode: OFF**\nUploads will have standard notification sounds.")


# Saved Messages destination toggle
@Client.on_message(filters.command(["to_saved"]) & filters.private)
async def toggle_to_saved(client: Client, message: Message):
    curr = await db.get_to_saved(message.from_user.id)
    new_val = not curr
    await db.set_to_saved(message.from_user.id, new_val)
    if new_val:
        await message.reply("📥 **Destination: Saved Messages**\nDownloads will be sent directly to your personal Saved Messages.")
    else:
        await message.reply("💬 **Destination: Bot Chat**\nDownloads will be delivered here in the bot chat.")


# Set Prefix
@Client.on_message(filters.command(["set_prefix"]) & filters.private)
async def set_prefix(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("📝 **Usage:** `/set_prefix <text>`\nExample: `/set_prefix [Course]`")
    prefix = message.text.split(None, 1)[1].strip()
    await db.set_prefix(message.from_user.id, prefix)
    await message.reply(f"✅ **Filename prefix set to:** `{prefix}`\nAll files will now start with this prefix.")


# Delete Prefix
@Client.on_message(filters.command(["del_prefix"]) & filters.private)
async def del_prefix(client: Client, message: Message):
    await db.del_prefix(message.from_user.id)
    await message.reply("🗑️ **Custom filename prefix removed.**")


# Custom Word Removals
@Client.on_message(filters.command(["replace"]) & filters.private)
async def set_replace(client: Client, message: Message):
    if len(message.command) < 2:
        curr = await db.get_removals(message.from_user.id)
        curr_str = ", ".join(curr) if curr else "None"
        return await message.reply(
            f"📝 **Usage:** `/replace <word1, word2, ...>`\n"
            f"Add words/ads to automatically remove from all filenames.\n\n"
            f"**Current active removals:** `{curr_str}`\n"
            f"*(Note: Standard phrases like 'cracked by', 'extracted by', '@channel' are already removed automatically)*"
        )
    removals = message.text.split(None, 1)[1].strip()
    await db.set_removals(message.from_user.id, removals)
    await message.reply(f"✅ **Custom removal words saved:** `{removals}`")


# Delete Removals
@Client.on_message(filters.command(["del_replace"]) & filters.private)
async def del_replace(client: Client, message: Message):
    await db.del_removals(message.from_user.id)
    await message.reply("🗑️ **Custom removal words cleared.** Standard auto-cleaning remains active.")


# Set Thumbnail
@Client.on_message((filters.command(["set_thumb"]) | filters.photo) & filters.private)
async def set_thumb(client: Client, message: Message):
    photo = None
    if message.reply_to_message and message.reply_to_message.photo:
        photo = message.reply_to_message.photo
    elif message.photo and message.caption and message.caption.startswith("/set_thumb"):
        photo = message.photo

    if not photo:
        if message.text and message.text.startswith("/set_thumb"):
            return await message.reply("📸 **Reply to an image with /set_thumb to save it as your custom thumbnail.**")
        return

    thumb_path = f"{THUMB_DIR}/{message.from_user.id}.jpg"
    await client.download_media(photo.file_id, file_name=thumb_path)
    await db.set_thumb(message.from_user.id, thumb_path)
    await message.reply("✅ **Custom thumbnail saved!** It will be applied to your downloaded videos and files.")


# See Thumbnail
@Client.on_message(filters.command(["see_thumb"]) & filters.private)
async def see_thumb(client: Client, message: Message):
    thumb = await db.get_thumb(message.from_user.id)
    if thumb and os.path.exists(thumb):
        await message.reply_photo(photo=thumb, caption="🖼️ **Your current custom thumbnail.**")
    else:
        await message.reply("❌ **No custom thumbnail set.** Reply to any image with /set_thumb.")


# Delete Thumbnail
@Client.on_message(filters.command(["del_thumb"]) & filters.private)
async def del_thumb(client: Client, message: Message):
    thumb = await db.get_thumb(message.from_user.id)
    if thumb and os.path.exists(thumb):
        try:
            os.remove(thumb)
        except:
            pass
    await db.del_thumb(message.from_user.id)
    await message.reply("🗑️ **Custom thumbnail deleted.** Original thumbnails will be used.")


# Set Caption
@Client.on_message(filters.command(["set_caption"]) & filters.private)
async def set_caption(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply(
            "📝 **Usage:** `/set_caption <your caption text>`\n\n"
            "**Available Tags:**\n"
            "• `{filename}` — Name of the file\n"
            "• `{size}` — Human readable size\n"
            "• `{caption}` — Original caption\n\n"
            "**Example:**\n"
            "`/set_caption 🎬 {filename}\n📦 Size: {size}\n\n{caption}`"
        )
    caption_text = message.text.split(None, 1)[1]
    await db.set_caption(message.from_user.id, caption_text)
    await message.reply(f"✅ **Custom caption template saved:**\n\n{caption_text}")


# See Caption
@Client.on_message(filters.command(["see_caption"]) & filters.private)
async def see_caption(client: Client, message: Message):
    caption = await db.get_caption(message.from_user.id)
    if caption:
        await message.reply(f"📝 **Your current custom caption:**\n\n`{caption}`")
    else:
        await message.reply("❌ **No custom caption set.** Original captions will be used.\nSet one with `/set_caption <text>`.")


# Delete Caption
@Client.on_message(filters.command(["del_caption"]) & filters.private)
async def del_caption(client: Client, message: Message):
    await db.del_caption(message.from_user.id)
    await message.reply("🗑️ **Custom caption deleted.** Original captions will be used.")


# Resume Command (Disabled for DDoS protection and storage hygiene)
@Client.on_message(filters.command(["resume"]) & filters.private)
async def handle_resume_command(client: Client, message: Message):
    try:
        await db.clear_batch_task(message.from_user.id)
    except Exception:
        pass
    await message.reply(
        "❌ **Batch resume is disabled.**\n\n"
        "To protect backend cloud storage from cluttered files and DDoS attack vectors, cancelled tasks are immediately purged.\n"
        "Please send a fresh link to start a new download."
    )


# Topic Command Handler
@Client.on_message(filters.command(["topic"]) & filters.private)
async def crawl_topic_command(client: Client, message: Message):
    if len(message.command) < 2:
        guide_markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📖 Full Topic Guide", callback_data="ui_topic_info"),
                InlineKeyboardButton("❌ Close", callback_data="help_close")
            ]
        ])
        return await message.reply(
            "ℹ️ **How to transfer an entire Forum Topic:**\n\n"
            "Send: `/topic <topic_link>`\n\n"
            "**Examples:**\n"
            "• `/topic https://t.me/c/3641059847/1321/1413`\n"
            "• `/topic https://t.me/c/3641059847/1321`\n\n"
            "• Scans every message, video, and PDF in the topic thread.\n"
            "• Preserves sequence by lecture number & parts.\n"
            "• Generates full Verification Checklist upon completion!",
            reply_markup=guide_markup
        )

    # Strict single-task concurrency check per user
    if TaskManager.is_user_busy(message.from_user.id):
        wait_time = max(WAITING_TIME, 10)
        cancel_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("🛑 Cancel Active Task", callback_data="task_cancel")
        ]])
        return await message.reply_text(
            f"⏳ **Another task is currently in progress!**\n\n"
            f"• Please wait until your ongoing task finishes (~{wait_time}s).\n"
            f"• Or tap below to cancel it immediately.\n\n"
            f"💡 *Strict single-task policy is active to protect server storage.*",
            reply_markup=cancel_markup
        )

    link = message.command[1].strip()
    link_info = parse_tg_link(link)
    if not link_info or not link_info.get("topic_id"):
        return await message.reply(
            f"❌ **Invalid topic link format.**\n"
            f"Received: `{link}`\n\n"
            "Expected:\n`https://t.me/c/<chat_id>/<topic_id>/<msg_id>`\n"
            "Or:\n`https://t.me/c/<chat_id>/<topic_id>`"
        )

    chat_id = link_info["chat_id"]
    topic_id = link_info["topic_id"]
    try:
        await run_topic_crawl(client, message, chat_id, topic_id)
    except Exception as e:
        err_str = str(e)
        if "locked" in err_str.lower():
            await asyncio.sleep(2)
            try:
                await run_topic_crawl(client, message, chat_id, topic_id)
                return
            except Exception as retry_err:
                err_str = str(retry_err)
        await message.reply(f"⚠️ **Topic Transfer Notice:** Unable to complete transfer (`{err_str}`). Please try again shortly.")


# Main Save / Link Handler (Processes raw links, non-commands)
@Client.on_message(filters.text & ~filters.regex(r"^/") & filters.private, group=10)
async def handle_message_transfer(client: Client, message: Message):
    if message.text.startswith("/"):
        raise pyrogram.ContinuePropagation

    # Strict single-task concurrency check per user
    if TaskManager.is_user_busy(message.from_user.id):
        wait_time = max(WAITING_TIME, 10)
        cancel_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("🛑 Cancel Active Task", callback_data="task_cancel")
        ]])
        return await message.reply_text(
            f"⏳ **Another task is currently in progress!**\n\n"
            f"• Please wait until your ongoing task finishes (~{wait_time}s).\n"
            f"• Or tap below to cancel it immediately.\n\n"
            f"💡 *Strict single-task policy is active to protect server storage.*",
            reply_markup=cancel_markup
        )

    # 1. External Web URLs (yt-dlp)
    if is_web_url(message.text):
        await handle_web_url(client, message)
        return

    # 2. Joining invite link for private chat
    if ("https://t.me/+" in message.text or "https://t.me/joinchat/" in message.text) and LOGIN_SYSTEM == False:
        if UserClient is None:
            await client.send_message(message.chat.id, "String Session is not set.", reply_to_message_id=message.id)
            return
        try:
            try:
                await UserClient.join_chat(message.text)
            except Exception as e: 
                await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id)
                return
            await client.send_message(message.chat.id, "Chat joined successfully!", reply_to_message_id=message.id)
        except UserAlreadyParticipant:
            await client.send_message(message.chat.id, "Already a participant in this chat.", reply_to_message_id=message.id)
        except InviteHashExpired:
            await client.send_message(message.chat.id, "Invite link has expired.", reply_to_message_id=message.id)
        return

    # 3. Telegram Post Links (Channels, Groups, Forum Topics)
    if "https://t.me/" in message.text:
        link_info = parse_tg_link(message.text)
        if not link_info:
            return await message.reply_text("❌ **Invalid link format.** Check /help for link syntax.")

        fromID = link_info["from_id"]
        toID = link_info["to_id"]

        # Automatically crawl topic thread if topic root link is provided
        if link_info.get("kind") == "topic" and fromID == link_info.get("topic_id"):
            return await run_topic_crawl(client, message, link_info["chat_id"], link_info["topic_id"])

        await run_batch_download(client, message, message.text, fromID, toID, parsed_info=link_info)


# Smart User Session Resolver (with automatic multi-account fallback)
async def get_user_client(user_id: int, target_chat_id: int = None):
    """
    Returns an authorized Client for the user.
    If target_chat_id is provided and the user's session cannot access it,
    it automatically checks other registered sessions in the database as fallback.
    """
    candidates = []
    user_data = await db.get_session(user_id)
    if user_data:
        api_id = int(await db.get_api_id(user_id) or API_ID)
        api_hash = await db.get_api_hash(user_id) or API_HASH
        candidates.append((user_id, user_data, api_id, api_hash))

    try:
        other_sessions = await db.get_all_other_sessions(user_id)
        for u_id, s_str, a_id, a_hash in other_sessions:
            candidates.append((u_id, s_str, int(a_id or API_ID), a_hash or API_HASH))
    except Exception:
        pass

    for cand_uid, cand_session, cand_aid, cand_ahash in candidates:
        try:
            cand_acc = Client(
                f"acc_{cand_uid}_{int(time.time()*1000)%10000}",
                session_string=cand_session,
                api_id=cand_aid,
                api_hash=cand_ahash,
                in_memory=True,
                sleep_threshold=60,
                max_concurrent_transmissions=2
            )
            await cand_acc.connect()
            if target_chat_id:
                try:
                    await cand_acc.get_chat(target_chat_id)
                    return cand_acc
                except Exception:
                    await cand_acc.disconnect()
                    continue
            else:
                return cand_acc
        except Exception:
            pass

    return None


# Batch Engine with Auto-Resume Tracking and Audit Reporting
async def run_batch_download(client: Client, message: Message, link_text: str, fromID: int, toID: int, resume_orig_from: int = None, parsed_info: dict = None):
    orig_from = resume_orig_from or fromID
    link_info = parsed_info or parse_tg_link(link_text)

    acc = None
    if LOGIN_SYSTEM == True:
        target_chat = link_info.get("chat_id") if link_info else None
        acc = await get_user_client(message.from_user.id, target_chat_id=target_chat)
        if acc is None:
            await message.reply("🔒 **Access Denied:** Neither your account nor any connected user session has access to this chat.\nPlease /login or make sure your account has joined first.")
            return
    else:
        if UserClient is None:
            await client.send_message(message.chat.id, "**String session is not set.**", reply_to_message_id=message.id)
            return
        acc = UserClient

    TaskManager.start_task(message.from_user.id, "batch_download")
    completed_all = True
    target_title = f"Topic #{link_info['topic_id']}" if link_info and link_info.get("topic_id") else f"Posts {fromID}-{toID}"
    tracker = AuditTracker(topic_title=target_title)

    try:
        for msgid in range(fromID, toID + 1):
            if TaskManager.is_cancelled(message.from_user.id):
                completed_all = False
                TaskManager.purge_user_files(message.from_user.id)
                break
            
            try:
                # 1. Topic or Private channel
                if link_info and link_info.get("chat_id"):
                    chatid = link_info["chat_id"]
                    ok, res_filename, serial, title, part = await handle_media(client, acc, message, chatid, msgid)
                    if ok:
                        tracker.record_item(msgid, serial, title, part, res_filename, "success")
                    else:
                        tracker.record_item(msgid, "", "", "", f"post_{msgid}", "skipped")

                # 2. Public channel
                elif link_info and link_info.get("username"):
                    username = link_info["username"]
                    try:
                        msg = await client.get_messages(username, msgid)
                    except UsernameNotOccupied: 
                        await client.send_message(message.chat.id, "The username is not occupied by anyone.", reply_to_message_id=message.id)
                        return
                    try:
                        silent = await db.get_silent(message.from_user.id)
                        dest = await get_destination(client, message)
                        await client.copy_message(dest, msg.chat.id, msg.id, reply_to_message_id=message.id, disable_notification=silent)
                        tracker.record_item(msgid, "", getattr(msg, "text", f"post_{msgid}")[:30], "", f"post_{msgid}", "success")
                    except:
                        ok, res_filename, serial, title, part = await handle_media(client, acc, message, username, msgid)
                        if ok:
                            tracker.record_item(msgid, serial, title, part, res_filename, "success")
                        else:
                            tracker.record_item(msgid, "", "", "", f"post_{msgid}", "skipped")

                # Fallback for old link structures
                elif "https://t.me/c/" in link_text:
                    datas = link_text.split("/")
                    chatid = int("-100" + datas[4])
                    ok, res_filename, serial, title, part = await handle_media(client, acc, message, chatid, msgid)
                    if ok:
                        tracker.record_item(msgid, serial, title, part, res_filename, "success")

            except FloodWait as e:
                await client.send_message(
                    message.chat.id, 
                    f"⚠️ **Telegram FloodWait:** Waiting `{e.value}` seconds before resuming..."
                )
                await asyncio.sleep(e.value)
            except Exception as e:
                if ERROR_MESSAGE == True:
                    await client.send_message(message.chat.id, f"Error on post {msgid}: {e}", reply_to_message_id=message.id)
                tracker.record_item(msgid, "", "", "", f"post_{msgid}", "error")

            await asyncio.sleep(WAITING_TIME)

        if completed_all and fromID <= toID:
            await client.send_message(message.chat.id, tracker.generate_report())

    finally:
        if LOGIN_SYSTEM == True and acc:
            try:
                await acc.disconnect()
            except:
                pass
        TaskManager.finish_task(message.from_user.id)
        try:
            await db.clear_batch_task(message.from_user.id)
        except Exception:
            pass



# Handle Any Media Type (PDF, ZIP, APK, MP4, MP3, Photo, etc.)
async def handle_media(client: Client, acc, message: Message, chatid, msgid: int):
    msg: Message = await acc.get_messages(chatid, msgid)
    if not msg or msg.empty:
        return (False, None, None, None, None)
    msg_type = get_message_type(msg)
    if not msg_type:
        return (False, None, None, None, None)

    dest = await get_destination(client, message)
    silent = await db.get_silent(message.from_user.id)

    if TaskManager.is_cancelled(message.from_user.id):
        return (False, None, None, None, None)

    # Plain text messages
    if "Text" == msg_type:
        try:
            reply_id = message.id if dest == message.chat.id else None
            if msg.entities:
                try:
                    await client.send_message(dest, msg.text, entities=msg.entities, reply_to_message_id=reply_id, disable_notification=silent)
                except Exception:
                    await client.send_message(dest, msg.text, reply_to_message_id=reply_id, disable_notification=silent)
            else:
                await client.send_message(dest, msg.text, reply_to_message_id=reply_id, disable_notification=silent)
            return (True, "Text", None, None, None)
        except Exception as e:
            if ERROR_MESSAGE == True:
                await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)
            return (False, None, None, None, None)

    smsg = await client.send_message(message.chat.id, '⏳ **Starting download...**', reply_to_message_id=message.id)
    start_time = time.time()
    file = None
    ph_path = None
    success = False
    serial = None
    title = None
    part = None
    filename = None

    try:
        # Download any media type with in-memory progress bar
        file = await acc.download_media(
            msg, 
            file_name=f"{DOWNLOAD_DIR}/",
            progress=progress_for_pyrogram, 
            progress_args=("📥 Downloading", smsg, start_time)
        )
        if file:
            TaskManager.register_file(message.from_user.id, file)

        if TaskManager.is_cancelled(message.from_user.id):
            if file and os.path.exists(file):
                try:
                    os.remove(file)
                except Exception:
                    pass
            return (False, None, None, None, None)

        prefix = await db.get_prefix(message.from_user.id)
        removals = await db.get_removals(message.from_user.id)
        orig_basename = os.path.basename(file)
        orig_caption = msg.caption or msg.text or ""

        # Smart course organizer: extracts serial, title, and part across ANY topic/course
        serial, title, part = parse_course_metadata(orig_caption, orig_basename)
        organized_name = format_organized_filename(orig_caption, orig_basename, prefix=prefix, custom_removals=removals)

        if organized_name != orig_basename:
            file_dir = os.path.dirname(file)
            new_file_path = os.path.join(file_dir, organized_name)
            try:
                if os.path.exists(new_file_path) and new_file_path != file:
                    os.remove(new_file_path)
                os.rename(file, new_file_path)
                file = new_file_path
            except Exception:
                file = rename_file_clean(file, prefix=prefix, custom_removals=removals)
        else:
            file = rename_file_clean(file, prefix=prefix, custom_removals=removals)

        filename = os.path.basename(file)
        filesize = humanbytes(os.path.getsize(file))

        # Caption formatting: custom template if set, else organized caption
        user_caption_tmpl = await db.get_caption(message.from_user.id)
        caption = format_organized_caption(orig_caption, filename, filesize, custom_tmpl=user_caption_tmpl)

        # Thumbnail management (applies to Document, Video, Audio)
        user_thumb = await db.get_thumb(message.from_user.id)
        if user_thumb and os.path.exists(user_thumb):
            ph_path = user_thumb
        else:
            try:
                media_obj = getattr(msg, msg_type.lower(), None)
                if media_obj and hasattr(media_obj, 'thumbs') and media_obj.thumbs:
                    ph_path = await acc.download_media(media_obj.thumbs[0].file_id)
            except:
                ph_path = None
            if not ph_path and os.path.exists(DEFAULT_THUMB):
                ph_path = DEFAULT_THUMB

        upload_as_doc = await db.get_upload_mode(message.from_user.id)
        up_start_time = time.time()

        # 1. Documents (PDF, ZIP, RAR, APK, etc.) OR Videos in Document Mode
        if "Document" == msg_type or ("Video" == msg_type and upload_as_doc):
            await client.send_document(
                dest, 
                file, 
                thumb=ph_path, 
                caption=caption, 
                reply_to_message_id=message.id, 
                parse_mode=enums.ParseMode.HTML, 
                disable_notification=silent,
                progress=progress_for_pyrogram, 
                progress_args=("📤 Uploading", smsg, up_start_time)
            )
            success = True

        # 2. Videos (streamable)
        elif "Video" == msg_type:
            await client.send_video(
                dest, 
                file, 
                duration=getattr(msg.video, 'duration', 0), 
                width=getattr(msg.video, 'width', 0), 
                height=getattr(msg.video, 'height', 0), 
                thumb=ph_path, 
                caption=caption, 
                reply_to_message_id=message.id, 
                parse_mode=enums.ParseMode.HTML, 
                disable_notification=silent,
                progress=progress_for_pyrogram, 
                progress_args=("📤 Uploading", smsg, up_start_time)
            )
            success = True

        # 3. Audio files (.mp3, .m4a, .flac, etc.)
        elif "Audio" == msg_type:
            await client.send_audio(
                dest, 
                file, 
                thumb=ph_path, 
                caption=caption, 
                reply_to_message_id=message.id, 
                parse_mode=enums.ParseMode.HTML, 
                disable_notification=silent,
                progress=progress_for_pyrogram, 
                progress_args=("📤 Uploading", smsg, up_start_time)
            )
            success = True

        # 4. Photos
        elif "Photo" == msg_type:
            await client.send_photo(dest, file, caption=caption, reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML, disable_notification=silent)
            success = True

        # 5. Voice Notes
        elif "Voice" == msg_type:
            await client.send_voice(
                dest, 
                file, 
                caption=caption, 
                reply_to_message_id=message.id, 
                parse_mode=enums.ParseMode.HTML, 
                disable_notification=silent,
                progress=progress_for_pyrogram, 
                progress_args=("📤 Uploading", smsg, up_start_time)
            )
            success = True

        # 6. Animations (GIFs)
        elif "Animation" == msg_type:
            await client.send_animation(dest, file, reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML, disable_notification=silent)
            success = True

        # 7. Stickers
        elif "Sticker" == msg_type:
            await client.send_sticker(dest, file, reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML, disable_notification=silent)
            success = True

    except Exception as e:
        if ERROR_MESSAGE == True:
            await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)
    finally:
        # Automatic Disk Cleanup: Always delete downloaded file
        if file and os.path.exists(file):
            try:
                os.remove(file)
            except:
                pass
        if ph_path and os.path.exists(ph_path) and not ph_path.startswith(THUMB_DIR):
            try:
                os.remove(ph_path)
            except:
                pass
        try:
            await smsg.delete()
        except:
            pass

    return (success, filename, serial, title, part)


# Topic Crawler Engine (Scans & transfers all media and text in a topic thread)
async def run_topic_crawl(client: Client, message: Message, chat_id: int, topic_id: int):
    TaskManager.start_task(message.from_user.id, "topic_crawl")
    status_msg = await message.reply(f"🔍 **Connecting & Scanning Topic #{topic_id}...**")
    acc = None
    if LOGIN_SYSTEM == True:
        acc = await get_user_client(message.from_user.id, target_chat_id=chat_id)
        if acc is None:
            TaskManager.finish_task(message.from_user.id)
            return await status_msg.edit_text(
                "🔒 **Access Denied:** Neither your account nor any connected session has joined this private group.\n"
                "Please make sure your Telegram account has joined the group first or send its invite link."
            )
    else:
        if UserClient is None:
            TaskManager.finish_task(message.from_user.id)
            return await status_msg.edit_text("**String session is not set.**")
        acc = UserClient

    dest = await get_destination(client, message)

    try:
        all_messages = []
        # 1. Fetch root topic message if it has content
        try:
            root_msg = await acc.get_messages(chat_id, topic_id)
            if root_msg and not root_msg.empty:
                if get_message_type(root_msg):
                    all_messages.append(root_msg)
        except Exception:
            pass

        # 2. In Telegram Forum Supergroups, topic messages are replies to the topic thread root message (topic_id)
        try:
            async for msg in acc.get_discussion_replies(chat_id, topic_id):
                if TaskManager.is_cancelled(message.from_user.id):
                    break
                if get_message_type(msg):
                    all_messages.append(msg)
        except Exception:
            # Fallback: scan recent history and match thread ID
            async for msg in acc.get_chat_history(chat_id, limit=500):
                if TaskManager.is_cancelled(message.from_user.id):
                    break
                if getattr(msg, "message_thread_id", None) == topic_id or getattr(msg, "topic_id", None) == topic_id:
                    if get_message_type(msg):
                        all_messages.append(msg)

        # Deduplicate & sort ascending so messages transfer in exact chronological sequence
        seen_ids = set()
        unique_messages = []
        for m in all_messages:
            if m.id not in seen_ids:
                seen_ids.add(m.id)
                unique_messages.append(m)
        unique_messages.sort(key=lambda m: m.id)

        if not unique_messages:
            return await status_msg.edit_text(
                f"❌ **No content messages found in Topic #{topic_id}.**\n"
                "Make sure the topic thread contains text messages, documents, or videos."
            )

        # Pure Sequential Transfer: Download and upload one file at a time using identical single-video cards
        tracker = AuditTracker(topic_title=f"Topic #{topic_id}")
        total_items = len(unique_messages)
        prefix = await db.get_prefix(message.from_user.id)
        removals = await db.get_removals(message.from_user.id)
        user_caption_tmpl = await db.get_caption(message.from_user.id)
        user_thumb = await db.get_thumb(message.from_user.id)
        upload_as_doc = await db.get_upload_mode(message.from_user.id)
        silent = await db.get_silent(message.from_user.id)

        for idx, msg in enumerate(unique_messages, 1):
            if TaskManager.is_cancelled(message.from_user.id):
                TaskManager.purge_user_files(message.from_user.id)
                break

            m_type = get_message_type(msg)
            if not m_type:
                continue

            # 1. Plain text messages
            if m_type == "Text":
                try:
                    if msg.entities:
                        try:
                            await client.send_message(dest, msg.text, entities=msg.entities, disable_notification=silent)
                        except Exception:
                            await client.send_message(dest, msg.text, disable_notification=silent)
                    else:
                        await client.send_message(dest, msg.text, disable_notification=silent)
                    tracker.record_item(msg.id, "", (msg.text[:30].replace("\n", " ") + "..."), "", "Text Message", "success")
                except Exception:
                    tracker.record_item(msg.id, "", f"post_{msg.id}", "", "Text Message", "error")
                await asyncio.sleep(min(WAITING_TIME, 2))
                continue

            # 2. Media message (Video, Document, Audio, Photo, etc.)
            file = None
            ph_path = None
            success = False
            item_serial = None
            item_title = None
            item_part = None
            final_filename = None

            try:
                # Update status message for current item
                dl_label = f"📥 Downloading [{idx}/{total_items}]"
                start_time = time.time()
                file = await acc.download_media(
                    msg,
                    file_name=f"{DOWNLOAD_DIR}/",
                    progress=progress_for_pyrogram,
                    progress_args=(dl_label, status_msg, start_time)
                )

                if TaskManager.is_cancelled(message.from_user.id):
                    TaskManager.purge_user_files(message.from_user.id)
                    break

                if not file or not os.path.exists(file):
                    tracker.record_item(msg.id, "", "", "", f"post_{msg.id}", "skipped")
                    continue

                TaskManager.register_file(message.from_user.id, file)

                orig_basename = os.path.basename(file)
                orig_caption = msg.caption or msg.text or ""
                item_serial, item_title, item_part = parse_course_metadata(orig_caption, orig_basename)
                organized_name = format_organized_filename(orig_caption, orig_basename, prefix=prefix, custom_removals=removals)

                if organized_name != orig_basename:
                    file_dir = os.path.dirname(file)
                    new_file_path = os.path.join(file_dir, organized_name)
                    try:
                        if os.path.exists(new_file_path) and new_file_path != file:
                            os.remove(new_file_path)
                        os.rename(file, new_file_path)
                        file = new_file_path
                    except Exception:
                        file = rename_file_clean(file, prefix=prefix, custom_removals=removals)
                else:
                    file = rename_file_clean(file, prefix=prefix, custom_removals=removals)

                final_filename = os.path.basename(file)
                filesize = humanbytes(os.path.getsize(file))
                caption = format_organized_caption(orig_caption, final_filename, filesize, custom_tmpl=user_caption_tmpl)

                # Thumbnail resolution
                if user_thumb and os.path.exists(user_thumb):
                    ph_path = user_thumb
                else:
                    try:
                        media_obj = getattr(msg, m_type.lower(), None)
                        if media_obj and hasattr(media_obj, 'thumbs') and media_obj.thumbs:
                            ph_path = await acc.download_media(media_obj.thumbs[0].file_id)
                    except Exception:
                        ph_path = None
                    if not ph_path and os.path.exists(DEFAULT_THUMB):
                        ph_path = DEFAULT_THUMB

                up_label = f"📤 Uploading [{idx}/{total_items}]"
                up_start_time = time.time()

                if m_type == "Document" or (m_type == "Video" and upload_as_doc):
                    await client.send_document(
                        dest,
                        file,
                        thumb=ph_path,
                        caption=caption,
                        parse_mode=enums.ParseMode.HTML,
                        disable_notification=silent,
                        progress=progress_for_pyrogram,
                        progress_args=(up_label, status_msg, up_start_time)
                    )
                    success = True
                elif m_type == "Video":
                    await client.send_video(
                        dest,
                        file,
                        duration=getattr(msg.video, 'duration', 0),
                        width=getattr(msg.video, 'width', 0),
                        height=getattr(msg.video, 'height', 0),
                        thumb=ph_path,
                        caption=caption,
                        parse_mode=enums.ParseMode.HTML,
                        disable_notification=silent,
                        progress=progress_for_pyrogram,
                        progress_args=(up_label, status_msg, up_start_time)
                    )
                    success = True
                elif m_type == "Audio":
                    await client.send_audio(
                        dest,
                        file,
                        thumb=ph_path,
                        caption=caption,
                        parse_mode=enums.ParseMode.HTML,
                        disable_notification=silent,
                        progress=progress_for_pyrogram,
                        progress_args=(up_label, status_msg, up_start_time)
                    )
                    success = True
                elif m_type == "Photo":
                    await client.send_photo(dest, file, caption=caption, parse_mode=enums.ParseMode.HTML, disable_notification=silent)
                    success = True
                elif m_type == "Voice":
                    await client.send_voice(
                        dest,
                        file,
                        caption=caption,
                        parse_mode=enums.ParseMode.HTML,
                        disable_notification=silent,
                        progress=progress_for_pyrogram,
                        progress_args=(up_label, status_msg, up_start_time)
                    )
                    success = True
                elif m_type == "Animation":
                    await client.send_animation(dest, file, parse_mode=enums.ParseMode.HTML, disable_notification=silent)
                    success = True
                elif m_type == "Sticker":
                    await client.send_sticker(dest, file, parse_mode=enums.ParseMode.HTML, disable_notification=silent)
                    success = True

            except FloodWait as e:
                await client.send_message(message.chat.id, f"⚠️ **Telegram FloodWait:** Waiting `{e.value}` seconds...")
                await asyncio.sleep(e.value + 1)
            except Exception as e:
                if ERROR_MESSAGE:
                    await client.send_message(message.chat.id, f"❌ Error on `{final_filename or f'post_{msg.id}'}`: {e}")
            finally:
                # Immediate Disk Cleanup: delete downloaded file and temp thumb
                if file and os.path.exists(file):
                    try:
                        os.remove(file)
                    except Exception:
                        pass
                if ph_path and os.path.exists(ph_path) and not ph_path.startswith(THUMB_DIR):
                    try:
                        os.remove(ph_path)
                    except Exception:
                        pass

            if success:
                tracker.record_item(msg.id, item_serial, item_title or final_filename, item_part, final_filename, "success")
            else:
                tracker.record_item(msg.id, item_serial, item_title or f"post_{msg.id}", item_part, final_filename or f"post_{msg.id}", "error")

            await asyncio.sleep(min(WAITING_TIME, 2))

        # Transfer complete: clean up reusable progress message & deliver report
        try:
            await status_msg.delete()
        except Exception:
            pass

        if not TaskManager.is_cancelled(message.from_user.id):
            await client.send_message(message.chat.id, tracker.generate_report())

    except Exception as e:
        err_msg = str(e)
        if "locked" in err_msg.lower():
            err_msg = "Database lock resolved. Please re-run your transfer."
        await client.send_message(message.chat.id, f"⚠️ **Topic Transfer Notice:** `{err_msg}`")
    finally:
        if LOGIN_SYSTEM == True and acc:
            try:
                await acc.disconnect()
            except:
                pass
        TaskManager.finish_task(message.from_user.id)





# Handle External Web URLs (YouTube, Instagram, X/Twitter, direct links)
async def handle_web_url(client: Client, message: Message):
    TaskManager.start_task(message.from_user.id, "web_download")
    smsg = await client.send_message(message.chat.id, "🌐 **Downloading media with yt-dlp...**", reply_to_message_id=message.id)
    file = None
    ph_path = None
    dest = await get_destination(client, message)
    silent = await db.get_silent(message.from_user.id)
    upload_as_doc = await db.get_upload_mode(message.from_user.id)

    try:
        file, title, duration = await download_web_media(message.text.strip(), DOWNLOAD_DIR)
        if file:
            TaskManager.register_file(message.from_user.id, file)

        if TaskManager.is_cancelled(message.from_user.id):
            return
        
        prefix = await db.get_prefix(message.from_user.id)
        removals = await db.get_removals(message.from_user.id)
        file = rename_file_clean(file, prefix=prefix, custom_removals=removals)
        if file:
            TaskManager.register_file(message.from_user.id, file)

        filename = os.path.basename(file)
        filesize = humanbytes(os.path.getsize(file))

        user_caption_tmpl = await db.get_caption(message.from_user.id)
        if user_caption_tmpl:
            caption = user_caption_tmpl.replace("{filename}", filename).replace("{size}", filesize).replace("{caption}", title)
        else:
            caption = f"🎬 **{filename}**\n📁 `{filesize}`"

        user_thumb = await db.get_thumb(message.from_user.id)
        if user_thumb and os.path.exists(user_thumb):
            ph_path = user_thumb
        elif os.path.exists(DEFAULT_THUMB):
            ph_path = DEFAULT_THUMB

        up_start = time.time()
        is_video = file.lower().endswith(('.mp4', '.mkv', '.webm', '.mov'))

        if is_video and not upload_as_doc:
            await client.send_video(
                dest, 
                file, 
                duration=int(duration or 0), 
                thumb=ph_path, 
                caption=caption, 
                parse_mode=enums.ParseMode.HTML,
                disable_notification=silent, 
                progress=progress_for_pyrogram, 
                progress_args=("📤 Uploading", smsg, up_start)
            )
        else:
            await client.send_document(
                dest, 
                file, 
                thumb=ph_path, 
                caption=caption, 
                parse_mode=enums.ParseMode.HTML,
                disable_notification=silent, 
                progress=progress_for_pyrogram, 
                progress_args=("📤 Uploading", smsg, up_start)
            )

    except Exception as e:
        await client.send_message(message.chat.id, f"❌ **Web download error:** `{e}`")
    finally:
        TaskManager.finish_task(message.from_user.id)
        if file and os.path.exists(file):
            try:
                os.remove(file)
            except:
                pass
        try:
            await smsg.delete()
        except:
            pass


# Detect Media Type
def get_message_type(msg: pyrogram.types.messages_and_media.message.Message):
    for t in ["document", "video", "audio", "photo", "animation", "sticker", "voice"]:
        if hasattr(msg, t) and getattr(msg, t) is not None:
            return t.capitalize()
    if hasattr(msg, "text") and msg.text is not None:
        return "Text"
    return None
