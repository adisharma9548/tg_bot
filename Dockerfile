FROM python:3.10-slim

WORKDIR /app

# Install system dependencies including ffmpeg for media processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose default port
EXPOSE 8080

# Start health web server and telegram bot process
CMD gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 2 app:app & python3 bot.py
