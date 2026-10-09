from pyrogram.errors import InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from database.db import db
from pyrogram import Client, filters
from config import ADMINS
import asyncio
import datetime
import time

async def broadcast_messages(user_id, message):
    try:
        await message.copy(chat_id=user_id)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages(user_id, message)
    except InputUserDeactivated:
        await db.delete_user(int(user_id))
        return False, "Deleted"
    except UserIsBlocked:
        await db.delete_user(int(user_id))
        return False, "Blocked"
    except PeerIdInvalid:
        await db.delete_user(int(user_id))
        return False, "Error"
    except Exception:
        return False, "Error"


@Client.on_message(filters.command("broadcast") & filters.private)
async def handle_broadcast_command(bot, message):
    if not ADMINS:
        return await message.reply_text("❌ **Broadcasting is disabled because no ADMIN is set.**")

    # Check if sender is admin
    user = message.from_user
    is_admin = False
    if isinstance(ADMINS, int) and user.id == ADMINS:
        is_admin = True
    elif isinstance(ADMINS, str) and user.username and user.username.lower() == ADMINS.lower():
        is_admin = True

    if not is_admin:
        return await message.reply_text("⛔ **Access Denied:** You are not authorized to use admin broadcast.")

    b_msg = message.reply_to_message
    if not b_msg:
        return await message.reply_text("📝 **Reply with /broadcast to the message you want to broadcast.**")

    sts = await message.reply_text("📢 **Broadcasting your message to all bot users...**")
    start_time = time.time()
    total_users = await db.total_users_count()
    users = await db.get_all_users()

    done = 0
    blocked = 0
    deleted = 0
    failed = 0
    success = 0

    async for u in users:
        if 'id' in u:
            pti, sh = await broadcast_messages(int(u['id']), b_msg)
            if pti:
                success += 1
            elif pti == False:
                if sh == "Blocked":
                    blocked += 1
                elif sh == "Deleted":
                    deleted += 1
                elif sh == "Error":
                    failed += 1
            done += 1
            if not done % 20:
                await sts.edit(
                    f"📢 **Broadcast in progress:**\n\n"
                    f"• Total Users: `{total_users}`\n"
                    f"• Processed: `{done} / {total_users}`\n"
                    f"• Success: `{success}`\n"
                    f"• Blocked: `{blocked}`\n"
                    f"• Deleted: `{deleted}`"
                )
        else:
            done += 1
            failed += 1

    time_taken = datetime.timedelta(seconds=int(time.time() - start_time))
    await sts.edit(
        f"✅ **Broadcast Completed!**\n"
        f"⏱️ Time taken: `{time_taken}`\n\n"
        f"• Total Users: `{total_users}`\n"
        f"• Success: `{success}`\n"
        f"• Blocked: `{blocked}`\n"
        f"• Deleted: `{deleted}`\n"
        f"• Failed: `{failed}`"
    )
