#!/usr/bin/env bash
# ===================================================================
# Telegram Bot Deployment & Setup Script for Ubuntu 22.04 / 24.04 EC2
# Official Maintainer: @No_MOORESINPS
# ===================================================================

set -e

echo "[*] Updating Ubuntu packages..."
sudo apt-get update -y && sudo apt-get upgrade -y
sudo apt-get install -y python3 python3-pip python3-venv ffmpeg git curl

# Configure 2GB swap space for t3.micro / t4g.nano memory protection
if [ ! -f /swapfile ]; then
    echo "[*] Configuring 2 GB swapfile for memory protection..."
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

# Ensure workspace directories
mkdir -p downloads database/thumbs
chmod 755 downloads database

# Python virtual environment setup
if [ ! -d "venv" ]; then
    echo "[*] Creating Python virtual environment..."
    python3 -m venv venv
fi

echo "[*] Installing Python dependencies..."
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

# Create .env if missing
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "[!] Created .env from .env.example. Please populate API_ID, API_HASH, and BOT_TOKEN."
fi

# Install and configure systemd service
if [ -f "tgbot.service" ]; then
    echo "[*] Installing systemd service..."
    sudo cp tgbot.service /etc/systemd/system/tgbot.service
    sudo systemctl daemon-reload
    sudo systemctl enable tgbot
    echo "[+] Systemd service enabled."
fi

echo "==================================================================="
echo " [SUCCESS] Telegram Bot environment is ready!"
echo " Start Bot:   sudo systemctl start tgbot"
echo " Stop Bot:    sudo systemctl stop tgbot"
echo " Live Logs:   sudo journalctl -u tgbot -f"
echo " Web Health:  curl http://127.0.0.1:5000/health"
echo "==================================================================="
