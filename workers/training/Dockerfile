FROM continuumio/miniconda3:latest

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Create conda environment with PyAV (CPU-only)
RUN conda create -n training python=3.10 -y && \
    conda install -n training -c conda-forge av -y

# Activate conda environment
SHELL ["conda", "run", "-n", "training", "/bin/bash", "-c"]

# Copy requirements and install Python packages
COPY requirements.txt .

# Install PyTorch CPU-only first
RUN pip install --no-cache-dir torch==2.1.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cpu

# Install other requirements
RUN pip install --no-cache-dir -r requirements.txt

# Install audiocraft without dependencies (PyAV already from conda)
RUN pip install --no-cache-dir --no-deps audiocraft

# Copy application code
COPY . .

# Expose port
EXPOSE 8003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8003/health').raise_for_status()"

# Run the application
CMD ["conda", "run", "--no-capture-output", "-n", "training", "python", "main.py"]
