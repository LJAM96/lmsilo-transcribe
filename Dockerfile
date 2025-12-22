# Transcribe - Merged Docker Image
# Contains: Frontend (nginx) + Backend (uvicorn) + Worker (celery)
# Run mode determined by command override in docker-compose

# Stage 1: Build Frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ .
RUN npm run build

# Stage 2: Python Backend with CUDA support
FROM nvidia/cuda:12.1-cudnn8-runtime-ubuntu22.04

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3-pip \
    ffmpeg \
    rubberband-cli \
    git \
    curl \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.11 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

# Create app directory
WORKDIR /app

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip
RUN pip install --upgrade pip wheel setuptools

# Install PyTorch with CUDA support
RUN pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

# Copy requirements and install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ .

# Copy frontend build from builder stage
COPY --from=frontend-builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY frontend/nginx.conf /etc/nginx/sites-available/default

# Create supervisord config
RUN mkdir -p /etc/supervisor/conf.d /var/log/supervisor
COPY <<EOF /etc/supervisor/conf.d/supervisord.conf
[supervisord]
nodaemon=true
user=root
logfile=/var/log/supervisor/supervisord.log
pidfile=/var/run/supervisord.pid

[program:nginx]
command=/usr/sbin/nginx -g "daemon off;"
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/nginx.log
stderr_logfile=/var/log/supervisor/nginx_error.log

[program:uvicorn]
command=/opt/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
directory=/app
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/uvicorn.log
stderr_logfile=/var/log/supervisor/uvicorn_error.log
EOF

# Create directories for data
RUN mkdir -p /app/uploads /app/outputs /app/models /app/huggingface

# Expose ports
EXPOSE 80 8000

# Default command runs supervisord (both nginx + uvicorn)
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
