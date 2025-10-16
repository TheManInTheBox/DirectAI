# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for audio processing
# PyAV (av) requires FFmpeg development headers and pkg-config
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    libsndfile1-dev \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libavfilter-dev \
    libswscale-dev \
    libswresample-dev \
    pkg-config \
    gcc \
    g++ \
    make \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set PKG_CONFIG_PATH to ensure PyAV can find FFmpeg libraries
ENV PKG_CONFIG_PATH=/usr/lib/x86_64-linux-gnu/pkgconfig

# Upgrade pip to latest version
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install build dependencies first (ensures compatibility with C extensions)
RUN pip install --no-cache-dir Cython>=0.29.0 numpy==1.24.3

# Install a specific PyAV version with pre-built wheels (10.x series is more stable)
# This avoids compilation issues with newer FFmpeg in Debian Trixie
RUN pip install --no-cache-dir av==10.0.0 || pip install --no-cache-dir av==9.2.0 || echo "PyAV pre-install skipped"

# Copy requirements and install remaining Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose FastAPI port
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV USE_GPU=false

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')"

# Run FastAPI with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
