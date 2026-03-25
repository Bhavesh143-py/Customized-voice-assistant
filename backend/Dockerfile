# ── PVG College Voice Assistant Backend ──────────────────────────────────────
# Multi-stage-friendly slim build for Windows/Linux/Mac Docker Desktop
FROM python:3.11-slim

WORKDIR /app

# ── System dependencies ────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    wget \
    curl \
    espeak-ng \
    libespeak-ng1 \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# ── Install Piper TTS binary (Linux x86_64) ───────────────────────────────────
# Piper binary handles TTS synthesis — the MODEL (.onnx) is mounted via volume
# so users place their models in ./tts_models/ without rebuilding the image
RUN wget -q "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz" \
    -O /tmp/piper.tar.gz \
    && tar -xzf /tmp/piper.tar.gz -C /tmp/ \
    && cp /tmp/piper/piper /usr/local/bin/piper \
    && chmod +x /usr/local/bin/piper \
    && rm -rf /tmp/piper.tar.gz /tmp/piper

# Verify piper binary
RUN piper --version 2>&1 || echo "Piper binary installed (model not yet present — mount via volume)"

# ── Python dependencies ────────────────────────────────────────────────────────
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────────────────────────────────────
COPY backend/ ./
COPY scripts/ingest.py ./scripts/ingest.py

# ── Runtime directories ────────────────────────────────────────────────────────
# tts_models: mounted from host via docker-compose volume (NOT bundled)
# data:       ingestion data files
RUN mkdir -p /app/data /app/tts_models /app/scripts

EXPOSE 8000

# Single worker for CPU-only inference — avoids model duplication in RAM
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
