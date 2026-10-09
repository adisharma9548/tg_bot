"""
Real-time Progress Card Engine
Official Maintainer: @No_MOORESINPS
Official Bot: https://t.me/chessvideosbot (@chessvideosbot)
"""

import time
import math
import asyncio
from pyrogram.errors import FloodWait, MessageNotModified

# In-memory timestamp cache to avoid Telegram rate limits
PROGRESS_CACHE = {}


def humanbytes(size) -> str:
    """Formats bytes into human-readable unit string."""
    if not size:
        return "0 B"
    power = 1024
    n = 0
    units = {0: ' ', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size >= power and n < 4:
        size /= power
        n += 1
    return f"{size:.2f} {units.get(n, '')}B".replace("  ", " ")


def time_formatter(seconds: int) -> str:
    """Formats seconds into readable elapsed / ETA time."""
    seconds = max(0, int(seconds))
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days:
        return f"{days}d, {hours}h"
    if hours:
        return f"{hours}h, {minutes}m"
    if minutes:
        return f"{minutes}m, {seconds}s"
    return f"{seconds}s"


def format_elapsed(diff: float) -> str:
    """Formats elapsed duration with millisecond precision under 1 second."""
    if diff < 1.0:
        return f"{max(1, int(diff * 1000))}ms"
    return time_formatter(int(diff))


def format_progress_bar(percentage: float, total_blocks: int = 10) -> str:
    """Generates modern high-contrast progress blocks."""
    filled = min(total_blocks, max(0, math.floor(percentage / (100 / total_blocks))))
    unfilled = total_blocks - filled
    return "▰" * filled + "▱" * unfilled


def build_progress_card(ud_type: str, current: int, total: int, start_time: float) -> str:
    """
    Renders Telegram Blockquote Progress Card matching the official specification:
    📩 Downloading...
    > ✦ ▰▰▰▱▱▱▱▱▱▱ ✦
    >
    > » 🔋 Percentage • 30.5%
    > » 🚀 Speed • 21.23 MB/s
    > » 🚦 Size • 2.0 MB / 659.93 MB
    > » ⏰ ETA • 30s
    > » ⏳ Elapsed • 94ms
    """
    now = time.time()
    diff = max(0.001, now - start_time)
    percentage = (current * 100 / total) if total > 0 else 0
    speed = current / diff
    eta_seconds = round((total - current) / speed) if speed > 0 else 0

    bar = format_progress_bar(percentage, 10)
    eta = time_formatter(eta_seconds)
    elapsed = format_elapsed(diff)

    ud_lower = ud_type.lower()
    if "download" in ud_lower:
        header = "📩 **Downloading...**"
    elif "upload" in ud_lower:
        header = "📤 **Uploading...**"
    else:
        header = f"⚡ **{ud_type}...**"

    return (
        f"{header}\n"
        f"> ✦ {bar} ✦\n"
        f"> \n"
        f"> » 🔋 **Percentage** • {percentage:.1f}%\n"
        f"> » 🚀 **Speed** • {humanbytes(speed)}/s\n"
        f"> » 🚦 **Size** • {humanbytes(current)} / {humanbytes(total)}\n"
        f"> » ⏰ **ETA** • {eta}\n"
        f"> » ⏳ **Elapsed** • {elapsed}"
    )


async def progress_for_pyrogram(
    current,
    total,
    ud_type,
    message,
    start_time
):
    """
    Pyrogram progress callback that edits the target message with real-time UI.
    """
    now = time.time()
    msg_id = f"{message.chat.id}_{message.id}_{ud_type}"
    last_update = PROGRESS_CACHE.get(msg_id, 0)

    # Throttled edit every 2.8 seconds or when 100% complete
    if (now - last_update) >= 2.8 or current == total:
        PROGRESS_CACHE[msg_id] = now
        text = build_progress_card(ud_type, current, total, start_time)

        try:
            await message.edit_text(text=text)
        except FloodWait as e:
            await asyncio.sleep(e.value + 0.5)
        except MessageNotModified:
            pass
        except Exception:
            pass

        if current == total and msg_id in PROGRESS_CACHE:
            PROGRESS_CACHE.pop(msg_id, None)
