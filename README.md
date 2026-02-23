# 🪟 Windows Quick Start

### 📦 Double-Click Setup (No Terminal Needed)

**SETUP.bat**
Run this **once** after cloning/downloading the project. It will automatically:

* Check if Docker is installed and running
* Download required AI models
* Build all containers
* Ingest initial data

👉 No terminal commands required.

---

**START.bat**
Use this for daily usage.

* Starts all services/containers
* Launches the application
* Automatically opens your browser

---

**STOP.bat**
Stops all running containers and services safely.

---

**REINGEST.bat**
Run this whenever new `.txt` files are added.

* Reloads documents
* Rebuilds embeddings/vector index
* Updates the assistant’s knowledge base

---

### 🧠 Typical Workflow

1. Run **SETUP.bat** → one time only
2. Use **START.bat** → every day
3. Add new data → run **REINGEST.bat**
4. Finish work → run **STOP.bat**

---

# 📐 System Architecture

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

# 📁 Project Structure

```
pvg_voice_assistant/
├── backend/
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   └── index.html
├── scripts/
│   └── ingest.py
├── data/                     ← PUT YOUR .txt FILES HERE
├── tts_models/               ← Piper model files (auto-downloaded)
├── qdrant_data/              ← Qdrant storage (auto-created)
├── setup.sh
├── run.sh
└── README.md
```

---

# 🚀 Quick Start (Linux / macOS)

### Step 1 — Place your data files

```
cp /path/to/your/scraped/*.txt data/
```

### Step 2 — Run setup (one time only)

```
chmod +x setup.sh run.sh
./setup.sh
```

This will:

* Create Python virtual environment
* Install Python packages
* Install Ollama and pull `qwen2.5:3b` and `nomic-embed-text`
* Install/start Qdrant via Docker
* Download Piper TTS voice model
* Ingest `.txt` files into Qdrant

### Step 3 — Start the server

```
./run.sh
```

### Step 4 — Open the frontend

Open `frontend/index.html` in your browser
(Chrome or Edge recommended)

---

# ⚙️ Manual Setup (If setup.sh Fails)

## 1. Python environment

```
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

## 2. Ollama models

```
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

## 3. Qdrant (Docker)

```
docker run -d --name pvg_qdrant -p 6333:6333 \
  -v $(pwd)/qdrant_data:/qdrant/storage qdrant/qdrant
```

## 4. Piper TTS

Download piper binary and model into `tts_models/`.

## 5. Ingest data

```
python3 scripts/ingest.py --data_dir ./data
```

## 6. Start backend

```
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

---

# 🔧 Configuration

Edit `backend/main.py` to change:

| Variable             | Default            | Description               |
| -------------------- | ------------------ | ------------------------- |
| `WHISPER_MODEL_SIZE` | "medium"           | STT model size            |
| `OLLAMA_LLM_MODEL`   | "qwen2.5:3b"       | LLM model                 |
| `OLLAMA_EMBED_MODEL` | "nomic-embed-text" | Embedding model           |
| `TOP_K`              | 5                  | Number of RAG chunks      |
| `MEMORY_TURNS`       | 4                  | Conversation memory turns |
| `PIPER_MODEL_PATH`   | ./tts_models/...   | Piper model path          |

---

# 🌐 Frontend Features

* Push-to-talk button
* Live waveform visualizer
* Transcript panel
* Conversation history
* Quick question pills
* Auto WebSocket reconnect
* Browser fallback TTS
* Spacebar toggle recording

---

# ❓ FAQ

**Bot gives wrong answers**
Re-run ingestion.

**No audio output**
Check Piper installation; browser fallback will activate if needed.

**WebSocket failed**
Ensure backend runs on port 8000.

**Out of memory**
Switch to smaller model: `qwen2.5:1.5b`.

---

# 📦 Tech Stack

| Component  | Technology              |
| ---------- | ----------------------- |
| Frontend   | Vanilla HTML/CSS/JS     |
| Backend    | FastAPI + Uvicorn       |
| STT        | Faster-Whisper (medium) |
| Embeddings | Nomic via Ollama        |
| Vector DB  | Qdrant                  |
| LLM        | Qwen2.5-3B via Ollama   |
| TTS        | Piper TTS               |
| Transport  | WebSocket               |

---

*Built for Pune Vidyarthi Griha's College of Engineering — Demo Project*
