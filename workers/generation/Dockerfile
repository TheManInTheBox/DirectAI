# MusicGen Generation Worker - Using conda for PyAV binary
FROM continuumio/miniconda3:latest

# Set working directory
WORKDIR /app

# Set timezone non-interactively
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Install mamba (faster than conda) and create environment with PyAV + updated libstdc++
RUN conda install -n base -c conda-forge mamba -y && \
    mamba create -n musicgen python=3.10 -y && \
    mamba install -n musicgen -c conda-forge av ffmpeg libsndfile libstdcxx-ng pkg-config -y

# Activate environment for all subsequent RUN commands
SHELL ["conda", "run", "-n", "musicgen", "/bin/bash", "-c"]

# Upgrade pip in the conda environment
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install PyTorch (required by Bark)
RUN pip install --no-cache-dir torch==2.1.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cpu

# Install dependencies from requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Bark and its dependencies
# Transformers needs to be installed from git for Bark to work correctly
RUN pip install --no-cache-dir git+https://github.com/huggingface/transformers.git
RUN pip install --no-cache-dir git+https://github.com/suno-ai/bark.git

# Copy application code
COPY . .

# Expose FastAPI port
EXPOSE 8002

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV USE_GPU=false

# Health check (run inside conda environment)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD conda run -n musicgen python -c "import requests; requests.get('http://localhost:8002/health')"

# Run FastAPI with uvicorn (inside conda environment)
CMD ["conda", "run", "--no-capture-output", "-n", "musicgen", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "1"]


