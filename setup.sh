#!/bin/bash
# ── PVG Voice Assistant — Linux First Time Setup ──────────────────────────────

set -e  # stop on any error
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo "=================================================="
echo "  PVG Voice Assistant — First Time Setup (Linux)  "
echo "=================================================="

# ── Check Docker ───────────────────────────────────────────────────────────
echo -e "\n[1/5] Checking Docker..."
if ! command -v docker &>/dev/null; then
    echo -e "${RED}Docker not found! Install with:${NC}"
    echo "  curl -fsSL https://get.docker.com | sh"
    echo "  sudo usermod -aG docker \$USER"
    echo "  (then log out and log back in)"
    exit 1
fi
echo -e "${GREEN}Docker found.${NC}"

# ── Check data folder ──────────────────────────────────────────────────────
echo -e "\n[2/5] Checking data folder..."
if [ ! -d "data" ] || [ -z "$(ls data/*.txt 2>/dev/null)" ]; then
    echo -e "${RED}No .txt files found in data/ folder!${NC}"
    echo "Add your scraped college .txt files to data/ then run again."
    exit 1
fi
COUNT=$(ls data/*.txt | wc -l)
echo -e "${GREEN}Found $COUNT .txt files in data/.${NC}"

# ── Check TTS models ───────────────────────────────────────────────────────
echo -e "\n[3/5] Checking TTS model..."
mkdir -p tts_models
if [ ! -f "tts_models/en_US-amy-medium.onnx" ]; then
    echo "Downloading Amy voice model (~60MB)..."
    wget -q --show-progress \
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx" \
        -O tts_models/en_US-amy-medium.onnx
    wget -q \
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json" \
        -O tts_models/en_US-amy-medium.onnx.json
    echo -e "${GREEN}Amy voice model downloaded.${NC}"
else
    echo -e "${GREEN}Amy voice model already present.${NC}"
fi

# ── Build and start all services ───────────────────────────────────────────
echo -e "\n[4/5] Building and starting all services..."
echo "(First time may take 10-20 mins — downloading images and models)"
docker compose up -d --build

# ── Wait for services to be healthy ───────────────────────────────────────
echo -e "\n[5/5] Waiting for services to be ready..."
sleep 10

echo -e "\n${GREEN}=================================================="
echo "  Setup Complete!"
echo "  Open in browser: http://localhost:3000"
echo "  Backend API:     http://localhost:8000"
echo "  Qdrant dashboard: http://localhost:6333/dashboard"
echo -e "==================================================${NC}"
