import os
import asyncio
import yt_dlp

def is_web_url(text: str) -> bool:
    """Returns True if text is an external web URL and not a Telegram link."""
    if not text:
        return False
    text = text.strip()
    if (text.startswith("http://") or text.startswith("https://")) and not ("t.me/" in text or "telegram.me/" in text):
        return True
    return False

def _sync_ytdl_download(url: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    ydl_opts = {
        'outtmpl': os.path.join(output_dir, '%(title).100s.%(ext)s'),
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if not info:
            raise Exception("Could not extract media info from URL")
        filename = ydl.prepare_filename(info)
        
        # If merged to mp4 or mkv
        if not os.path.exists(filename):
            base = os.path.splitext(filename)[0]
            for ext in [".mp4", ".mkv", ".webm", ".mp3", ".m4a"]:
                if os.path.exists(f"{base}{ext}"):
                    filename = f"{base}{ext}"
                    break

        return filename, info.get('title', 'Media'), info.get('duration', 0)

async def download_web_media(url: str, output_dir: str):
    return await asyncio.to_thread(_sync_ytdl_download, url, output_dir)
