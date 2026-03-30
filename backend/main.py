"""
PVG College Voice Assistant - FastAPI Backend
TRUE BIDIRECTIONAL STREAMING WebSocket:
  Browser → Server : raw PCM audio bytes
  Server → Browser : status JSONs + streamed LLM tokens + streamed TTS audio chunks
                     all flowing simultaneously, not in turn
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import wave
from collections import deque
from pathlib import Path
from typing import Dict

import numpy as np
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from faster_whisper import WhisperModel
from qdrant_client import QdrantClient
import ollama

try:
    import noisereduce as nr
    NOISEREDUCE_AVAILABLE = True
except ImportError:
    NOISEREDUCE_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── CONFIG (env-overridable for Docker) ───────────────────────────────────────
# Point directly to your local cached model — no re-download needed
# Faster-Whisper accepts either a model name ("medium") or a full local path
WHISPER_MODEL_SIZE = os.getenv(
    "WHISPER_MODEL_SIZE",
    "/home/apollo/.cache/huggingface/hub/models--Systran--faster-whisper-medium.en/snapshots/a29b04bd15381511a9af671baec01072039215e3"
)
WHISPER_DEVICE     = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE    = os.getenv("WHISPER_COMPUTE", "int8")
WHISPER_CPU_THREADS = int(os.getenv("WHISPER_CPU_THREADS", "4"))
WHISPER_NUM_WORKERS = int(os.getenv("WHISPER_NUM_WORKERS", "1"))
OLLAMA_LLM_MODEL   = os.getenv("OLLAMA_LLM_MODEL",  "qwen2.5:3b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
QDRANT_HOST        = os.getenv("QDRANT_HOST",        "localhost")
QDRANT_PORT        = int(os.getenv("QDRANT_PORT",    "6333"))
OLLAMA_HOST        = os.getenv("OLLAMA_HOST",        "localhost")
OLLAMA_PORT        = int(os.getenv("OLLAMA_PORT",    "11434"))
QDRANT_COLLECTION  = "pvg_college"
VECTOR_DIM         = 768
TOP_K              = 5
PIPER_MODEL_PATH   = os.getenv("PIPER_MODEL_PATH", "./tts_models/en_US-amy-medium.onnx")
MEMORY_TURNS       = 4

# Splits streamed LLM output into TTS-able sentences
SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')

SYSTEM_PROMPT = """You are a helpful voice assistant for Pune Vidyarthi Griha's College of Engineering (PVGCOET), Pune, India.
You help students, faculty, visitors, and admin staff with:
- Admissions and fees
- Faculty and department information
- Campus facilities and events
- Timetables and exam schedules

Answer concisely in 2-3 sentences — your response will be spoken aloud.
Only answer from the provided context. If unsure, say so politely. Do NOT fabricate information."""

# ── INIT ───────────────────────────────────────────────────────────────────────
log.info("Loading Faster-Whisper (%s)...", WHISPER_MODEL_SIZE)
whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device=WHISPER_DEVICE,
                              compute_type=WHISPER_COMPUTE, cpu_threads=WHISPER_CPU_THREADS, num_workers=WHISPER_NUM_WORKERS)
log.info("Whisper ready on device=%s compute_type=%s.", WHISPER_DEVICE, WHISPER_COMPUTE)

qdrant        = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
ollama_client = ollama.Client(host=f"http://{OLLAMA_HOST}:{OLLAMA_PORT}")

sessions: Dict[str, deque] = {}

app = FastAPI(title="PVG Voice Assistant")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://admin_user:admin_pass@sql_database:5432/admin_db"
)
INGEST_SCRIPT_PATH = os.getenv("INGEST_SCRIPT_PATH", "/app/scripts/ingest.py")

sync_lock = asyncio.Lock()
sync_state = {
    "in_progress": False,
    "last_sync_at": None,
    "last_status": "never_run",
    "last_message": "Sync has not been run yet.",
    "duration_seconds": None,
}


# ── AUDIO PREPROCESSING ────────────────────────────────────────────────────────

def preprocess_audio(pcm_bytes: bytes, sr: int = 16000) -> bytes:
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
        if text.lower().strip(" .") in {"thank you","you","","...","hmm","uh","um"}:
            return ""
        log.info("STT: '%s' (%.1fs)", text, info.duration)
        return text
    finally:
        os.unlink(tmp)


# ── RAG ─────────────────────────────────────────────────────────────────────────

def retrieve_context(query: str) -> str:
    vec = ollama_client.embeddings(model=OLLAMA_EMBED_MODEL, prompt=query)["embedding"]

    # Support both qdrant-client v1.7+ (query_points) and older (search)
    try:
        results = qdrant.query_points(
            collection_name=QDRANT_COLLECTION,
            query=vec,
            limit=TOP_K,
            with_payload=True,
        )
        hits = results.points
    except AttributeError:
        hits = qdrant.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=vec,
            limit=TOP_K,
            with_payload=True,
        )

    return "\n\n---\n\n".join(h.payload.get("text", "") for h in hits)


# ── TTS ─────────────────────────────────────────────────────────────────────────

def tts_sentence(text: str) -> bytes:
    """Synthesize one sentence with Piper, return WAV bytes."""
    if not Path(PIPER_MODEL_PATH).exists():
        return b""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        out = f.name
    try:
        r = subprocess.run(
            ["piper", "--model", PIPER_MODEL_PATH, "--output_file", out],
            input=text.encode(), capture_output=True, timeout=30,
        )
        return open(out, "rb").read() if r.returncode == 0 else b""
    finally:
        if os.path.exists(out): os.unlink(out)


# ── STREAMING PIPELINE ──────────────────────────────────────────────────────────

async def run_pipeline(ws: WebSocket, transcript: str, session_id: str):
    """
    TRUE FULL-DUPLEX streaming pipeline.

    What flows simultaneously over the WebSocket:
    ┌─────────────────────────────────────────────────────────┐
    │  Server → Browser (all these interleave in real time):  │
    │    {"type":"status", "message":"..."}                   │
    │    {"type":"rag_done"}                                   │
    │    {"type":"token",  "text":"Hello"}  ← per LLM token   │
    │    {"type":"token",  "text":" there"} ← next token      │
    │    {"type":"tts_chunk_start"}                           │
    │    <binary WAV bytes for sentence 1>  ← audio plays     │
    │    {"type":"tts_chunk_done"}          ←  while LLM      │
    │    {"type":"token",  "text":" The"}   ←  still running  │
    │    {"type":"tts_chunk_start"}                           │
    │    <binary WAV bytes for sentence 2>                    │
    │    {"type":"tts_chunk_done"}                            │
    │    {"type":"response", "text":"<full text>"}            │
    │    {"type":"audio_done"}                                │
    └─────────────────────────────────────────────────────────┘
    """
    if sync_state["in_progress"]:
        await ws.send_json(
            {
                "type": "error",
                "message": "Knowledge sync is in progress. Please retry in a moment.",
            }
        )
        return

    loop = asyncio.get_event_loop()

    # 1. RAG ───────────────────────────────────────────────────────────────────
    await ws.send_json({"type": "status", "message": "Searching knowledge base..."})
    context = await loop.run_in_executor(None, retrieve_context, transcript)
    await ws.send_json({"type": "rag_done"})

    # 2. Build messages for LLM ────────────────────────────────────────────────
    history = sessions[session_id]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content":
        f"Context:\n{context}\n\nQuestion: {transcript}\n\nAnswer based on context only."})

    await ws.send_json({"type": "status", "message": "Generating response..."})

    # 3. LLM token stream + sentence-level TTS ─────────────────────────────────
    full_response = ""
    sentence_buf  = ""
    tts_tasks     = []

    # Bridge blocking Ollama stream → async queue
    token_queue: asyncio.Queue = asyncio.Queue()

    def _stream_to_queue():
        """Runs in a thread: pulls tokens from Ollama, puts them in async queue."""
        try:
            for chunk in ollama_client.chat(
                model=OLLAMA_LLM_MODEL,
                messages=messages,
                stream=True,                       # ← streaming enabled
                options={"temperature": 0.3, "num_predict": 200, "num_ctx": 2048},
            ):
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

    # Start streaming in background thread
    threading.Thread(target=_stream_to_queue, daemon=True).start()

    async def synthesize_and_send(sentence: str):
        """TTS one sentence and immediately push WAV over WebSocket."""
        sentence = sentence.strip()
        if not sentence:
            return
        audio = await loop.run_in_executor(None, tts_sentence, sentence)
        if audio:
            await ws.send_json({"type": "tts_chunk_start"})
            await ws.send_bytes(audio)
            await ws.send_json({"type": "tts_chunk_done"})
        else:
            # Fallback to browser TTS for this sentence
            await ws.send_json({"type": "tts_fallback", "text": sentence})

    # Consume token queue — send tokens live + trigger TTS on sentence boundaries
    while True:
        token, is_done = await token_queue.get()

        if token == "__ERROR__":
            await ws.send_json({"type": "error", "message": "LLM error occurred."})
            break

        if token:
            full_response += token
            sentence_buf  += token

            # ── Send token immediately to browser for live text display ───────
            await ws.send_json({"type": "token", "text": token})

            # ── Check for sentence boundary → fire TTS immediately ────────────
            parts = SENTENCE_SPLIT.split(sentence_buf)
            if len(parts) > 1:
                for complete in parts[:-1]:
                    if complete.strip():
                        # asyncio.create_task = fire TTS concurrently
                        # while token stream continues — this IS the duplex part
                        task = asyncio.create_task(synthesize_and_send(complete))
                        tts_tasks.append(task)
                sentence_buf = parts[-1]

        if is_done:
            break

    # Synthesize any remaining buffer
    if sentence_buf.strip():
        task = asyncio.create_task(synthesize_and_send(sentence_buf))
        tts_tasks.append(task)

    # Wait for all TTS chunks to finish sending
    if tts_tasks:
        await asyncio.gather(*tts_tasks)

    # 4. Update memory + finalize ──────────────────────────────────────────────
    sessions[session_id].append({"role": "user",      "content": transcript})
    sessions[session_id].append({"role": "assistant",  "content": full_response.strip()})

    await ws.send_json({"type": "response",   "text": full_response.strip()})
    await ws.send_json({"type": "audio_done"})
    log.info("Pipeline done. Full response: '%s'", full_response.strip()[:80])


# ── WEBSOCKET ENDPOINT ──────────────────────────────────────────────────────────

@app.websocket("/ws/voice")
async def voice_ws(websocket: WebSocket):
    await websocket.accept()
    sid = str(uuid.uuid4())
    sessions[sid] = deque(maxlen=MEMORY_TURNS * 2)
    log.info("Session connected: %s", sid)

    try:
        await websocket.send_json({"type": "session", "session_id": sid})

        while True:
            msg = await websocket.receive()

            # ── Audio binary ──────────────────────────────────────────────────
            if "bytes" in msg and msg["bytes"]:
                log.info("Audio received: %d bytes", len(msg["bytes"]))
                await websocket.send_json({"type": "status", "message": "Transcribing..."})

                transcript = await asyncio.get_event_loop().run_in_executor(
                    None, transcribe_audio, msg["bytes"]
                )
                if not transcript:
                    await websocket.send_json({"type": "error",
                                               "message": "Could not understand. Please try again."})
                    continue

                await websocket.send_json({"type": "transcript", "text": transcript})
                await run_pipeline(websocket, transcript, sid)

            # ── Text control ─────────────────────────────────────────────────
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
    except Exception as e:
        log.exception("Session error %s: %s", sid, e)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        sessions.pop(sid, None)


# ── HEALTH ──────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "llm": OLLAMA_LLM_MODEL,
        "stt": WHISPER_MODEL_SIZE,
        "whisper_device": WHISPER_DEVICE,
        "whisper_compute_type": WHISPER_COMPUTE,
    }

@app.get("/")
async def root():
    return {"message": "PVG Voice Assistant API running."}


async def run_sync_job() -> dict:
    log.info(
        "run_sync_job started: ingest_script_path=%s database_url=%s",
        INGEST_SCRIPT_PATH,
        DATABASE_URL,
    )
    if not Path(INGEST_SCRIPT_PATH).exists():
        raise HTTPException(
            status_code=500,
            detail=f"Ingest script not found at {INGEST_SCRIPT_PATH}",
        )

    started_at = time.perf_counter()
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        INGEST_SCRIPT_PATH,
        "--database_url",
        DATABASE_URL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    duration = round(time.perf_counter() - started_at, 2)

    out_text = stdout.decode("utf-8", errors="ignore").strip()
    err_text = stderr.decode("utf-8", errors="ignore").strip()

    if proc.returncode != 0:
        sync_state.update(
            {
                "last_status": "failed",
                "last_message": err_text or out_text or "Sync failed",
                "duration_seconds": duration,
            }
        )
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Ingest failed.",
                "return_code": proc.returncode,
                "stderr": err_text,
                "stdout": out_text,
            },
        )

    sync_state.update(
        {
            "last_status": "success",
            "last_message": "Ingest completed successfully.",
            "duration_seconds": duration,
        }
    )
    return {
        "message": "Ingest completed successfully.",
        "duration_seconds": duration,
        "stdout": out_text,
        "stderr": err_text,
    }


async def _sync_documents_impl():
    log.info(
        "_sync_documents_impl called: lock_locked=%s in_progress=%s last_status=%s",
        sync_lock.locked(),
        sync_state["in_progress"],
        sync_state["last_status"],
    )
    if sync_lock.locked():
        log.warning("_sync_documents_impl rejected: sync already in progress")
        raise HTTPException(
            status_code=409, detail="A sync job is already in progress."
        )

    async with sync_lock:
        sync_state["in_progress"] = True
        log.info("_sync_documents_impl started: sync_state=%s", sync_state)
        try:
            result = await run_sync_job()
            sync_state["last_sync_at"] = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            )
            log.info(
                "_sync_documents_impl success: last_sync_at=%s",
                sync_state["last_sync_at"],
            )
            return result
        finally:
            sync_state["in_progress"] = False
            log.info("_sync_documents_impl finished: sync_state=%s", sync_state)


async def _sync_status_impl():
    return sync_state


@app.post("/admin/sync-documents")
async def sync_documents_admin():
    log.info("Route hit: POST /admin/sync-documents")
    return await _sync_documents_impl()


@app.get("/admin/sync-status")
async def sync_status_admin():
    log.info("Route hit: GET /admin/sync-status")
    return await _sync_status_impl()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
