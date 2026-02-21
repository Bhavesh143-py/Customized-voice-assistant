#!/bin/bash
# ============================================================
#  PVG Voice Assistant — Start Script
# ============================================================

set -e

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   PVG Voice Assistant — Starting...                  ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# Activate venv
source venv/bin/activate 2>/dev/null || true

# ── Start Ollama in background ───────────────────────────────
echo "▶ Starting Ollama server..."
ollama serve &>/tmp/ollama.log &
OLLAMA_PID=$!
sleep 2
echo "  Ollama running (PID $OLLAMA_PID)"

# ── Start Qdrant via Docker (if not already running) ─────────
if command -v docker &> /dev/null; then
  echo "▶ Ensuring Qdrant is running..."
  docker start pvg_qdrant 2>/dev/null || \
    docker run -d \
      --name pvg_qdrant \
      -p 6333:6333 \
      -v "$(pwd)/qdrant_data:/qdrant/storage" \
      qdrant/qdrant
  echo "  Qdrant running on http://localhost:6333"
fi

sleep 1

# ── Start FastAPI backend ────────────────────────────────────
echo ""
echo "▶ Starting FastAPI backend on http://localhost:8000..."
echo "▶ Open frontend/index.html in your browser"
echo ""
echo "  Press Ctrl+C to stop."
echo ""

cd backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1

# Cleanup on exit
trap "kill $OLLAMA_PID 2>/dev/null; echo 'Stopped.'" EXIT
