"""
Admin FastAPI backend for document upload + SQL storage.

Run:
    uvicorn app:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import json
import hashlib
import logging
import os
from urllib import error as urlerror
from urllib import request as urlrequest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - optional runtime dependency
    PdfReader = None


DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://admin_user:admin_pass@sql_database:5432/admin_db"
)
VOICE_BACKEND_URL = os.getenv("VOICE_BACKEND_URL", "http://127.0.0.1:8000")
VOICE_SYNC_TIMEOUT_SECONDS = int(os.getenv("VOICE_SYNC_TIMEOUT_SECONDS", "600"))
ALLOWED_EXTENSIONS = {".txt", ".pdf"}


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def get_connection() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def initialize_database() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id SERIAL PRIMARY KEY,
                    filename TEXT NOT NULL,
                    extension TEXT NOT NULL,
                    content TEXT NOT NULL,
                    uploaded_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                ALTER TABLE documents
                ADD COLUMN IF NOT EXISTS updated_at TEXT NOT NULL DEFAULT ''
                """
            )
            cur.execute(
                """
                ALTER TABLE documents
                ADD COLUMN IF NOT EXISTS content_hash TEXT NOT NULL DEFAULT ''
                """
            )
            cur.execute(
                """
                ALTER TABLE documents
                ADD COLUMN IF NOT EXISTS sync_status TEXT NOT NULL DEFAULT 'pending'
                """
            )
            cur.execute(
                """
                ALTER TABLE documents
                ADD COLUMN IF NOT EXISTS last_synced_at TEXT
                """
            )
            cur.execute(
                """
                ALTER TABLE documents
                ADD COLUMN IF NOT EXISTS sync_error TEXT
                """
            )
            cur.execute(
                """
                ALTER TABLE documents
                ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
            cur.execute(
                """
                UPDATE documents
                SET
                    updated_at = CASE
                        WHEN updated_at = '' THEN uploaded_at
                        ELSE updated_at
                    END,
                    content_hash = CASE
                        WHEN content_hash = '' THEN md5(content)
                        ELSE content_hash
                    END,
                    sync_status = CASE
                        WHEN sync_status = '' THEN 'pending'
                        ELSE sync_status
                    END
                """
            )
        conn.commit()


def parse_txt(raw: bytes) -> str:
    return raw.decode("utf-8", errors="ignore").strip()


def parse_pdf(raw: bytes) -> str:
    if PdfReader is None:
        raise HTTPException(
            status_code=500,
            detail="PDF support requires pypdf. Install it with: pip install pypdf",
        )
    from io import BytesIO

    reader = PdfReader(BytesIO(raw))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def parse_uploaded_content(filename: str, raw: bytes) -> tuple[str, str]:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail="Only .txt and .pdf files are supported."
        )

    if ext == ".txt":
        text = parse_txt(raw)
    else:
        text = parse_pdf(raw)

    if not text:
        raise HTTPException(
            status_code=400, detail=f"No extractable text found in {filename}."
        )

    return ext, text


def compute_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


app = FastAPI(title="PVG Admin Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    initialize_database()
    routes = sorted(
        f"{','.join(sorted(r.methods or []))} {r.path}"
        for r in app.routes
        if hasattr(r, "path") and "sync" in r.path
    )
    log.info("Admin backend registered sync routes: %s", routes)


@app.middleware("http")
async def log_sync_requests(request: Request, call_next):
    if "sync" in request.url.path:
        log.info(
            "Admin sync request received: method=%s path=%s",
            request.method,
            request.url.path,
        )
    response = await call_next(request)
    if "sync" in request.url.path:
        log.info(
            "Admin sync response sent: method=%s path=%s status=%s",
            request.method,
            request.url.path,
            response.status_code,
        )
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/documents")
async def upload_document(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file name.")

    raw = await file.read()
    ext, content = parse_uploaded_content(file.filename, raw)
    uploaded_at = current_timestamp()
    content_hash = compute_content_hash(content)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM documents
                WHERE filename = %s AND is_deleted = FALSE
                ORDER BY id DESC
                LIMIT 1
                """,
                (file.filename,),
            )
            existing = cur.fetchone()

            if existing is None:
                cur.execute(
                    """
                    INSERT INTO documents (
                        filename,
                        extension,
                        content,
                        uploaded_at,
                        updated_at,
                        content_hash,
                        sync_status,
                        last_synced_at,
                        sync_error,
                        is_deleted
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, 'pending', NULL, NULL, FALSE)
                    RETURNING id
                    """,
                    (file.filename, ext, content, uploaded_at, uploaded_at, content_hash),
                )
                row = cur.fetchone()
                action = "uploaded"
            else:
                cur.execute(
                    """
                    UPDATE documents
                    SET
                        extension = %s,
                        content = %s,
                        updated_at = %s,
                        content_hash = %s,
                        sync_status = 'pending',
                        last_synced_at = NULL,
                        sync_error = NULL,
                        is_deleted = FALSE
                    WHERE id = %s
                    RETURNING id, uploaded_at
                    """,
                    (ext, content, uploaded_at, content_hash, existing["id"]),
                )
                row = cur.fetchone()
                action = "updated"
        conn.commit()

    return {
        "id": row["id"],
        "filename": file.filename,
        "extension": ext,
        "uploaded_at": row.get("uploaded_at", uploaded_at),
        "updated_at": uploaded_at,
        "sync_status": "pending",
        "action": action,
        "message": f"Document {action} in SQL and marked for sync.",
    }


@app.put("/documents/{doc_id}")
async def update_document(doc_id: int, file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file name.")

    raw = await file.read()
    ext, content = parse_uploaded_content(file.filename, raw)
    updated_at = current_timestamp()
    content_hash = compute_content_hash(content)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE documents
                SET
                    filename = %s,
                    extension = %s,
                    content = %s,
                    updated_at = %s,
                    content_hash = %s,
                    sync_status = 'pending',
                    last_synced_at = NULL,
                    sync_error = NULL,
                    is_deleted = FALSE
                WHERE id = %s AND is_deleted = FALSE
                RETURNING id, uploaded_at
                """,
                (file.filename, ext, content, updated_at, content_hash, doc_id),
            )
            row = cur.fetchone()
        conn.commit()

    if row is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    return {
        "id": row["id"],
        "filename": file.filename,
        "extension": ext,
        "uploaded_at": row["uploaded_at"],
        "updated_at": updated_at,
        "sync_status": "pending",
        "action": "updated",
        "message": "Document updated in SQL and marked for sync.",
    }


@app.get("/documents")
def list_documents() -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    filename,
                    extension,
                    uploaded_at,
                    updated_at,
                    is_deleted,
                    sync_status,
                    last_synced_at,
                    sync_error,
                    LENGTH(content) AS content_length
                FROM documents
                WHERE is_deleted = FALSE OR sync_status IN ('pending_delete', 'failed')
                ORDER BY id DESC
                """
            )
            rows = cur.fetchall()

    return list(rows)


@app.get("/documents/{doc_id}")
def get_document(doc_id: int) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    filename,
                    extension,
                    content,
                    uploaded_at,
                    updated_at,
                    is_deleted,
                    sync_status,
                    last_synced_at,
                    sync_error
                FROM documents
                WHERE id = %s
                """,
                (doc_id,),
            )
            row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return row


@app.delete("/documents/{doc_id}")
def delete_document(doc_id: int) -> dict[str, str]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE documents
                SET
                    is_deleted = TRUE,
                    sync_status = 'pending_delete',
                    updated_at = %s,
                    sync_error = NULL
                WHERE id = %s AND is_deleted = FALSE
                """,
                (current_timestamp(), doc_id),
            )
            deleted = cur.rowcount
        conn.commit()

    if deleted == 0:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"message": "Document marked for deletion and pending vector cleanup."}


HARDCODED_LOGS: list[dict[str, Any]] = [
    {
        "id": 1,
        "user": "student_001",
        "action": "query_submitted",
        "details": "Asked about admission process",
        "timestamp": "2026-03-01T10:00:00Z",
    },
    {
        "id": 2,
        "user": "admin_001",
        "action": "document_uploaded",
        "details": "Uploaded placements.txt",
        "timestamp": "2026-03-01T10:30:00Z",
    },
]


def next_log_id() -> int:
    return max((item["id"] for item in HARDCODED_LOGS), default=0) + 1


@app.get("/logs")
def get_logs() -> list[dict[str, Any]]:
    return HARDCODED_LOGS


@app.post("/logs")
def create_log(log: dict[str, Any]) -> dict[str, Any]:
    new_log = {
        "id": next_log_id(),
        "user": log.get("user", "unknown"),
        "action": log.get("action", "unknown_action"),
        "details": log.get("details", ""),
        "timestamp": log.get(
            "timestamp", datetime.now(timezone.utc).isoformat(timespec="seconds")
        ),
    }
    HARDCODED_LOGS.append(new_log)
    return new_log


@app.put("/logs/{log_id}")
def update_log(log_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    for item in HARDCODED_LOGS:
        if item["id"] == log_id:
            item["user"] = payload.get("user", item["user"])
            item["action"] = payload.get("action", item["action"])
            item["details"] = payload.get("details", item["details"])
            item["timestamp"] = payload.get("timestamp", item["timestamp"])
            return item
    raise HTTPException(status_code=404, detail="Log not found.")


@app.delete("/logs/{log_id}")
def delete_log(log_id: int) -> dict[str, str]:
    index = next(
        (i for i, row in enumerate(HARDCODED_LOGS) if row["id"] == log_id), None
    )
    if index is None:
        raise HTTPException(status_code=404, detail="Log not found.")
    HARDCODED_LOGS.pop(index)
    return {"message": "Log deleted successfully."}


@app.post("/sync-documents")
def sync_documents() -> dict[str, Any]:
    sync_url = f"{VOICE_BACKEND_URL.rstrip('/')}/admin/sync-documents"
    log.info(
        "sync_documents called: voice_backend_url=%s sync_url=%s timeout=%ss",
        VOICE_BACKEND_URL,
        sync_url,
        VOICE_SYNC_TIMEOUT_SECONDS,
    )
    req = urlrequest.Request(sync_url, method="POST")

    try:
        with urlrequest.urlopen(req, timeout=VOICE_SYNC_TIMEOUT_SECONDS) as resp:
            body = resp.read().decode("utf-8")
            payload = json.loads(body) if body else {}
            log.info(
                "sync_documents upstream success: status=%s payload_keys=%s",
                getattr(resp, "status", "unknown"),
                list(payload.keys()) if isinstance(payload, dict) else "non-dict",
            )
            return {"message": "Document sync completed.", "sync": payload}
    except urlerror.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        log.error(
            "sync_documents upstream HTTP error: status=%s reason=%s url=%s body=%s",
            exc.code,
            exc.reason,
            sync_url,
            detail,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Voice backend sync failed ({exc.code}): {detail or exc.reason}",
        ) from exc
    except urlerror.URLError as exc:
        log.error(
            "sync_documents upstream URL error: url=%s reason=%s",
            sync_url,
            exc.reason,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Cannot reach voice backend sync API at {sync_url}: {exc.reason}",
        ) from exc
