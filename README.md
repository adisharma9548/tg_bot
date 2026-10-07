<p align="center">
  <img src="logo.jpg" alt="My Aditya Logo" width="220" style="border-radius: 24px; box-shadow: 0 4px 20px rgba(255, 140, 0, 0.4);">
</p>

# 🚀 My Aditya — Save Restricted Content Bot

A high-performance Telegram bot powered by **Pyrofork** and **SQLite**, designed to save, forward, clean, and manage restricted media and files from Telegram channels, groups, and external websites.

---

## 👑 Bot Administration
* **Admin**: `@No_MOORESINPS`
* **Storage Engine**: Local SQLite Database (`database/bot.db`) stored directly on host device (Zero cloud DB setup required).

---

## 🌟 Key Features

### 1. 🗂️ Universal File Type Support
Download and forward **any** content shared in Telegram channels or chats:
* **Documents & Archives**: `.pdf`, `.zip`, `.rar`, `.apk`, `.epub`, `.iso`, `.exe`, `.tar.gz`, etc.
* **Videos**: `.mp4`, `.mkv`, `.webm`, `.avi`, `.mov`
* **Audio & Music**: `.mp3`, `.m4a`, `.flac`, `.wav`, `.aac`
* **Media**: Photos, Voice Notes, Animations (GIFs), Stickers, and Text.

### 2. 🧹 Automatic Filename Cleaner & Ad Remover (Always ON)
Cleans all downloaded files automatically before re-uploading:
* Strips annoying promo tags like:
  * `cracked by...`
  * `extracted by...`
  * `downloaded from...`
  * `uploaded by...`
  * `shared by...`
  * `provided by...`
* Strips `@channel_usernames` and website URLs (`https://...`, `t.me/...`, `www...`).
* Normalizes repeated separators (`___`, `---`, `...`).
* Optional custom prefix support (`/set_prefix [Course]`).
* Optional custom word removal rules (`/replace <word>`).

### 3. 🔄 Batch Auto-Resume (`/resume`)
* Never lose progress on large multi-file batches (e.g., 50–100 posts).
* Each completed post ID is continuously saved in `database/bot.db`.
* If a download is interrupted by internet drop or system restart, send `/resume` to immediately pick up from the last finished file.

### 4. 🌐 External Web Downloader (`yt-dlp`)
* Paste any web URL into the chat to download and upload directly:
  * **YouTube** Videos and Shorts
  * **Instagram** Reels and Posts
  * **Twitter / X** Videos
  * Direct web media links

### 5. ⚡ Live In-Memory Progress Bar
* Real-time progress bar with percentage, speed (`MB/s`), downloaded size, and ETA.
* Strictly in-memory to prevent disk I/O load.
* Throttled updates to prevent Telegram API `FloodWait` limits.

### 6. 🎨 Custom Thumbnail & Caption System
* **`/set_thumb`**: Reply to any image to set it as the custom thumbnail for all videos and documents.
* **`/set_caption`**: Custom caption templates with dynamic tags:
  * `{filename}` — Cleaned filename
  * `{size}` — Human-readable size
  * `{caption}` — Original post caption

### 7. ⚙️ User Preference Controls & Chat Management
* **`/clear`**: One-click two-sided chat cleanup — deletes all messages in the conversation from both sides (bot & user), leaving the chat clean.
* **`/reset`**: Reset all user settings (thumbnails, captions, prefix, upload mode) to defaults.
* **`/mode`**: Toggle between **Video Mode** (streamable inline) and **Document Mode** (100% original uncompressed quality).
* **`/silent`**: Toggle silent upload delivery (`disable_notification=True`).
* **`/to_saved`**: Route downloads directly to your personal **Saved Messages** cloud storage.
* **`/status`**: Dashboard displaying account status, active toggles, and host PC disk space.

### 8. 📚 Universal Course Organizer & Forum Topic Crawler (`/topic`)
* **Forum Topic Support**: Supports 3-part Telegram forum links: `https://t.me/c/<chat_id>/<topic_id>/<message_id>`.
* **Topic Crawler (`/topic <link>`)**: Automatically discovers all media inside a forum topic thread, sorts them chronologically by lecture and part, and transfers them with 0 missing files.
* **Universal Naming**: Dynamically extracts master sequence numbers (`✦ 300 ✦`, `#300`), subject titles across any course, and parts (`Part 1`, `Part 2`):
  * `[300] EM - Lecture 6 (Vector Calculus) - Part 1.mp4`
  * `[300] EM - Lecture 6 (Vector Calculus) - Part 2.mp4`
  * `[301] EM - Lecture 7.mp4`
* **Audit Summary Report**: Generates a sequential verification checklist upon transfer completion.

---

## 📋 Full Command Reference

| Command | Description |
| :--- | :--- |
| `/start` | Check bot status and welcome message |
| `/help` | Display interactive help menu |
| `/login` | Connect your Telegram user account session |
| `/logout` | Disconnect and clear user session |
| `/cancel` | Stop any active batch download |
| `/clear` | Clear chat history from both sides in one click |
| `/reset` | Reset all custom settings, captions & thumbnails |
| `/resume` | Resume an interrupted batch download |
| `/topic <link>` | Crawl and transfer an entire forum topic in sequence with audit report |
| `/status` | View host disk space, account status & active settings |
| `/mode` | Toggle upload format: Video vs. Document |
| `/silent` | Toggle silent notifications ON/OFF |
| `/to_saved` | Toggle delivery between Saved Messages and Bot Chat |
| `/set_prefix <text>` | Add custom prefix to all filenames |
| `/del_prefix` | Remove custom prefix |
| `/replace <words>` | Add custom words to strip from filenames |
| `/del_replace` | Clear custom removal words |
| `/set_thumb` | Reply to an image to set custom thumbnail |
| `/see_thumb` | View current custom thumbnail |
| `/del_thumb` | Revert to original thumbnail |
| `/set_caption <text>` | Set custom caption template |
| `/see_caption` | View current custom caption |
| `/del_caption` | Revert to original post caption |
| `/broadcast` | *(Admin Only - @No_MOORESINPS)* Broadcast a message to all users |

---

## 🛠️ Installation & Running Locally

### 1. Requirements
* Python 3.9 – 3.14
* Git

### 2. Setup
```powershell
cd c:\Users\adish\Desktop\bot\theaditya
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Configuration (`.env`)
Fill in your credentials in [.env](file:///c:/Users/adish/Desktop/bot/theaditya/.env):
```env
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
ADMINS=No_MOORESINPS
LOGIN_SYSTEM=True
WAITING_TIME=10
ERROR_MESSAGE=True
```

### 4. Start the Bot
```powershell
python bot.py
```

---

## 🔒 Security & Privacy
* All user sessions and configurations are kept strictly on your local PC in `database/bot.db`.
* Downloaded files are placed in an isolated `downloads/` directory and **automatically deleted immediately after upload**.
* `.env`, `.db`, `.session`, and `downloads/` are strictly ignored by `.gitignore`.
