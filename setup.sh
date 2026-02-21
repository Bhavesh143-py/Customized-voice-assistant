#!/bin/bash
# ============================================================
#  PVG Voice Assistant — Setup Script
#  Run this once to install all dependencies
# ============================================================

set -e

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   PVG College Voice Assistant — Setup                ║"
echo "║   Pune Vidyarthi Griha's College of Engineering      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── 1. Check Python ─────────────────────────────────────────
echo "▶ Checking Python version..."
python3 --version || { echo "ERROR: Python 3 not found. Install Python 3.10+"; exit 1; }

# ── 2. Create virtual environment ───────────────────────────
echo "▶ Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# ── 3. Install Python dependencies ──────────────────────────
echo "▶ Installing Python packages..."
pip install --upgrade pip -q
pip install -r backend/requirements.txt

# ── 4. Check Ollama ─────────────────────────────────────────
echo "▶ Checking Ollama..."
if ! command -v ollama &> /dev/null; then
  echo "  Ollama not found. Installing..."
  curl -fsSL https://ollama.com/install.sh | sh
else
  echo "  Ollama found."
fi

# ── 5. Pull Ollama models ────────────────────────────────────
echo "▶ Pulling Qwen2.5:3b LLM model (this may take a while)..."
ollama pull qwen2.5:3b

echo "▶ Pulling nomic-embed-text embedding model..."
ollama pull nomic-embed-text

# ── 6. Check / Start Qdrant ─────────────────────────────────
echo "▶ Checking Qdrant..."
if ! command -v docker &> /dev/null; then
  echo ""
  echo "  ⚠  Docker not found. You can either:"
  echo "     a) Install Docker and run Qdrant via Docker (recommended)"
  echo "        docker pull qdrant/qdrant"
  echo "        docker run -p 6333:6333 -v \$(pwd)/qdrant_data:/qdrant/storage qdrant/qdrant"
  echo ""
  echo "     b) Install Qdrant natively: https://qdrant.tech/documentation/quick-start/"
  echo ""
else
  echo "  Docker found. Starting Qdrant container..."
  docker run -d \
    --name pvg_qdrant \
    -p 6333:6333 \
    -v "$(pwd)/qdrant_data:/qdrant/storage" \
    qdrant/qdrant \
    || echo "  (Qdrant may already be running)"
fi

# ── 7. Check / Install Piper TTS ────────────────────────────
echo "▶ Setting up Piper TTS..."
if ! command -v piper &> /dev/null; then
  echo "  Piper not found. Downloading..."
  mkdir -p tts_models
  
  # Detect architecture
  ARCH=$(uname -m)
  if [ "$ARCH" = "x86_64" ]; then
    PIPER_URL="https://github.com/rhasspy/piper/releases/latest/download/piper_linux_x86_64.tar.gz"
  elif [ "$ARCH" = "aarch64" ]; then
    PIPER_URL="https://github.com/rhasspy/piper/releases/latest/download/piper_linux_aarch64.tar.gz"
  else
    echo "  ⚠  Unknown architecture: $ARCH. Download Piper manually from https://github.com/rhasspy/piper/releases"
    PIPER_URL=""
  fi

  if [ -n "$PIPER_URL" ]; then
    wget -q "$PIPER_URL" -O /tmp/piper.tar.gz
    tar -xzf /tmp/piper.tar.gz -C /usr/local/bin/ --strip-components=1
    echo "  Piper installed."
  fi
fi

# Download TTS voice model
echo "▶ Downloading Piper voice model (en_US-lessac-medium)..."
mkdir -p tts_models
cd tts_models
if [ ! -f "en_US-lessac-medium.onnx" ]; then
  wget -q "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx" \
       -O en_US-lessac-medium.onnx
  wget -q "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json" \
       -O en_US-lessac-medium.onnx.json
  echo "  Voice model downloaded."
else
  echo "  Voice model already present."
fi
cd ..

# ── 8. Ingest data ───────────────────────────────────────────
echo ""
echo "▶ Running data ingestion (your .txt files in /data)..."
if ls data/*.txt 1> /dev/null 2>&1; then
  python3 scripts/ingest.py --data_dir ./data
else
  echo "  ⚠  No .txt files found in ./data/"
  echo "     Place your scraped college website .txt files in the ./data/ folder"
  echo "     Then run:  python3 scripts/ingest.py --data_dir ./data"
fi

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ✅ Setup complete!                                   ║"
echo "║                                                      ║"
echo "║  To start:  ./run.sh                                 ║"
echo "║  Frontend:  Open frontend/index.html in browser      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
