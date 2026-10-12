# 🚀 Telegram Save Restricted Content Bot (AWS Edition)

A high-performance Telegram bot powered by **Pyrofork** and **Amazon Web Services (AWS)** (with local SQLite fallback), designed to download, organize, clean, and forward restricted media from Telegram channels, groups, forum topics, and external websites.

---

## 🌟 Key Features

1. **Restricted Media Transfer**: Downloads restricted videos, documents, audio, photos, and formatted text up to 2 GB (4 GB with Premium).
2. **Sequential Forum Topic Crawler (`/topic`)**: Transfers complete forum topics file-by-file in exact 1:1 original order, retaining verbatim filenames and captions.
3. **Interactive Client UI**: 2-column menu on `/start` and 1-tap toggles on `/settings` (Format, Sound, Destination, Thumbnail, Caption).
4. **Pre-Download Disk Protection**: Validates available EBS/ephemeral drive space before downloading to prevent server disk exhaustion.
5. **Instant Task Cancellation**: One-tap `[🛑 Cancel Task]` button directly on the live progress card; immediately purges backend files.
6. **Single-Task DDoS Protection**: Enforces one active transfer per user with instant file cleanup.
7. **External Downloader (yt-dlp)**: Downloads videos and audio from YouTube (with quality selection 1080p-360p & MP3), Instagram Reels, X/Twitter, and direct URLs.
8. **Pure AWS Cloud Persistence**: Uses Amazon DynamoDB for cloud persistence with automatic table provisioning and seamless local SQLite WAL fallback.

---

## 📂 Project Structure

```text
theaditya/
├── plugins/
│   ├── start.py         # Main command, link transfer & disk validation
│   ├── generate.py      # Account login (/login, /logout)
│   ├── cleaner.py       # Filename ad/promo cleaner
│   ├── organizer.py     # Link parser & topic metadata extractor
│   ├── progress.py      # Blockquote progress bar with cancel button
│   ├── strings.py       # Help menus & UI text templates
│   ├── ytdl.py          # yt-dlp web downloader with multi-client bot bypass
│   └── broadcast.py     # Admin broadcast handler
├── database/
│   ├── db.py            # Amazon DynamoDB & SQLite database manager
│   ├── thumbs/          # Custom user thumbnails
│   └── bot.db           # Local SQLite database fallback (WAL mode)
├── app.py               # Flask HTTP health check service (DynamoDB probe)
├── application.py       # AWS Elastic Beanstalk WSGI supervisor
├── bot.py               # Pyrogram client entry point
├── config.py            # Environment configuration & AWS parameter validator
├── guard.py             # Maintainer integrity banner
├── runner.py            # Unified production supervisor (Flask + Bot)
├── create_aws_bundle.py # AWS Elastic Beanstalk Linux zip packager
├── Dockerfile           # Container build definition
├── Procfile             # Process manager for cloud platforms
├── requirements.txt     # Essential Python dependencies (boto3, pyrofork)
├── .env.example         # AWS & Telegram configuration template
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
| `AWS_DEFAULT_REGION` | AWS Region (e.g. `ap-south-1`) |
| `DYNAMODB_TABLE_NAME`| DynamoDB Table Name (default: `tg_users`) |
| `AWS_ACCESS_KEY_ID` | Optional AWS Access Key (or use IAM Role on EC2) |
| `AWS_SECRET_ACCESS_KEY` | Optional AWS Secret Key (or use IAM Role on EC2) |
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

## ☁️ AWS Elastic Beanstalk / EC2 Deployment

1. Package the Linux-compliant deployment bundle:
   ```bash
   python create_aws_bundle.py
   ```
   *Generates `tg_bot_aws.zip` using POSIX forward slashes.*

2. In the AWS Management Console:
   - Deploy `tg_bot_aws.zip` to AWS Elastic Beanstalk (Python 3.11 / AL2023 platform) or run on an EC2 `t4g.nano` / `t3.micro` instance.
   - Attach the IAM role or configure environment variables in Configuration > Software.
