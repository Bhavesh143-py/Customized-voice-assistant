# ── PVG Voice Assistant Backend ───────────────────────────────────────────────
# CUDA runtime is required when Faster-Whisper should run on GPU.
FROM nvidia/cuda:12.3.2-cudnn9-runtime-ubuntu22.04

WORKDIR /app

# ── System dependencies ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    ffmpeg \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1 \
    && python -m pip install --no-cache-dir --upgrade pip

# ── Install Piper TTS binary ──────────────────────────────────────────────────
RUN wget -q "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz" \
    -O /tmp/piper.tar.gz \
    && tar -xzf /tmp/piper.tar.gz -C /tmp/ \
    && cp /tmp/piper/piper /usr/local/bin/piper \
    && chmod +x /usr/local/bin/piper \
    && rm -rf /tmp/piper.tar.gz /tmp/piper

# ── Python dependencies ───────────────────────────────────────────────────────
# Build context is project root so paths start from there
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy application code ─────────────────────────────────────────────────────
COPY backend/main.py .
COPY scripts/ingest.py ./scripts/ingest.py

# ── Create necessary directories ──────────────────────────────────────────────
RUN mkdir -p /app/data /app/tts_models /app/scripts

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
