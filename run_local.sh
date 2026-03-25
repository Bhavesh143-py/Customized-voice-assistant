#!/bin/bash
# ── PVG College Voice Assistant — Local Runner ────────────────────────────────
# Starts Ollama, Qdrant, ingester, backend and frontend in one script.
# Usage: bash run_local.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$PROJECT_DIR/venv"

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[PVG]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
die()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ── Cleanup on exit ───────────────────────────────────────────────────────────
cleanup() {
    log "Shutting down..."
    kill $FRONTEND_PID 2>/dev/null
    docker stop pvg_qdrant 2>/dev/null
    log "Done."
}
trap cleanup EXIT INT TERM

# ── Check venv ────────────────────────────────────────────────────────────────
if [ ! -d "$VENV" ]; then
    log "Creating virtual environment..."
    python3 -m venv "$VENV"
    source "$VENV/bin/activate"
    log "Installing requirements..."
    pip install -q --upgrade pip
    pip install -q -r "$PROJECT_DIR/backend/requirements.txt"
else
    source "$VENV/bin/activate"
fi

# ── Step 1: Ollama ────────────────────────────────────────────────────────────
log "Checking Ollama..."
if ! command -v ollama &>/dev/null; then
    die "Ollama not found. Install from https://ollama.com"
fi

if ! pgrep -x "ollama" > /dev/null; then
    log "Starting Ollama..."
    ollama serve > /tmp/ollama.log 2>&1 &
    sleep 3
else
    log "Ollama already running."
fi

# ── Step 2: Qdrant ────────────────────────────────────────────────────────────
log "Starting Qdrant..."
docker run -d --rm \
    --name pvg_qdrant \
    -p 6333:6333 \
    qdrant/qdrant > /dev/null 2>&1 || log "Qdrant already running."

sleep 2

# ── Step 3: Ingest data ───────────────────────────────────────────────────────
log "Running ingester..."
OLLAMA_HOST=localhost OLLAMA_PORT=11434 \
QDRANT_HOST=localhost QDRANT_PORT=6333 \
python3 "$PROJECT_DIR/scripts/ingest.py" --data_dir "$PROJECT_DIR/data"
log "Ingestion complete."

# ── Step 4: Serve frontend ────────────────────────────────────────────────────
log "Starting frontend on http://localhost:3000 ..."
cd "$PROJECT_DIR/frontend"
python3 -m http.server 3000 > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!

# ── Step 5: Start backend ─────────────────────────────────────────────────────
log "Starting backend on http://localhost:8000 ..."
log ">>> Open your browser at: http://localhost:3000 <<<"
log "Press Ctrl+C to stop everything."
echo ""

cd "$PROJECT_DIR/backend"
OLLAMA_HOST=localhost \
OLLAMA_PORT=11434 \
QDRANT_HOST=localhost \
QDRANT_PORT=6333 \
OLLAMA_LLM_MODEL=gemma2:2b \
OLLAMA_EMBED_MODEL=nomic-embed-text \
WHISPER_MODEL_SIZE=medium.en \
PIPER_MODEL_PATH="$PROJECT_DIR/tts_models/en_US-amy-medium.onnx" \
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
