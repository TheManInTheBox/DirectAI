# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for audio processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    libsndfile1-dev \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Install build dependencies first (required by madmom and other C extensions)
RUN pip install --no-cache-dir Cython>=0.29.0 numpy==1.24.3

# Copy requirements and install remaining Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Audio Flamingo models (use a specific branch for stability)
# Note: Using the audio_flamingo_2 branch which has the best balance of features and stability
RUN pip install --no-cache-dir git+https://github.com/NVIDIA/audio-flamingo.git@audio_flamingo_2

# Copy application code
COPY . .

# Expose FastAPI port
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEMUCS_MODEL=htdemucs
ENV WORKERS=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')"

# Run FastAPI with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
