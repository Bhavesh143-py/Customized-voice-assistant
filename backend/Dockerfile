# ── PVG Voice Assistant Backend ───────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# ── System dependencies ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

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
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── Copy application code ─────────────────────────────────────────────────────
COPY backend/main.py .
COPY scripts/ingest.py ./scripts/ingest.py

# ── Create necessary directories ──────────────────────────────────────────────
RUN mkdir -p /app/data /app/tts_models /app/scripts

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
