import time
import math
import asyncio
from pyrogram.errors import FloodWait, MessageNotModified

# In-memory timestamp cache to avoid Telegram rate limits
PROGRESS_CACHE = {}

def humanbytes(size):
    if not size:
        return "0 B"
    power = 1024
    n = 0
    dic_power_n = {0: ' ', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size >= power and n < 4:
        size /= power
        n += 1
    return f"{size:.2f} {dic_power_n.get(n, '')}B"

def time_formatter(seconds: int) -> str:
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + "d, ") if days else "") + \
          ((str(hours) + "h, ") if hours else "") + \
          ((str(minutes) + "m, ") if minutes else "") + \
          ((str(seconds) + "s") if seconds else "")
    return tmp if tmp else "0s"

async def progress_for_pyrogram(
    current,
    total,
    ud_type,
    message,
    start_time
):
    now = time.time()
    diff = now - start_time
    if diff <= 0:
        diff = 0.001

    msg_id = f"{message.chat.id}_{message.id}_{ud_type}"
    last_update = PROGRESS_CACHE.get(msg_id, 0)

    # Update at most once every 3.5 seconds or when finished
    if (now - last_update) >= 3.5 or current == total:
        PROGRESS_CACHE[msg_id] = now
        percentage = (current * 100 / total) if total > 0 else 0
        speed = current / diff
        eta_seconds = round((total - current) / speed) if speed > 0 else 0
        eta = time_formatter(eta_seconds)

        filled = math.floor(percentage / 10)
        unfilled = max(0, 10 - filled)
        bar = "■" * filled + "□" * unfilled

        text = (
            f"**{ud_type}**\n"
            f"[{bar}] `{percentage:.1f}%`\n\n"
            f"📁 **Size:** `{humanbytes(current)}` / `{humanbytes(total)}`\n"
            f"🚀 **Speed:** `{humanbytes(speed)}/s`\n"
            f"⏱️ **ETA:** `{eta}`"
        )
        try:
            await message.edit_text(text=text)
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except MessageNotModified:
            pass
        except Exception:
            pass

        if current == total and msg_id in PROGRESS_CACHE:
            PROGRESS_CACHE.pop(msg_id, None)
