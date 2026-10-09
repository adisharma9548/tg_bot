# Dockerfile for AWS Elastic Beanstalk / ECS / Cloud Containers
# Proprietary build maintained by @No_MOORESINPS
# Official Telegram Bot: https://t.me/chessvideosbot (@chessvideosbot)

FROM python:3.10-slim

WORKDIR /app

# Set non-interactive debian frontend
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

# Install system dependencies: ffmpeg for media streaming/merging, gcc/dev for crypto builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    python3-dev \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies first for efficient layer caching
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy repository application source
COPY . .

# Ensure permissions and directories
RUN mkdir -p downloads database/thumbs && chmod -R 755 /app

# Expose AWS Elastic Beanstalk default health check port
EXPOSE 5000

# Launch unified AWS production supervisor (Web Health Server + Telegram Bot)
CMD ["python", "-u", "runner.py"]
