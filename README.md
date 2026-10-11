# 🚀 Telegram Save Restricted Content Bot

A clean, high-performance Telegram bot powered by **Pyrofork** and **MongoDB Atlas** (with local SQLite fallback), designed to download, organize, clean, and forward restricted media from Telegram channels, groups, forum topics, and external websites.

---

## 🌟 Key Features

1. **Restricted Media Transfer**: Downloads restricted videos, documents, audio, photos, and formatted text.
2. **Sequential Forum Topic Crawler (`/topic`)**: Transfers complete forum topics file-by-file in exact order with real-time progress cards.
3. **Interactive Client UI**: 2-column menu on `/start` and 1-tap toggles on `/settings` (Format, Sound, Destination, Thumbnail, Caption).
4. **Instant Task Cancellation**: One-tap `[🛑 Cancel Task]` button directly on the live progress card; immediately purges backend files.
5. **Single-Task DDoS Protection**: Enforces one active transfer per user with instant file cleanup.
6. **Automatic Filename Cleaner**: Strips channel ads, promo tags, usernames, and URLs from filenames automatically.
7. **External Downloader (yt-dlp)**: Downloads videos and audio from YouTube, Instagram Reels, X/Twitter, and direct URLs.
8. **Dual-Tier Cloud Ready**: Production-ready for AWS Elastic Beanstalk (Amazon Linux 2 / AL2023) and Docker.

---

## 📂 Project Structure

```text
theaditya/
├── plugins/
│   ├── start.py         # Main command & link transfer router
│   ├── generate.py      # Account login (/login, /logout)
│   ├── cleaner.py       # Filename ad/promo cleaner
│   ├── organizer.py     # Link parser & topic metadata extractor
│   ├── progress.py      # Blockquote progress bar with cancel button
│   ├── strings.py       # Help menus & UI text templates
│   ├── ytdl.py          # yt-dlp web downloader
│   └── broadcast.py     # Admin broadcast handler
├── database/
│   ├── db.py            # MongoDB Atlas & SQLite database manager
│   ├── thumbs/          # Custom user thumbnails
│   └── bot.db           # Local SQLite database fallback
├── app.py               # Flask HTTP health check service
├── application.py       # AWS Elastic Beanstalk WSGI supervisor
├── bot.py               # Pyrogram client entry point
├── config.py            # Environment configuration & validator
├── guard.py             # Maintainer integrity banner
├── runner.py            # Unified production supervisor (Flask + Bot)
├── create_aws_bundle.py # AWS Elastic Beanstalk Linux zip packager
├── Dockerfile           # Container build definition
├── Procfile             # Process manager for cloud platforms
├── requirements.txt     # Essential Python dependencies
├── .env.example         # Configuration template
└── README.md            # Setup and operational guide
```

---

## ⚙️ Quick Start

### 1. Installation

```bash
git clone https://github.com/adisharma9548/tg_bot.git
cd theaditya
pip install -r requirements.txt
```

### 2. Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

| Variable | Description |
| :--- | :--- |
| `API_ID` | Telegram API ID from https://my.telegram.org |
| `API_HASH` | Telegram API Hash from https://my.telegram.org |
| `BOT_TOKEN` | Bot Token from [@BotFather](https://t.me/BotFather) |
| `MONGODB_URI` | MongoDB Atlas URI (leave empty for local SQLite fallback) |
| `ADMINS` | Admin Telegram username or numerical ID |
| `WAITING_TIME` | Flood delay in seconds between transfers (default: `10`) |

### 3. Run the Bot

**Direct CLI Mode:**
```bash
python bot.py
```

**AWS / Cloud Mode (Flask Health Server + Bot):**
```bash
python runner.py
```

---

## ☁️ AWS Elastic Beanstalk Deployment

1. Package the Linux-compliant deployment bundle:
   ```bash
   python create_aws_bundle.py
   ```
   *Generates `tg_bot_aws.zip` using POSIX forward slashes.*

2. In the AWS Elastic Beanstalk Console, click **Upload and deploy** and choose `tg_bot_aws.zip`.
3. Set your environment variables under **Configuration** ➔ **Updates, monitoring, and logging** ➔ **Environment properties**.

---

## 📌 Bot Commands

- `/start` — Welcome menu with interactive navigation buttons
- `/settings` — Interactive settings dashboard (Video/Document, Silent, Destination)
- `/help` — Interactive documentation and link syntax guide
- `/status` — Storage and account status
- `/topic <link>` — Crawl and transfer an entire forum topic sequentially
- `/login` — Connect your Telegram user account for private channel access
- `/logout` — Disconnect your user account
- `/cancel` — Abort active transfer and purge backend files immediately
- `/clear` — Wipe conversation history from both sides
- `/reset` — Reset all custom preferences to defaults
- `/broadcast` — (Admin only) Broadcast message to all bot users
