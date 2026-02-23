## 📐 System Architecture

```
Browser (Frontend)
  │
  │  [WebSocket ws://localhost:8000/ws/voice]
  │
  │  User presses mic → MediaRecorder captures audio
  │  → PCM bytes sent over WebSocket
  │
FastAPI Backend (backend/main.py)
  │
  ├─ 1. STT:        Faster-Whisper medium  →  transcript text
  ├─ 2. Embed:      Nomic via Ollama       →  query vector
  ├─ 3. Retrieve:   Qdrant vector DB       →  top-5 context chunks
  ├─ 4. LLM:        Qwen2.5-3B via Ollama →  answer text
  ├─ 5. Memory:     Last 4 turns kept      →  conversational context
  └─ 6. TTS:        Piper TTS              →  WAV audio bytes
  │
  └─ WAV bytes sent back over WebSocket → Browser plays audio
```

---

## 📁 Project Structure

```
pvg_voice_assistant/
├── backend/
│   ├── main.py               ← FastAPI server (main entry point)
│   └── requirements.txt      ← Python dependencies
├── frontend/
│   └── index.html            ← Demo website (open in browser)
├── scripts/
│   └── ingest.py             ← Data ingestion script
├── data/                     ← PUT YOUR .txt FILES HERE
├── tts_models/               ← Piper model files (auto-downloaded)
├── qdrant_data/              ← Qdrant storage (auto-created)
├── setup.sh                  ← One-time setup script
├── run.sh                    ← Start the server
└── README.md
```

---

## 🚀 Quick Start

### Step 1 — Place your data files
```bash
# Copy all your scraped college .txt files into the data/ folder
cp /path/to/your/scraped/*.txt data/
```

### Step 2 — Run setup (one time only)
```bash
chmod +x setup.sh run.sh
./setup.sh
```

This will:
- Create Python virtual environment
- Install all Python packages
- Install Ollama and pull `qwen2.5:3b` and `nomic-embed-text`
- Install/start Qdrant via Docker
- Download Piper TTS voice model
- Ingest your .txt files into Qdrant

### Step 3 — Start the server
```bash
./run.sh
```

### Step 4 — Open the frontend
```
Open frontend/index.html in your browser
(Chrome or Edge recommended for WebRTC/Audio APIs)
```

---

## ⚙️ Manual Setup (if setup.sh fails)

### 1. Python environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

### 2. Ollama models
```bash
# Install Ollama: https://ollama.com
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

### 3. Qdrant
```bash
# Via Docker (recommended):
docker run -d --name pvg_qdrant -p 6333:6333 \
  -v $(pwd)/qdrant_data:/qdrant/storage qdrant/qdrant

# Or install natively: https://qdrant.tech/documentation/quick-start/
```

### 4. Piper TTS
```bash
# Download piper binary: https://github.com/rhasspy/piper/releases
# Download voice model:
mkdir -p tts_models && cd tts_models
wget "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
wget "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
```

### 5. Ingest data
```bash
source venv/bin/activate
python3 scripts/ingest.py --data_dir ./data
```

### 6. Start backend
```bash
source venv/bin/activate
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## 🔧 Configuration

Edit `backend/main.py` to change:

| Variable | Default | Description |
|---|---|---|
| `WHISPER_MODEL_SIZE` | `"medium"` | STT model size (tiny/base/small/medium) |
| `OLLAMA_LLM_MODEL` | `"qwen2.5:3b"` | LLM model name in Ollama |
| `OLLAMA_EMBED_MODEL` | `"nomic-embed-text"` | Embedding model |
| `TOP_K` | `5` | Number of RAG chunks to retrieve |
| `MEMORY_TURNS` | `4` | Conversation turns to remember |
| `PIPER_MODEL_PATH` | `./tts_models/...` | Path to Piper ONNX model |

---

## 🌐 Frontend Features

- **Push-to-talk button** — Click once to start recording, click again to send
- **Live waveform visualizer** — Shows audio input in real time
- **Transcript panel** — Shows what you said + what the bot responded
- **Conversation history** — Scrollable chat window with all turns
- **Quick pills** — One-click questions for common queries
- **Auto-reconnect** — WebSocket reconnects if backend restarts
- **Fallback TTS** — Uses browser Web Speech API if Piper audio fails
- **Keyboard shortcut** — Press `Space` to toggle recording

---

## ❓ FAQ

**Q: The bot gives wrong answers**
A: Re-run ingestion: `python3 scripts/ingest.py --data_dir ./data`
   Check your .txt files have relevant content.

**Q: No audio output**
A: Check that `piper` binary is in PATH and model files are in `tts_models/`.
   Browser fallback TTS will activate automatically if Piper fails.

**Q: WebSocket connection failed**
A: Make sure backend is running on port 8000. Check CORS if serving frontend from a web server.

**Q: Out of memory errors**
A: Use a smaller LLM: change `OLLAMA_LLM_MODEL = "qwen2.5:1.5b"` in `main.py`.

---

## 📦 Tech Stack

| Component | Technology |
|---|---|
| Frontend | Vanilla HTML/CSS/JS (WebSocket + Web Audio API) |
| Backend | FastAPI + Uvicorn |
| STT | Faster-Whisper medium (CPU/int8) |
| Embeddings | Nomic-embed-text via Ollama |
| Vector DB | Qdrant (local) |
| LLM | Qwen2.5-3B via Ollama |
| TTS | Piper TTS (en_US-lessac-medium) |
| Transport | WebSocket (simpler than full WebRTC for LAN kiosk use) |

---

*Built for Pune Vidyarthi Griha's College of Engineering — Demo Project*
