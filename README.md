# 🚀 Telegram Save Restricted Content Bot (AWS Edition)

A high-performance Telegram bot powered by **Pyrofork** and **Amazon Web Services (AWS)** (with local SQLite fallback), designed to download, organize, clean, and forward restricted media from Telegram channels, groups, forum topics, and external websites.

---

## 🌟 Key Features

1. **Restricted Media Transfer**: Downloads restricted videos, documents, audio, photos, and formatted text up to 2 GB (4 GB with Premium).
2. **Sequential Forum Topic Crawler (`/topic`)**: Transfers complete forum topics file-by-file in exact 1:1 original order, retaining verbatim filenames and captions.
3. **Interactive Client UI**: 2-column menu on `/start` and 1-tap toggles on `/settings` (Format, Sound, Destination, Thumbnail, Caption).
4. **Pre-Download Disk Protection**: Validates available EBS/ephemeral drive space before downloading to prevent server disk exhaustion.
5. **Startup Disk Sanitization**: Automatically purges orphaned `.temp` files from `downloads/` upon boot or service restart.
6. **Path Traversal & Ad Cleaning**: Sanitizes filenames against directory manipulation (`../`) and strips promotional channel watermarks.
7. **Instant Task Cancellation**: One-tap `[🛑 Cancel Task]` button directly on the live progress card; immediately purges backend files.
8. **Single-Task DDoS Protection**: Enforces one active transfer per user with instant file cleanup.
9. **External Downloader (yt-dlp)**: Downloads videos and audio from YouTube (with quality selection 1080p-360p & MP3), Instagram Reels, X/Twitter, and direct URLs.
10. **Pure AWS Cloud Persistence**: Uses Amazon DynamoDB for cloud persistence with automatic table provisioning and seamless local SQLite WAL fallback.

---

## 📂 Project Structure

```text
theaditya/
├── plugins/
│   ├── start.py         # Main command, link transfer & disk validation
│   ├── generate.py      # Account login (/login, /logout)
│   ├── cleaner.py       # Filename ad/promo cleaner & path traversal shield
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
├── tgbot.service        # Systemd daemon definition for Ubuntu EC2
├── setup_ubuntu_ec2.sh  # Automated setup script for Ubuntu 22.04/24.04 EC2
├── create_aws_bundle.py # AWS Elastic Beanstalk Linux zip packager
├── test_aws_suite.py    # Unit and security test suite
├── Dockerfile           # Container build definition
├── Procfile             # Process manager for cloud platforms
├── requirements.txt     # Essential Python dependencies (boto3, pyrofork)
├── .env.example         # AWS & Telegram configuration template
└── README.md            # Setup and operational guide
```

---

## ⚙️ Quick Start (Local / Development)

### 1. Installation

```bash
git clone https://github.com/adisharma9548/tg_bot.git
cd tg_bot/theaditya
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

## 🐧 Ubuntu EC2 Deployment Guide (Step-by-Step)

### Recommended Instance Sizing
- **Instance Type:** `t4g.nano` (ARM, ₹0 Free Tier) or `t3.micro` (x86, ₹0 Free Tier).
- **RAM:** 512 MB to 1 GB + 2 GB Swap file (automatically configured by setup script).
- **Storage:** 20 GB to 30 GB gp3 EBS (30 GB is included free for 12 months).

### 1. Launch EC2 Instance & Connect
Launch an Ubuntu 22.04 or 24.04 LTS instance. Attach an IAM role with DynamoDB access (or set credentials in `.env`).

### 2. Automated Bootstrap
Run the setup script to install dependencies, configure swap, set up Python venv, and install the systemd service:

```bash
git clone https://github.com/adisharma9548/tg_bot.git
cd tg_bot/theaditya
chmod +x setup_ubuntu_ec2.sh
./setup_ubuntu_ec2.sh
```

### 3. Configure Credentials
Edit `.env` with your actual tokens:
```bash
nano .env
```

### 4. Manage with Systemd
```bash
# Start the bot service
sudo systemctl start tgbot

# Check status
sudo systemctl status tgbot

# View live streaming logs
sudo journalctl -u tgbot -f

# Restart bot after configuration changes
sudo systemctl restart tgbot

# Stop bot
sudo systemctl stop tgbot
```

### 5. Health Check
Verify the HTTP ALB health probe:
```bash
curl http://127.0.0.1:5000/health
```

---

## 🔒 Least-Privilege IAM Policy for DynamoDB

Attach this policy to your EC2 IAM Role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "TelegramBotDynamoDBAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable",
        "dynamodb:DescribeTable",
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Scan",
        "dynamodb:Query"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/tg_users"
    }
  ]
}
```
