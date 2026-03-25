"""
PVG College Voice Assistant — FastAPI Backend (Extended)
========================================================
TRUE BIDIRECTIONAL STREAMING WebSocket for voice:
  Browser → Server : raw PCM audio bytes
  Server → Browser : status JSONs + LLM tokens + TTS audio chunks

NEW in this version:
  - Admin dashboard REST APIs (events, notifications, auth)
  - Voice assistant fetches live events/notifications from DB
  - Configurable TTS: Piper (local/external path) + gTTS fallback
  - TTS model path via PIPER_MODEL_PATH env var (NOT bundled)
  - Graceful degradation if TTS model is missing
  - Gemma/Qwen2.5 LLM configurable via OLLAMA_LLM_MODEL env var
"""

import asyncio
import io
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import uuid
import wave
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List

import numpy as np
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from faster_whisper import WhisperModel
from qdrant_client import QdrantClient
import ollama

# ── Add parent to sys.path so relative imports work ───────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

try:
    import noisereduce as nr
    NOISEREDUCE_AVAILABLE = True
except ImportError:
    NOISEREDUCE_AVAILABLE = False

# ── gTTS ──────────────────────────────────────────────────────────────────────
try:
    from gtts import gTTS as _gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

# ── DB imports ─────────────────────────────────────────────────────────────────
from models.database import create_tables, get_db, AdminUser
from auth.jwt_auth import hash_password
from routes.events import router as events_router
from routes.notifications import router as notifs_router
from routes.auth import router as auth_router
from services.events_service import get_upcoming_events, format_events_for_voice
from services.notifications_service import get_recent_notifications, format_notifications_for_voice
from models.database import SessionLocal


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# ── CONFIG ─────────────────────────────────────────────────────────────────────
WHISPER_MODEL_SIZE  = os.getenv("WHISPER_MODEL_SIZE",  "medium.en")
WHISPER_DEVICE      = "cpu"
WHISPER_COMPUTE     = "int8"
OLLAMA_LLM_MODEL    = os.getenv("OLLAMA_LLM_MODEL",    "gemma2:2b")
OLLAMA_EMBED_MODEL  = os.getenv("OLLAMA_EMBED_MODEL",  "nomic-embed-text")
QDRANT_HOST         = os.getenv("QDRANT_HOST",         "localhost")
QDRANT_PORT         = int(os.getenv("QDRANT_PORT",     "6333"))
OLLAMA_HOST         = os.getenv("OLLAMA_HOST",         "localhost")
OLLAMA_PORT         = int(os.getenv("OLLAMA_PORT",     "11434"))
QDRANT_COLLECTION   = "pvg_college"
VECTOR_DIM          = 768
TOP_K               = 5
MIN_SCORE           = 0.45
MEMORY_TURNS        = 4

# ── TTS Configuration ──────────────────────────────────────────────────────────
PIPER_MODEL_PATH = os.getenv(
    "PIPER_MODEL_PATH",
    "./tts_models/en_US-amy-medium.onnx"
)
TTS_ENGINE = os.getenv("TTS_ENGINE", "piper")

# Check TTS model availability at startup
_piper_model_exists = Path(PIPER_MODEL_PATH).exists()
if not _piper_model_exists:
    log.warning(
        "⚠️  Piper TTS model NOT found at: %s\n"
        "   Voice output will use gTTS (requires internet) or be silent.\n"
        "   To fix: place en_US-amy-medium.onnx in ./tts_models/\n"
        "   or set PIPER_MODEL_PATH env var to the correct path.",
        PIPER_MODEL_PATH
    )
else:
    log.info("✅ Piper TTS model found at: %s", PIPER_MODEL_PATH)

SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')

SYSTEM_PROMPT = """You are a helpful voice assistant for Pune Vidyarthi Griha's College of Engineering (PVGCOET), Pune, India.
You help students, faculty, visitors, and admin staff with:
- Admissions and fees
- Faculty and department information
- Campus facilities, events and announcements
- Timetables and exam schedules

Answer concisely in 2-3 sentences — your response will be spoken aloud.
Answer from the provided context. If unsure, say so politely. Do NOT fabricate information."""


# ── INIT ───────────────────────────────────────────────────────────────────────
log.info("TTS engine: %s | gTTS available: %s | Piper model: %s",
         TTS_ENGINE, GTTS_AVAILABLE, "✓" if _piper_model_exists else "✗ (missing)")
log.info("Loading Faster-Whisper (%s)...", WHISPER_MODEL_SIZE)
whisper_model = WhisperModel(
    WHISPER_MODEL_SIZE, device=WHISPER_DEVICE,
    compute_type=WHISPER_COMPUTE, cpu_threads=6, num_workers=2
)
log.info("Whisper ready.")

qdrant        = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
ollama_client = ollama.Client(host=f"http://{OLLAMA_HOST}:{OLLAMA_PORT}")

sessions: Dict[str, deque] = {}


# ── LIFESPAN (replaces deprecated @app.on_event) ──────────────────────────────
# FIX #7: @app.on_event("startup") is deprecated since FastAPI 0.93 and will
# be removed in a future version. The modern replacement is the lifespan
# context manager, which is the correct pattern for FastAPI 0.95+.
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Replaces the deprecated @app.on_event("startup") pattern.
    Runs startup logic, then yields (app runs), then teardown (if any).
    """
    log.info("Creating database tables...")
    create_tables()
    _seed_default_admin()

    log.info("Warming up LLM and embedding models...")
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, lambda: ollama_client.chat(
            model=OLLAMA_LLM_MODEL,
            messages=[{"role": "user", "content": "hi"}],
            options={"num_predict": 1}
        ))
        await loop.run_in_executor(None, lambda: ollama_client.embeddings(
            model=OLLAMA_EMBED_MODEL, prompt="test"
        ))
        log.info("Warmup complete.")
    except Exception as e:
        log.warning("Warmup failed (first query will be slower): %s", e)

    yield  # App is running

    # Teardown (if needed in the future)
    log.info("Shutting down.")


app = FastAPI(
    title="PVG College Voice Assistant",
    description="Voice assistant + Admin dashboard API for PVGCOET",
    version="2.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register API routers ───────────────────────────────────────────────────────
app.include_router(auth_router,   prefix="/api")
app.include_router(events_router, prefix="/api")
app.include_router(notifs_router, prefix="/api")


# ── AUDIO PREPROCESSING ────────────────────────────────────────────────────────

def preprocess_audio(pcm_bytes: bytes, sr: int = 16000) -> bytes:
    """Normalize and optionally denoise raw PCM audio."""
    arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    if NOISEREDUCE_AVAILABLE:
        try:
            arr = nr.reduce_noise(y=arr, sr=sr, stationary=True, prop_decrease=0.75)
        except Exception:
            pass
    peak = np.max(np.abs(arr))
    if peak > 0.01:
        arr = arr / peak * 0.95
    return (arr * 32768.0).clip(-32768, 32767).astype(np.int16).tobytes()


# ── STT ─────────────────────────────────────────────────────────────────────────

def transcribe_audio(pcm_bytes: bytes, sr: int = 16000) -> str:
    """Transcribe raw PCM bytes → text using Faster-Whisper."""
    clean = preprocess_audio(pcm_bytes, sr)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
        with wave.open(tmp, "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
            wf.writeframes(clean)
    try:
        segs, info = whisper_model.transcribe(
            tmp, language="en", beam_size=3, vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400, "speech_pad_ms": 200, "threshold": 0.35},
            suppress_tokens=[-1], condition_on_previous_text=False,
            no_speech_threshold=0.6, log_prob_threshold=-1.0,
        )
        text = " ".join(s.text.strip() for s in segs).strip()
        if text.lower().strip(" .") in {"thank you", "you", "", "...", "hmm", "uh", "um"}:
            return ""
        log.info("STT: '%s' (%.1fs)", text, info.duration)
        return text
    finally:
        os.unlink(tmp)


# ── RAG ─────────────────────────────────────────────────────────────────────────

def retrieve_context(query: str) -> str:
    """
    Retrieve relevant text chunks from Qdrant vector store.
    Filters by MIN_SCORE to avoid irrelevant results.
    """
    vec_resp = ollama_client.embeddings(model=OLLAMA_EMBED_MODEL, prompt=query)
    vec = vec_resp["embedding"] if isinstance(vec_resp, dict) else vec_resp.embedding
    try:
        results = qdrant.query_points(
            collection_name=QDRANT_COLLECTION,
            query=vec,
            limit=TOP_K,
            with_payload=True,
            score_threshold=MIN_SCORE,
        )
        hits = results.points
    except AttributeError:
        hits = qdrant.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=vec,
            limit=TOP_K,
            with_payload=True,
            score_threshold=MIN_SCORE,
        )

    if hits:
        log.info("RAG: %d chunks (scores: %s)", len(hits), [round(h.score, 3) for h in hits])
    else:
        log.warning("RAG: No chunks above %.2f for '%s'", MIN_SCORE, query[:50])

    return "\n\n---\n\n".join(h.payload.get("text", "") for h in hits) if hits else ""


def fetch_live_context() -> str:
    """
    Fetch live events and notifications from the database.
    Appended to RAG context so voice assistant always has fresh data.
    """
    try:
        db = SessionLocal()
        events = get_upcoming_events(db, limit=10)
        notifications = get_recent_notifications(db, limit=5)
        db.close()

        parts = []
        events_text = format_events_for_voice(events)
        if events_text:
            parts.append(events_text)
        notifs_text = format_notifications_for_voice(notifications)
        if notifs_text:
            parts.append(notifs_text)

        return "\n\n".join(parts)
    except Exception as e:
        log.warning("Failed to fetch live context: %s", e)
        return ""


# ── TTS ─────────────────────────────────────────────────────────────────────────

def tts_piper(text: str) -> bytes:
    """
    Piper TTS — Amy medium voice (en_US-amy-medium), fully offline.
    Returns WAV bytes on success, empty bytes if model missing or error.
    """
    model_path = PIPER_MODEL_PATH
    json_path  = model_path + ".json"

    if not Path(model_path).exists():
        log.warning(
            "Piper model not found at '%s'. "
            "Download en_US-amy-medium.onnx from https://github.com/rhasspy/piper/releases "
            "and place it in ./tts_models/ or set PIPER_MODEL_PATH.",
            model_path
        )
        return b""

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        out = f.name
    try:
        cmd = ["piper", "--model", model_path, "--output_file", out]
        r = subprocess.run(cmd, input=text.encode(), capture_output=True, timeout=30)
        if r.returncode != 0:
            log.warning("Piper error (code %d): %s", r.returncode, r.stderr.decode()[:200])
            return b""
        return open(out, "rb").read()
    except FileNotFoundError:
        log.warning("Piper binary not found in PATH. Install piper-tts or check installation.")
        return b""
    except Exception as e:
        log.warning("Piper TTS exception: %s", e)
        return b""
    finally:
        if os.path.exists(out):
            os.unlink(out)


def tts_gtts(text: str) -> bytes:
    """
    Google TTS with Indian English accent (tld='co.in').
    Returns MP3 bytes. Requires internet.
    Falls back to Piper on network failure.
    """
    if not GTTS_AVAILABLE:
        log.warning("gTTS not installed — falling back to Piper")
        return tts_piper(text)
    try:
        tts = _gTTS(text=text, lang='en', tld='co.in', slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        log.warning("gTTS failed (%s), falling back to Piper", e)
        return tts_piper(text)


def tts_sentence(text: str) -> bytes:
    """
    TTS router — selects engine from TTS_ENGINE env var.
    Always falls back gracefully: no crash if model is missing.
    """
    text = text.strip()
    if not text:
        return b""

    if TTS_ENGINE == "gtts":
        return tts_gtts(text)
    return tts_piper(text)


# ── STREAMING PIPELINE ──────────────────────────────────────────────────────────

async def run_pipeline(ws: WebSocket, transcript: str, session_id: str):
    """
    Full-duplex streaming pipeline:
      1. Retrieve RAG context (Qdrant) + live events/notifications (DB)
      2. Stream LLM tokens
      3. TTS each sentence as it completes (concurrent with token stream)
      4. Update conversation memory
    """
    loop = asyncio.get_event_loop()

    await ws.send_json({"type": "status", "message": "Searching knowledge base..."})
    rag_context  = await loop.run_in_executor(None, retrieve_context, transcript)
    live_context = await loop.run_in_executor(None, fetch_live_context)

    context_parts = [p for p in [rag_context, live_context] if p.strip()]
    context = "\n\n---\n\n".join(context_parts)
    await ws.send_json({"type": "rag_done"})

    history  = sessions[session_id]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)

    if context:
        user_content = (
            f"Context from college knowledge base:\n{context}\n\n"
            f"Question: {transcript}\n\n"
            f"Answer using only the context above. Be concise, 2-3 sentences."
        )
    else:
        user_content = (
            f"Question: {transcript}\n\n"
            f"No relevant information was found in the college knowledge base. "
            f"Politely tell the user you don't have that information and suggest they "
            f"contact the college at 020-24228258 or enquiry@pvgcoet.ac.in"
        )
    messages.append({"role": "user", "content": user_content})

    await ws.send_json({"type": "status", "message": "Generating response..."})

    full_response = ""
    sentence_buf  = ""
    tts_tasks: List[asyncio.Task] = []
    token_queue: asyncio.Queue = asyncio.Queue()

    def _stream_to_queue():
        try:
            for chunk in ollama_client.chat(
                model=OLLAMA_LLM_MODEL,
                messages=messages,
                stream=True,
                options={"temperature": 0.3, "num_predict": 100, "num_ctx": 1024},
            ):
                # ollama-python >= 0.2 returns objects, not dicts
                if hasattr(chunk, "message"):
                    token = chunk.message.content or ""
                    is_done = chunk.done
                else:
                    # fallback for older dict-style responses
                    token   = chunk.get("message", {}).get("content", "")
                    is_done = chunk.get("done", False)
                asyncio.run_coroutine_threadsafe(
                    token_queue.put((token, is_done)), loop
                )
                if is_done:
                    break
        except Exception as e:
            asyncio.run_coroutine_threadsafe(token_queue.put(("__ERROR__", True)), loop)
            log.error("LLM stream error: %s", e)

    threading.Thread(target=_stream_to_queue, daemon=True).start()

    async def synthesize_and_send(sentence: str):
        sentence = sentence.strip()
        if not sentence:
            return
        audio = await loop.run_in_executor(None, tts_sentence, sentence)
        if audio:
            await ws.send_json({"type": "tts_chunk_start"})
            await ws.send_bytes(audio)
            await ws.send_json({"type": "tts_chunk_done"})
        else:
            await ws.send_json({"type": "tts_fallback", "text": sentence})

    while True:
        token, is_done = await token_queue.get()

        if token == "__ERROR__":
            await ws.send_json({"type": "error", "message": "LLM error occurred."})
            break

        if token:
            full_response += token
            sentence_buf  += token
            await ws.send_json({"type": "token", "text": token})

            parts = SENTENCE_SPLIT.split(sentence_buf)
            if len(parts) > 1:
                for complete in parts[:-1]:
                    if complete.strip():
                        task = asyncio.create_task(synthesize_and_send(complete))
                        tts_tasks.append(task)
                sentence_buf = parts[-1]

        if is_done:
            break

    if sentence_buf.strip():
        task = asyncio.create_task(synthesize_and_send(sentence_buf))
        tts_tasks.append(task)

    if tts_tasks:
        await asyncio.gather(*tts_tasks)

    sessions[session_id].append({"role": "user",      "content": transcript})
    sessions[session_id].append({"role": "assistant",  "content": full_response.strip()})

    await ws.send_json({"type": "response",   "text": full_response.strip()})
    await ws.send_json({"type": "audio_done"})
    log.info("Pipeline done. Response: '%s'", full_response.strip()[:80])


# ── WEBSOCKET ENDPOINT ──────────────────────────────────────────────────────────

@app.websocket("/ws/voice")
async def voice_ws(websocket: WebSocket):
    """
    Full-duplex voice WebSocket.
    Receives raw PCM audio → transcribes → RAG + live DB → LLM → TTS → streams back.
    """
    await websocket.accept()
    sid = str(uuid.uuid4())
    sessions[sid] = deque(maxlen=MEMORY_TURNS * 2)
    log.info("Session connected: %s", sid)

    try:
        await websocket.send_json({"type": "session", "session_id": sid})

        while True:
            msg = await websocket.receive()

            if "bytes" in msg and msg["bytes"]:
                log.info("Audio received: %d bytes", len(msg["bytes"]))
                await websocket.send_json({"type": "status", "message": "Transcribing..."})

                transcript = await asyncio.get_event_loop().run_in_executor(
                    None, transcribe_audio, msg["bytes"]
                )
                if not transcript:
                    await websocket.send_json({
                        "type": "error", "message": "Could not understand. Please try again."
                    })
                    continue

                await websocket.send_json({"type": "transcript", "text": transcript})
                await run_pipeline(websocket, transcript, sid)

            elif "text" in msg and msg["text"]:
                data = json.loads(msg["text"])
                t    = data.get("type")

                if t == "ping":
                    await websocket.send_json({"type": "pong"})
                elif t == "clear_history":
                    sessions[sid].clear()
                    await websocket.send_json({"type": "history_cleared"})
                elif t == "text_query":
                    q = data.get("text", "").strip()
                    if q:
                        await websocket.send_json({"type": "transcript", "text": q})
                        await run_pipeline(websocket, q, sid)

    except WebSocketDisconnect:
        log.info("Session disconnected: %s", sid)
    except RuntimeError as e:
        if "disconnect" in str(e).lower():
            log.info("Session closed by client: %s", sid)
        else:
            log.exception("Runtime error in session %s: %s", sid, e)
    except Exception as e:
        log.exception("Session error %s: %s", sid, e)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        sessions.pop(sid, None)


# ── HEALTH + ROOT ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    """Service health check."""
    return {
        "status": "ok",
        "llm": OLLAMA_LLM_MODEL,
        "stt": WHISPER_MODEL_SIZE,
        "tts_engine": TTS_ENGINE,
        "tts_model_path": PIPER_MODEL_PATH,
        "tts_model_present": _piper_model_exists,
    }


@app.get("/", tags=["System"])
async def root():
    return {"message": "PVG Voice Assistant API v2.0 running.", "docs": "/docs"}


def _seed_default_admin():
    """
    Create a default admin account if no admin users exist.
    Credentials come from environment variables — change before deploying!
    """
    default_username = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    default_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "PvgAdmin@2024!")
    default_email    = os.getenv("DEFAULT_ADMIN_EMAIL",    "admin@pvgcoet.ac.in")

    db = SessionLocal()
    try:
        if db.query(AdminUser).count() == 0:
            admin = AdminUser(
                username=default_username,
                email=default_email,
                hashed_password=hash_password(default_password),
            )
            db.add(admin)
            db.commit()
            log.info(
                "Default admin created → username: '%s' | "
                "Change password immediately via /api/auth endpoints!",
                default_username
            )
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
