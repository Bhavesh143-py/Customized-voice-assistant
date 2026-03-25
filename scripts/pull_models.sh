#!/bin/sh
# Pull Ollama models via REST API.
# Called by the model-puller container on first startup.
# Uses the REST API (not CLI) to avoid Ollama 0.18.x TUI issues in headless containers.
set -e

OLLAMA_BASE="http://pvg_ollama:11434"
LLM_MODEL="${OLLAMA_LLM_MODEL:-gemma2:2b}"
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"

pull_model() {
    MODEL="$1"
    echo ">>> Pulling model: $MODEL (may take several minutes on first run)"
    RESP=$(curl -sf --max-time 1800 \
        -X POST "${OLLAMA_BASE}/api/pull" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"${MODEL}\",\"stream\":false}")
    if echo "$RESP" | grep -q '"error"'; then
        echo "ERROR: Pull failed for $MODEL"
        echo "$RESP"
        exit 1
    fi
    echo "OK: $MODEL is ready"
}

apk add --no-cache curl
pull_model "$LLM_MODEL"
pull_model "$EMBED_MODEL"
echo "All models pulled successfully"
