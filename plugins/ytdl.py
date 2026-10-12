"""
Enhanced YouTube & Web Media Downloader Engine
Supports alternative player clients (Android/iOS) to bypass datacenter IP bot detection,
cookie authentication, video resolution selection (1080p, 720p, 480p, 360p), and MP3 audio extraction.
Maintainer: @No_MOORESINPS
Official Bot: @chessvideosbot (https://t.me/chessvideosbot)
"""

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


def get_cookie_file() -> str | None:
    """Locates or generates a Netscape cookies.txt file for authenticated extraction."""
    # 1. Environment variable support for cloud containers (Render, AWS, Docker)
    cookies_env = os.environ.get("YOUTUBE_COOKIES", "").strip()
    target_path = "database/cookies.txt"
    if cookies_env:
        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(cookies_env)
            return target_path
        except Exception:
            pass

    # 2. Local files
    for p in ["cookies.txt", "database/cookies.txt"]:
        if os.path.exists(p) and os.path.getsize(p) > 0:
            return p
    return None


def get_ydl_base_opts() -> dict:
    """Returns baseline yt-dlp options with multi-client bot bypass and cookies."""
    opts = {
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web']
            }
        },
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'nocheckcertificate': True,
    }
    cookie_path = get_cookie_file()
    if cookie_path:
        opts['cookiefile'] = cookie_path
    return opts


def _sync_probe_web_media(url: str) -> dict:
    """Extracts media metadata, available heights, and thumbnails without downloading."""
    opts = get_ydl_base_opts()
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if not info:
            raise Exception("Unable to fetch media info from URL")

        title = info.get("title", "Media")
        duration = info.get("duration", 0)
        thumbnail = info.get("thumbnail")

        formats = info.get("formats", [])
        # Filter available heights for standard options
        available_heights = []
        for f in formats:
            h = f.get("height")
            if h and isinstance(h, int) and h in [360, 480, 720, 1080, 1440, 2160]:
                if h not in available_heights:
                    available_heights.append(h)
        available_heights.sort(reverse=True)

        return {
            "title": title,
            "duration": duration,
            "thumbnail": thumbnail,
            "heights": available_heights,
            "extractor": info.get("extractor", "generic"),
        }


async def probe_web_media(url: str) -> dict:
    """Asynchronously probe URL media info."""
    return await asyncio.to_thread(_sync_probe_web_media, url)


def _sync_ytdl_download(url: str, output_dir: str, format_type: str = "mp4", quality: str = "best"):
    """Downloads media file with selected format and quality."""
    os.makedirs(output_dir, exist_ok=True)
    ydl_opts = get_ydl_base_opts()
    ydl_opts['outtmpl'] = os.path.join(output_dir, '%(title).100s.%(ext)s')

    if format_type.lower() == "mp3":
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        # Video MP4 download
        if quality and quality != "best" and quality.isdigit():
            h = quality
            ydl_opts['format'] = (
                f'bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/'
                f'bestvideo[height<={h}]+bestaudio/'
                f'best[height<={h}]/best'
            )
        else:
            ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        ydl_opts['merge_output_format'] = 'mp4'

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if not info:
            raise Exception("Could not download media from URL")

        filename = ydl.prepare_filename(info)

        # Detect final postprocessed / merged file extension
        target_exts = [".mp3"] if format_type.lower() == "mp3" else [".mp4", ".mkv", ".webm"]
        if not os.path.exists(filename):
            base = os.path.splitext(filename)[0]
            for ext in target_exts + [".mp4", ".mkv", ".webm", ".mp3", ".m4a"]:
                if os.path.exists(f"{base}{ext}"):
                    filename = f"{base}{ext}"
                    break

        return filename, info.get('title', 'Media'), info.get('duration', 0)


async def download_web_media(url: str, output_dir: str, format_type: str = "mp4", quality: str = "best"):
    """Asynchronously download media using yt-dlp."""
    return await asyncio.to_thread(_sync_ytdl_download, url, output_dir, format_type, quality)
