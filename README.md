<p align="center">
  <img src="logo.jpg" alt="Bot Logo" width="220" style="border-radius: 24px; box-shadow: 0 4px 20px rgba(255, 140, 0, 0.4);">
</p>

# 🚀 Telegram Save Restricted Content Bot

A high-performance Telegram bot powered by **Pyrofork** and **MongoDB Atlas**, designed to download, organize, clean, and forward restricted media and files from Telegram channels, groups, forum topics, and external websites.

---

## 📑 Table of Contents
1. [Features](#features)
2. [Architecture](#architecture)
3. [Requirements](#requirements)
4. [MongoDB Atlas Setup](#mongodb-atlas-setup)
5. [Telegram API Setup](#telegram-api-setup)
6. [Environment Variables](#environment-variables)
7. [Local Development](#local-development)
8. [Database Migration (SQLite → MongoDB)](#database-migration)
9. [Running the Bot](#running-the-bot)
10. [Production Deployment](#deployment)
11. [Health Check Endpoint](#health-check-endpoint)
12. [Troubleshooting](#troubleshooting)
13. [Security](#security)
14. [Backup & Recovery](#backup-and-recovery)

---

## 🌟 Features

### 1. 🗂️ Universal Media & Content Handling
* **Documents & Archives**: `.pdf`, `.zip`, `.rar`, `.apk`, `.epub`, `.iso`, `.exe`, `.tar.gz`, etc.
* **Streamable Videos**: `.mp4`, `.mkv`, `.webm`, `.avi`, `.mov`.
* **Audio & Voice**: `.mp3`, `.m4a`, `.flac`, `.wav`, voice notes.
* **Full Text & Formatting**: Pure text messages with emojis, bold, italics, links, and code blocks preserved (`entities`).
* **Animations & Stickers**: Animated GIFs and Telegram stickers.

### 2. ⚡ Pipelined Lookahead Pre-fetching Engine
* **Concurrent Transfer**: Downloads File $N+1$ in the background while uploading File $N$ to Telegram.
* **Strict Sequential Delivery (FIFO)**: Delivers all files in exact chronological sequence (`[300] Part 1 ➡️ [300] Part 2 ➡️ [301]`).
* **Zero Disk Bloat**: Limits pre-fetched files to 1 in local storage; deletes files immediately after upload.
* **Live Queue Dashboard**: Real-time status display showing currently uploading file, pre-fetched queue status, speed, ETA, and progress bar.

### 3. 🧹 Automatic Filename Cleaning & Ad Removal
* Strips annoying promo text (`cracked by`, `downloaded from`, `shared by`, etc.).
* Strips `@channel_usernames` and URLs (`https://...`, `t.me/...`, `www...`).
* Normalizes repeated separators (`___`, `---`, `...`).
* Custom prefix support (`/set_prefix [Course]`).
* Custom word removal rules (`/replace <word>`).

### 4. 📚 Universal Course Organizer & Forum Topic Crawler (`/topic`)
* Supports 3-part Telegram forum topic links (`https://t.me/c/<chat_id>/<topic_id>/<msg_id>`).
* Discovers and crawls all messages inside topic discussion threads.
* Preserves lecture sequence numbers (`[300]`, `#300`) and multi-part files (`Part 1`, `Part 2`).
* Generates a comprehensive verification and audit checklist report upon completion.

### 5. 🔄 Resumable Batches (`/resume`)
* Every processed post ID is recorded atomically in MongoDB Atlas.
* Interrupted multi-file batches can be resumed anytime with `/resume`.

### 6. 🌐 External Web Downloader (`yt-dlp`)
* Downloads videos from YouTube, Instagram Reels, X/Twitter, and direct web links.

### 7. 🎨 Custom Thumbnail, Caption & Mode Toggles
* **`/set_thumb`**: Custom thumbnail for all uploaded documents and videos.
* **`/set_caption`**: Dynamic caption templates (`{filename}`, `{size}`, `{caption}`).
* **`/mode`**: Toggle between Video Mode (streamable) and Document Mode (uncompressed).
* **`/silent`**: Toggle silent upload notifications.
* **`/to_saved`**: Forward directly to personal Saved Messages.
* **`/clear`**: One-click two-sided chat history purge.
* **`/reset`**: Factory reset all user settings.

---

## 🏗️ Architecture

```text
┌───────────────────────┐         ┌─────────────────────────┐
│ Telegram Clients      │         │ External Web (yt-dlp)   │
└───────────┬───────────┘         └────────────┬────────────┘
            │                                  │
            ▼                                  ▼
┌───────────────────────────────────────────────────────────┐
│                 Pyrofork Core Engine                      │
│   • Bot Client: Event handling & upload dispatcher        │
│   • User Client (acc): Restricted content download engine │
└───────────────┬──────────────────────────────┬────────────┘
                │                              │
                ▼                              ▼
┌───────────────────────────────┐  ┌─────────────────────────┐
│ Pipelined Lookahead Queue     │  │ MongoDB Atlas Cluster   │
│ • Bounded producer-consumer   │  │ • tg_users (sessions)   │
│ • Live queue progress manager │  │ • tg_batch_tasks        │
│ • Ephemeral temp file cleanup │  │ • Persistent settings   │
└───────────────────────────────┘  └─────────────────────────┘
```

---

## 📦 Requirements

* **Python**: 3.10+ (Recommended: 3.10 or 3.11)
* **MongoDB**: MongoDB Atlas Cluster 6.0+ (or local MongoDB with Replica Set/Standalone)
* **Telegram**: Telegram API ID & API Hash (from [my.telegram.org](https://my.telegram.org))
* **Bot Token**: From [@BotFather](https://t.me/BotFather)
* **FFmpeg**: Required for media stream analysis and thumbnail generation

---

## 🍃 MongoDB Atlas Setup

1. **Create an Account**: Go to [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) and register or sign in.
2. **Build a Cluster**: Select the free **M0 Sandbox** cluster (AWS/GCP/Azure) and choose the region closest to your deployment server.
3. **Database Access (User)**:
   * Navigate to **Security** ➡️ **Database Access** ➡️ **Add New Database User**.
   * Select **Password Authentication**.
   * Set a username (e.g., `sih26044`) and a secure password.
   * Assign the role **Read and write to any database** (or specific database privileges).
4. **Network Access (IP Whitelist)**:
   * Navigate to **Security** ➡️ **Network Access** ➡️ **Add IP Address**.
   * Choose **Allow Access from Anywhere** (`0.0.0.0/0`) for dynamic cloud container deployments (Koyeb, Render, Railway, Heroku).
5. **Get Connection String**:
   * Click **Database** ➡️ **Connect** ➡️ **Drivers** (Python).
   * Copy the connection string format:
     ```text
     mongodb+srv://USERNAME:PASSWORD@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority
     ```
   * *Special Characters Note*: If your password contains characters like `@`, `:`, `/`, or `%`, URL-encode them (e.g. `@` ➡️ `%40`).

---

## 📱 Telegram API Setup

1. Log in to [my.telegram.org](https://my.telegram.org) using your Telegram phone number.
2. Go to **API development tools**.
3. Create a new application to obtain your:
   * `API_ID` (integer)
   * `API_HASH` (32-character string)
4. Message [@BotFather](https://t.me/BotFather) on Telegram and send `/newbot` to generate your `BOT_TOKEN`.

---

## 🔐 Environment Variables

Create a `.env` file in the project root based on `.env.example`:

| Variable | Required | Description | Example |
| :--- | :---: | :--- | :--- |
| `API_ID` | **Yes** | Telegram API ID | `10907272` |
| `API_HASH` | **Yes** | Telegram API Hash | `cd96b7ebc0df678e076...` |
| `BOT_TOKEN` | **Yes** | Telegram Bot Token from @BotFather | `8841562162:AAE-...` |
| `MONGODB_URI` | **Yes** | MongoDB Atlas connection string | `mongodb+srv://user:pass@cluster.mongodb.net/` |
| `DB_NAME` | No | MongoDB Database Name (Default: `sih26044`) | `sih26044` |
| `ADMINS` | No | Admin Telegram user ID or username | `No_MOORESINPS` |
| `LOGIN_SYSTEM` | No | Enables `/login` in-bot session generator | `True` |
| `STRING_SESSION` | Conditional | Pyrogram session string (only if `LOGIN_SYSTEM=False`) | `BQC...` |
| `CHANNEL_ID` | No | Channel ID to route all downloads to | `-1001234567890` |
| `WAITING_TIME` | No | Anti-flood delay in seconds between uploads | `10` |
| `ERROR_MESSAGE` | No | Send error messages in chat | `True` |
| `PORT` | No | Web port for Flask health check endpoint | `8080` |

---

## 💻 Local Development

### 1. Clone & Set Up Virtual Environment
```bash
git clone https://github.com/adisharma9548/tg_bot.git
cd tg_bot

python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env with your credentials
```

---

## 🔄 Database Migration (SQLite → MongoDB)

If you have existing user preferences, sessions, or batch tasks in `database/bot.db`:

```bash
python migrate_sqlite_to_mongodb.py
```

* **Safe & Idempotent**: Uses atomic upserts (`$set`) to prevent duplicate records.
* **Preserves Data**: Does not delete `database/bot.db`.
* **Indexes**: Automatically generates unique and sparse indexes on the target collections.

---

## ▶️ Running the Bot

### Start the Bot Process:
```bash
python -u bot.py
```

### Run with Background Web Health Server:
```bash
gunicorn --bind 0.0.0.0:8080 app:app & python3 bot.py
```

---

## 🚢 Production Deployment

### Recommended Low-Cost / Free Deployment Options:
1. **Render.com / Railway.app / Koyeb**:
   * Deploy as a **Docker Container** or **Web Service**.
   * Connect your GitHub repository.
   * Add Environment Variables in the platform dashboard (`API_ID`, `API_HASH`, `BOT_TOKEN`, `MONGODB_URI`, `DB_NAME`).
   * The container automatically boots `gunicorn app:app` for health checks and `python3 bot.py` for Telegram handling.
2. **Oracle Cloud Free Tier (Always-Free Compute)**:
   * Create an Ubuntu VM (Ampere 4-Core or AMD).
   * Unmetered bandwidth, 1Gbps fiber connection directly to Telegram DC.
   * Run using `docker compose` or `systemd`.

### Docker Deployment:
```bash
docker build -t telegram-bot .
docker run -d --name tg_bot --env-file .env -p 8080:8080 telegram-bot
```

---

## 🩺 Health Check Endpoint

When running `app.py` or deploying via Docker, the web server exposes a health monitoring endpoint:

* **Endpoint**: `GET /health` or `GET /`
* **Response**:
```json
{
  "bot": "running",
  "database": "connected",
  "status": "ok"
}
```
* Status Code: `200 OK` (when database is connected) or `503 Service Unavailable` (if MongoDB is unreachable).

---

## 🔧 Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| `Discarding packet: The msg_id belongs to over 30 seconds in the future` | Host system clock is desynchronized from Telegram server time. | Resync Windows/Linux NTP clock (`w32tm /resync` or `timedatectl`). |
| `ServerSelectionTimeoutError: No replica set members found` | MongoDB Atlas network whitelist is blocking connection. | Add `0.0.0.0/0` in MongoDB Atlas Network Access. |
| `ChatForwardsRestricted` | Target group/channel has protected content enabled. | The bot uses authorized user string sessions (`acc`) to stream raw byte chunks. Make sure your account has joined the channel. |
| `FloodWait: Waiting X seconds` | Telegram API rate limit reached. | The bot automatically pauses for the required duration and resumes seamlessly. |

---

## 🛡️ Security

* **No Hardcoded Secrets**: Secrets are read exclusively from environment variables.
* **Safe Logging**: The MongoDB URI is automatically sanitized in logs (`mongodb+srv://user:****@...`).
* **Stateless Containers**: String sessions are saved in MongoDB Atlas; user clients connect using `in_memory=True` with no sensitive local session files stored on disk.
* **Git Safety**: `.gitignore` strictly excludes `.env`, `*.session`, and `*.db`.

---

## 💾 Backup and Recovery

1. **MongoDB Atlas Automated Backups**:
   * MongoDB Atlas provides continuous automated snapshots in the cluster management tab.
2. **Manual Dump (mongodump)**:
   ```bash
   mongodump --uri="<MONGODB_URI>" --db=sih26044 --out=./backup
   ```
3. **Manual Restore (mongorestore)**:
   ```bash
   mongorestore --uri="<MONGODB_URI>" --db=sih26044 ./backup/sih26044
   ```
