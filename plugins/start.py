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
from plugins.organizer import parse_tg_link, parse_course_metadata, format_organized_filename, format_organized_caption, AuditTracker
from plugins.pipeline import run_pipelined_transfer, get_message_type
from plugins.ytdl import is_web_url, download_web_media
from bot import UserClient

DOWNLOAD_DIR = "downloads"
THUMB_DIR = "database/thumbs"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(THUMB_DIR, exist_ok=True)

class batch_temp(object):
    IS_BATCH = {}


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

# Start command
@Client.on_message(filters.command(["start"]) & filters.private)
async def send_start(client: Client, message: Message):
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
    start_text = (
        f"👋 **Hi {message.from_user.mention}**, I am **Aditya's Save Restricted Content Bot**.\n\n"
        f"• Connect your account with **/login** to access restricted chats.\n"
        f"• Check commands and link syntax with **/help**.\n"
        f"• Check storage and settings with **/status**.\n"
        f"• Auto-cleaner is **always active** for all files (PDF, ZIP, APK, MP4, MP3, etc.)."
    )
    if os.path.exists(LOGO_PATH):
        await client.send_photo(
            chat_id=message.chat.id,
            photo=LOGO_PATH,
            caption=start_text,
            reply_to_message_id=message.id
        )
    else:
        await client.send_message(
            chat_id=message.chat.id,
            text=start_text,
            reply_to_message_id=message.id
        )


# Interactive Help command
@Client.on_message(filters.command(["help"]) & filters.private)
async def send_help(client: Client, message: Message):
    await client.send_message(
        chat_id=message.chat.id, 
        text=HELP_MAIN_TXT,
        reply_markup=get_help_main_markup(),
        reply_to_message_id=message.id
    )


# Help Callback Query Handler
@Client.on_callback_query(filters.regex(r"^help_"))
async def help_callback(client: Client, query: CallbackQuery):
    data = query.data
    if data == "help_close":
        await query.message.delete()
        return

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
        except:
            pass


# Cancel command
@Client.on_message(filters.command(["cancel"]) & filters.private)
async def send_cancel(client: Client, message: Message):
    batch_temp.IS_BATCH[message.from_user.id] = True
    await client.send_message(
        chat_id=message.chat.id, 
        text="🛑 **Batch process cancelled.** You can resume anytime using /resume."
    )


# Clear command: clears chats from both sides in one click
@Client.on_message(filters.command(["clear"]) & filters.private)
async def clear_chat_history(client: Client, message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    current_msg_id = message.id

    # 1. Stop any ongoing batch task for this user
    batch_temp.IS_BATCH[user_id] = True

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
    batch_temp.IS_BATCH[user_id] = True
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

    batch_info = "None"
    if batch_task and batch_task.get('last_id') and batch_task.get('to_id'):
        batch_info = f"Post {batch_task['last_id']} of {batch_task['to_id']} (/resume)"

    text = (
        "📊 **Bot Status & Settings Dashboard**\n\n"
        f"👤 **Account:** {'✅ Connected' if is_logged_in else '❌ Not Logged In (/login)'}\n"
        f"🎬 **Upload Mode:** `{upload_mode}` (/mode)\n"
        f"🔔 **Silent Upload:** `{silent}` (/silent)\n"
        f"📍 **Destination:** `{to_saved}` (/to_saved)\n"
        f"🧹 **Filename Cleaner:** `✅ Always Active`\n"
        f"🏷️ **Prefix:** `{prefix or 'None'}` (/set_prefix)\n"
        f"🚫 **Custom Removals:** `{', '.join(removals) if removals else 'None'}` (/replace)\n"
        f"🖼️ **Thumbnail:** {'✅ Active' if has_thumb else '❌ Default (/set_thumb)'}\n"
        f"📝 **Caption:** {'✅ Active' if custom_caption else '❌ Original (/set_caption)'}\n"
        f"🔄 **Unfinished Batch:** `{batch_info}`\n\n"
        f"💾 **Host PC Storage:**\n"
        f"• Free: `{free_gb:.1f} GB` / `{total_gb:.1f} GB`\n"
        f"• Used: `{used_gb:.1f} GB`"
    )
    await message.reply(text)


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


# Resume Command
@Client.on_message(filters.command(["resume"]) & filters.private)
async def resume_batch(client: Client, message: Message):
    task = await db.get_batch_task(message.from_user.id)
    if not task:
        return await message.reply("❌ **No interrupted batch download found to resume.**")

    last_id = task.get('last_id', 0)
    to_id = task.get('to_id', 0)
    link_prefix = task.get('link_prefix', '')

    if last_id >= to_id:
        await db.clear_batch_task(message.from_user.id)
        return await message.reply("✅ **Your previous batch was already completed!**")

    next_id = last_id + 1
    await message.reply(f"🔄 **Resuming batch from post {next_id} to {to_id}...**")
    await run_batch_download(client, message, link_prefix, next_id, to_id, resume_orig_from=task.get('from_id', next_id))


# Topic Command Handler
@Client.on_message(filters.command(["topic"]) & filters.private)
async def crawl_topic_command(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply(
            "ℹ️ **How to transfer an entire Forum Topic:**\n\n"
            "Send: `/topic <topic_link>`\n"
            "Example:\n`/topic https://t.me/c/3641059847/1321/1413`\n"
            "Or:\n`/topic https://t.me/c/3641059847/1321`\n\n"
            "• Automatically scans all files inside that topic\n"
            "• Preserves sequence by lecture number & parts\n"
            "• Generates a full Verification & Audit Checklist!"
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
        await message.reply(f"❌ **Topic Transfer Error:** `{e}`")


# Main Save / Link Handler (Processes raw links, non-commands)
@Client.on_message(filters.text & ~filters.regex(r"^/") & filters.private, group=10)
async def save(client: Client, message: Message):
    if message.text.startswith("/"):
        raise pyrogram.ContinuePropagation


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
        if batch_temp.IS_BATCH.get(message.from_user.id) == False:
            return await message.reply_text("⏳ **Another task is currently processing.**\nPlease wait for it to finish or send /cancel to stop it.")

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
            cand_acc = Client(f"acc_{cand_uid}_{int(time.time()*1000)%10000}", session_string=cand_session, api_id=cand_aid, api_hash=cand_ahash, in_memory=True)
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

    batch_temp.IS_BATCH[message.from_user.id] = False
    completed_all = True
    target_title = f"Topic #{link_info['topic_id']}" if link_info and link_info.get("topic_id") else f"Posts {fromID}-{toID}"
    tracker = AuditTracker(topic_title=target_title)

    try:
        for msgid in range(fromID, toID + 1):
            if batch_temp.IS_BATCH.get(message.from_user.id):
                completed_all = False
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

                # Save progress after each successful item for /resume
                await db.save_batch_task(
                    user_id=message.from_user.id,
                    link_prefix=link_text,
                    from_id=orig_from,
                    to_id=toID,
                    last_id=msgid,
                    chat_id=str(link_info.get("chat_id") or link_info.get("username") or "chat") if link_info else "chat",
                    task_type="batch"
                )

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
            await db.clear_batch_task(message.from_user.id)
            await client.send_message(message.chat.id, tracker.generate_report())

    finally:
        if LOGIN_SYSTEM == True:
            try:
                await acc.disconnect()
            except:
                pass                				
        batch_temp.IS_BATCH[message.from_user.id] = True



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

    if batch_temp.IS_BATCH.get(message.from_user.id):
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
        
        if batch_temp.IS_BATCH.get(message.from_user.id):
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
    status_msg = await message.reply(f"🔍 **Connecting & Scanning Topic #{topic_id}...**")
    acc = None
    if LOGIN_SYSTEM == True:
        acc = await get_user_client(message.from_user.id, target_chat_id=chat_id)
        if acc is None:
            return await status_msg.edit_text(
                "🔒 **Access Denied:** Neither your account nor any connected session has joined this private group.\n"
                "Please make sure your Telegram account has joined the group first or send its invite link."
            )
    else:
        if UserClient is None:
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
                if batch_temp.IS_BATCH.get(message.from_user.id):
                    break
                if get_message_type(msg):
                    all_messages.append(msg)
        except Exception:
            # Fallback: scan recent history and match thread ID
            async for msg in acc.get_chat_history(chat_id, limit=500):
                if batch_temp.IS_BATCH.get(message.from_user.id):
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

        # Launch Pipelined Lookahead Transfer with Live Queue Monitor
        await run_pipelined_transfer(
            client=client,
            acc=acc,
            user_message=message,
            dest=dest,
            messages_list=unique_messages,
            title=f"Topic #{topic_id}",
            status_msg=status_msg,
            batch_temp_dict=batch_temp.IS_BATCH
        )

    except Exception as e:
        await client.send_message(message.chat.id, f"❌ **Error during topic transfer:** `{e}`")
    finally:
        if LOGIN_SYSTEM == True and acc:
            try:
                await acc.disconnect()
            except:
                pass
        batch_temp.IS_BATCH[message.from_user.id] = True





# Handle External Web URLs (YouTube, Instagram, X/Twitter, direct links)
async def handle_web_url(client: Client, message: Message):
    smsg = await client.send_message(message.chat.id, "🌐 **Downloading media with yt-dlp...**", reply_to_message_id=message.id)
    file = None
    ph_path = None
    dest = await get_destination(client, message)
    silent = await db.get_silent(message.from_user.id)
    upload_as_doc = await db.get_upload_mode(message.from_user.id)

    try:
        file, title, duration = await download_web_media(message.text.strip(), DOWNLOAD_DIR)
        
        prefix = await db.get_prefix(message.from_user.id)
        removals = await db.get_removals(message.from_user.id)
        file = rename_file_clean(file, prefix=prefix, custom_removals=removals)
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
