# PVGCOET Voice Assistant — v2.0

AI-powered voice assistant for Pune Vidyarthi Griha's College of Engineering with a full admin dashboard, REST API, event/notification management, and true bidirectional streaming.

---

## Features

- **Voice Assistant** — Speak to ask anything about the college; get spoken responses
- **Admin Dashboard** — Secure web UI to manage events and notifications
- **Live Data Integration** — Voice assistant fetches events/notifications from the database in real time
- **Streaming Pipeline** — LLM tokens stream as they're generated; TTS plays sentence-by-sentence
- **Configurable TTS** — Amy medium voice (Piper, offline) or Google TTS (Indian accent, online)
- **RAG** — Knowledge base stored in Qdrant, retrieved by semantic similarity
- **JWT Auth** — Secure admin login with token-based sessions

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| Database | SQLite (dev) / PostgreSQL (prod) via SQLAlchemy |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| STT | Faster-Whisper (small.en) |
| LLM | Ollama (Qwen2.5, Gemma2, or any model) |
| Embeddings | Nomic Embed Text via Ollama |
| Vector DB | Qdrant |
| TTS | Piper (Amy medium, offline) + gTTS fallback |
| Frontend | Vanilla HTML/CSS/JS (no build step) |
| Container | Docker + Docker Compose |

---

## Architecture

```
Browser
  │
  ├── index.html (Voice Assistant)
  │     └── WebSocket /ws/voice → Backend
  │           ├── Faster-Whisper (STT)
  │           ├── Qdrant (RAG context)
  │           ├── SQLite/PostgreSQL (live events + notifications)
  │           ├── Ollama (LLM streaming)
  │           └── Piper TTS (audio streaming)
  │
  └── admin.html (Admin Dashboard)
        └── REST API /api/* → Backend
              ├── POST/GET/PUT/DELETE /api/events
              ├── POST/GET/PUT/DELETE /api/notifications
              └── POST /api/auth/login
```

---

## Quick Start — Docker (Recommended, Windows-Friendly)

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac/Linux)
- At least 8GB RAM recommended

### 1. Clone / Extract the project

```bash
cd pvg_project
```

### 2. Copy environment file

```bash
cp .env.example .env
```

Edit `.env` — at minimum change `JWT_SECRET_KEY` for production.

### 3. Place TTS Model Files

> The Amy medium voice is **not bundled** to keep the project size manageable.

Download from [Piper Releases](https://github.com/rhasspy/piper/releases):

```
en_US-amy-medium.onnx
en_US-amy-medium.onnx.json
```

Place **both files** in `./tts_models/`:

```
pvg_project/
└── tts_models/
    ├── en_US-amy-medium.onnx        ← required
    └── en_US-amy-medium.onnx.json   ← required
```

If you don't have the model, set `TTS_ENGINE=gtts` in `.env` to use Google TTS (requires internet, Indian English accent).

### 4. Add your college knowledge base

Place `.txt` files in `./data/` — they will be ingested into Qdrant automatically.

### 5. Start everything

```bash
docker-compose up --build
```

First startup takes a few minutes (pulls models, builds images). Wait for:
```
pvg_backend | INFO: Application startup complete.
```

### 6. Access the apps

| Service | URL |
|---|---|
| Voice Assistant | http://localhost:3000 |
| Admin Dashboard | http://localhost:3000/admin.html |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |

### Default Admin Login
- **Username:** `admin`
- **Password:** `PvgAdmin@2024!`

> Change the password after first login via environment variables or the API.

---

## Local Setup (venv, no Docker)

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com) running locally
- [Qdrant](https://qdrant.tech/documentation/quick-start/) running locally

### Linux / macOS

```bash
# 1. Setup
bash setup.sh

# 2. Pull Ollama models
ollama pull qwen2.5:1.5b
ollama pull nomic-embed-text

# 3. Start Qdrant (separate terminal)
docker run -p 6333:6333 qdrant/qdrant

# 4. Ingest knowledge base
source venv/bin/activate
python scripts/ingest.py --data_dir ./data

# 5. Run backend
bash run.sh

# 6. Open frontend
# Open frontend/index.html in browser
# Or: python -m http.server 3000 --directory frontend
```

### Windows

```batch
# 1. Setup
Windows_Scripts\SETUP.bat

# 2. Pull Ollama models
ollama pull qwen2.5:1.5b
ollama pull nomic-embed-text

# 3. Start Qdrant (separate terminal)
docker run -p 6333:6333 qdrant/qdrant

# 4. Ingest knowledge base
venv\Scripts\activate
python scripts\ingest.py --data_dir data

# 5. Start backend
Windows_Scripts\START.bat
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_LLM_MODEL` | `qwen2.5:1.5b` | LLM model name (any Ollama model) |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `WHISPER_MODEL_SIZE` | `small.en` | STT model: `tiny.en`, `small.en`, `medium.en` |
| `TTS_ENGINE` | `piper` | `piper` (offline) or `gtts` (Google, needs internet) |
| `PIPER_MODEL_PATH` | `./tts_models/en_US-amy-medium.onnx` | Path to Piper .onnx model |
| `DATABASE_URL` | `sqlite:///./pvg_college.db` | SQLAlchemy DB URL |
| `JWT_SECRET_KEY` | *(change this!)* | Secret for signing JWT tokens |
| `JWT_EXPIRE_MINUTES` | `480` | Token validity (8 hours) |
| `DEFAULT_ADMIN_USERNAME` | `admin` | Initial admin username |
| `DEFAULT_ADMIN_PASSWORD` | `PvgAdmin@2024!` | Initial admin password |

---

## TTS Models — Detailed Guide

### Voice Used: Amy Medium (en_US-amy-medium)

The system uses the **Piper TTS** engine with Amy medium voice by default.

### How to get the model

```bash
mkdir -p tts_models
cd tts_models

# Download Amy medium voice
wget https://github.com/rhasspy/piper/releases/download/2023.11.14-2/en_US-amy-medium.onnx.tar.gz
tar -xzf en_US-amy-medium.onnx.tar.gz

# You should now have:
# tts_models/en_US-amy-medium.onnx
# tts_models/en_US-amy-medium.onnx.json
```

### How to switch voices

1. Download any Piper voice from https://github.com/rhasspy/piper/releases
2. Place the `.onnx` and `.onnx.json` files in `./tts_models/`
3. Update `.env`:
   ```
   PIPER_MODEL_PATH=./tts_models/en_US-lessac-medium.onnx
   ```
4. Restart the backend

### Fallback behavior

If the Piper model is missing:
- The backend logs a warning (does not crash)
- Falls back to `gTTS` (Google TTS, Indian English accent) if `GTTS_AVAILABLE`
- Falls back to browser `SpeechSynthesis` API if both fail
- Voice output is gracefully disabled — the text response still displays

---

## API Documentation

### Authentication

```http
POST /api/auth/login
Content-Type: application/json

{"username": "admin", "password": "PvgAdmin@2024!"}
```

Response: `{"access_token": "...", "token_type": "bearer", "username": "admin"}`

Use the token in subsequent requests:
```
Authorization: Bearer <access_token>
```

### Events

```http
GET    /api/events               # All events (public)
GET    /api/events/upcoming      # Upcoming events (public)
GET    /api/events/{id}          # Single event (public)
POST   /api/events               # Create event (admin)
PUT    /api/events/{id}          # Update event (admin)
DELETE /api/events/{id}          # Delete event (admin)
```

**Create event example:**
```json
POST /api/events
{
  "title": "Annual Tech Fest",
  "description": "College-wide technology festival",
  "date": "2025-03-15",
  "time": "09:00",
  "location": "Main Auditorium"
}
```

### Notifications

```http
GET    /api/notifications         # All notifications (public)
GET    /api/notifications/recent  # Recent 5 (public)
GET    /api/notifications/{id}    # Single notification (public)
POST   /api/notifications         # Create (admin)
PUT    /api/notifications/{id}    # Update (admin)
DELETE /api/notifications/{id}    # Delete (admin)
```

**Create notification example:**
```json
POST /api/notifications
{
  "title": "Exam Schedule Released",
  "message": "The end-semester exam schedule for all branches has been published on the college notice board."
}
```

---

## Admin Dashboard Usage

1. Open http://localhost:3000/admin.html
2. Log in with username `admin` and the password from your `.env`
3. **Dashboard** — overview of all events and notifications
4. **Events** — click "+ Add Event" to create; click "✏ Edit" or "✕ Delete" per row
5. **Notifications** — same for announcements

---

## Voice Assistant Usage

1. Open http://localhost:3000
2. Click the microphone button (or press **Space**)
3. Speak your question
4. Click again to stop recording and send

### Example questions
- "What are the upcoming events?"
- "Are there any recent announcements?"
- "What are the admission requirements?"
- "How do I contact the college?"

### Text mode
Click any quick question pill or type in the text box to ask without speaking.

---

## LLM Configuration

### Using Gemma (as specified)

```bash
# Pull Gemma via Ollama
ollama pull gemma2:2b

# Set in .env
OLLAMA_LLM_MODEL=gemma2:2b
```

### Other supported models

| Model | Speed | Quality | RAM |
|---|---|---|---|
| `qwen2.5:1.5b` | Fast | Good | 2GB |
| `gemma2:2b` | Medium | Better | 3GB |
| `llama3.2:3b` | Medium | Better | 4GB |
| `qwen2.5:7b` | Slow | Best | 8GB |

---

## Troubleshooting

### Windows — Docker not starting

```
Error: "WSL 2 installation is incomplete"
```
→ Install WSL2: `wsl --install` in PowerShell as Administrator, then restart.

### Port already in use

```
Error: bind: address already in use (port 8000)
```
→ Find and stop the process: `netstat -ano | findstr :8000` (Windows) or `lsof -i :8000` (Linux/Mac)

### TTS model not loading

```
WARNING: Piper model not found at ./tts_models/en_US-amy-medium.onnx
```
→ Download both `.onnx` AND `.onnx.json` files and place in `./tts_models/`
→ Or set `TTS_ENGINE=gtts` in `.env` for internet-based TTS

### Ollama model not pulling

```
Error pulling model: connection refused
```
→ Ensure Ollama is running: `ollama serve`
→ In Docker: wait for the `model-puller` container to complete

### First query is slow

Normal — Ollama lazy-loads models on first use. The backend warms up models on startup, but Docker startup sequencing can cause a delay. The second query will be fast.

### SQLite database locked

```
sqlite3.OperationalError: database is locked
```
→ Only one backend instance should run. Set `--workers 1` in uvicorn (already configured).

### CORS errors in browser

→ The backend allows all origins by default. If you change this, add your frontend URL to `allow_origins` in `main.py`.

---

## Production Checklist

- [ ] Change `JWT_SECRET_KEY` in `.env`
- [ ] Change `DEFAULT_ADMIN_PASSWORD`
- [ ] Change `ADMIN_REGISTRATION_SECRET`
- [ ] Switch `DATABASE_URL` to PostgreSQL
- [ ] Set `WHISPER_MODEL_SIZE=medium.en` for better accuracy
- [ ] Enable HTTPS (reverse proxy: Nginx/Caddy)
- [ ] Restrict CORS origins in `main.py`
- [ ] Set up log rotation

---

## Directory Structure

```
pvg_project/
├── backend/
│   ├── auth/           JWT authentication
│   ├── models/         SQLAlchemy DB models
│   ├── routes/         FastAPI route handlers
│   ├── schemas/        Pydantic validation schemas
│   ├── services/       Business logic (CRUD)
│   ├── main.py         App entry point + voice pipeline
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html      Voice assistant UI
│   └── admin.html      Admin dashboard
├── scripts/
│   └── ingest.py       Knowledge base ingestion
├── tts_models/         ← Place .onnx + .json files here (not bundled)
├── data/               ← Place .txt knowledge base files here
├── docker/
│   └── nginx.conf      Nginx reverse proxy config
├── Windows_Scripts/
│   ├── SETUP.bat
│   └── START.bat
├── docker-compose.yml
├── setup.sh
├── run.sh
└── .env.example
```
