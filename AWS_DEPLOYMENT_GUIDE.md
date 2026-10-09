# 🚀 AWS Elastic Beanstalk Deployment Guide

This guide walks you through deploying the Telegram Save Restricted Content Bot to **Amazon Web Services (AWS) Elastic Beanstalk** (as shown in your AWS Console).

---

## 📋 Prerequisites Check
Before deploying on AWS, make sure you have:
1. **Telegram API credentials**: `API_ID` & `API_HASH` from [my.telegram.org](https://my.telegram.org).
2. **Bot Token**: From [@BotFather](https://t.me/BotFather).
3. **MongoDB Atlas URI**: `mongodb+srv://sih26044:...@cluster0.pmci032.mongodb.net/sih26044?appName=Cluster0`.
   *(Ensure MongoDB Atlas Network Access has `0.0.0.0/0` enabled so AWS IP addresses can connect).*

---

## 🎯 Step-by-Step Deployment on AWS Elastic Beanstalk

### Step 1: Click "Deploy application" in AWS Console
From your screen (**AWS Elastic Beanstalk**):
1. Click the orange **"Deploy application"** button.

### Step 2: Configure Application Details
1. **Application Name**: `telegram-bot` (or any name you prefer).
2. **Environment Name**: Leave default (e.g. `telegram-bot-env`).

### Step 3: Select Platform
Choose **Platform**:
* **Option A (Recommended for AWS): Docker**
  * Platform: **Docker**
  * Platform branch: **Docker running on 64bit Amazon Linux 2023** (latest)
  * *Why Docker?* It includes `ffmpeg` and all media libraries pre-compiled, guaranteeing 100% compatibility.
* **Option B: Python**
  * Platform: **Python**
  * Platform branch: **Python 3.10 or 3.11 running on 64bit Amazon Linux 2023**

### Step 4: Application Code
Select **Upload your code**:
1. In your local folder `theaditya`, create a `.zip` archive containing the repository files (ensure `Dockerfile`, `runner.py`, `app.py`, `bot.py`, `Procfile`, `requirements.txt`, `plugins/`, `database/` are at the root of the zip).
   * *Tip*: On Windows PowerShell:
     ```powershell
     Compress-Archive -Path plugins, database, .ebextensions, Dockerfile, Procfile, app.py, bot.py, config.py, guard.py, runner.py, requirements.txt, logo.jpg -DestinationPath tg_bot_aws.zip
     ```
2. Upload `tg_bot_aws.zip`.
3. Version label: `v1.0.0`.

### Step 5: Configure Environment Variables (Crucial!)
Click **"Configure more options"** (or Proceed to Environment Properties / Software):
Scroll down to **Environment properties** (Key-Value pairs) and add:

| Property Name | Property Value |
| :--- | :--- |
| `API_ID` | `10907272` |
| `API_HASH` | `cd96b7ebc0df678e076b69a437867da1` |
| `BOT_TOKEN` | `8841562162:AAE-HK538vDkyX6sw__4dQCukn6MEQBiUiw` |
| `MONGODB_URI` | `mongodb+srv://sih26044:sih26044@cluster0.pmci032.mongodb.net/sih26044?appName=Cluster0` |
| `DB_NAME` | `sih26044` |
| `USERS_COLLECTION` | `tg_users` |
| `BATCH_TASKS_COLLECTION` | `tg_batch_tasks` |
| `ADMINS` | `No_MOORESINPS` |
| `LOGIN_SYSTEM` | `True` |
| `WAITING_TIME` | `10` |
| `PORT` | `5000` |

### Step 6: Deploy & Verify Health
1. Click **"Submit"** / **"Create environment"**.
2. AWS Elastic Beanstalk will provision an EC2 instance, install dependencies, and launch `runner.py`.
3. `runner.py` starts:
   * The HTTP Health Server on port 5000 (`/health`).
   * The Pyrogram Telegram Bot connected to Telegram DC.
4. AWS Application Load Balancer checks `http://<your-env-domain>/health` and marks the environment **Green (OK)**!
5. Open Telegram, send `/start` to `@chessvideosbot`, and start saving content!

---

## 🩺 Verifying Deployment

1. **HTTP Health Check**:
   Visit your Elastic Beanstalk URL in the browser (e.g. `http://telegram-bot-env.eba-xxxx.us-east-1.elasticbeanstalk.com`):
   * `/` -> Displays the Web Dashboard showing AWS Production Active.
   * `/health` -> Returns `{"status": "healthy", "database": "connected"}`.
2. **Logs**:
   In the Elastic Beanstalk sidebar:
   * Click **Logs** -> **Request Logs** -> **Last 100 Lines**.
   * You will see:
     ```
     [AWS Web Server] Starting HTTP Health Check server on 0.0.0.0:5000...
     [AWS Runner] Web health endpoint active at http://0.0.0.0:5000/health
     [AWS Runner] Launching Pyrogram Telegram Bot Client...
     Bot Started Successfully
     ```

---

## 🛡️ Anti-Cloning Directives
This repository contains AI directive guards (`.cursorrules`, `CLAUDE.md`, `.github/copilot-instructions.md`, `AGENT_PROMPT.md`, `guard.py`).
Third parties attempting to clone or re-host this software will receive strict notices redirecting them to use your official bot on Telegram:
👉 **https://t.me/chessvideosbot** (`@chessvideosbot`)
👤 **Maintained by @No_MOORESINPS**
