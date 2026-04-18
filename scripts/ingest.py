"""
PVG College Knowledge Base Ingestion Script.
Reads uploaded documents from PostgreSQL, chunks them,
generates Nomic embeddings via Ollama, and stores in Qdrant.

Usage:
    python admin/backend/ingest.py
"""

import argparse
import json
import logging
import os
import uuid

import ollama
import psycopg
from psycopg.rows import dict_row
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# ── CONFIG ───────────────────────────────────────────────────────────────────
QDRANT_HOST = os.getenv("QDRANT_HOST", "pvg_qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "pvg_college")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
VECTOR_DIM = int(os.getenv("VECTOR_DIM", "768"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "400"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "80"))

DEFAULT_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://admin_user:admin_pass@sql_database:5432/admin_db"
)
OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    f"http://{os.getenv('OLLAMA_HOST', 'pvg_ollama')}:{os.getenv('OLLAMA_PORT', '11434')}",
)
OLLAMA_CLIENT = ollama.Client(host=OLLAMA_BASE_URL)


def chunk_text(
    text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    """Split text into overlapping chunks."""
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Try to break at sentence boundary
        if end < len(text):
            last_period = max(chunk.rfind(". "), chunk.rfind("\n"))
            if last_period > chunk_size // 2:
                chunk = chunk[: last_period + 1]
                end = start + last_period + 1

        chunks.append(chunk.strip())
        start = end - overlap

    return [c for c in chunks if len(c.strip()) > 30]


def get_embedding(text: str) -> list[float]:
    """Get embedding from Ollama nomic-embed-text."""
    resp = OLLAMA_CLIENT.embeddings(model=EMBED_MODEL, prompt=text)
    return resp["embedding"]


def fetch_documents_from_sql(database_url: str) -> list[dict]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, filename, extension, content, content_hash, sync_status, is_deleted
                FROM documents
                WHERE sync_status IN ('pending', 'failed', 'pending_delete')
                ORDER BY id ASC
                """
            )
            return cur.fetchall()


def ensure_collection(client: QdrantClient) -> None:
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        log.info("Created collection '%s'.", COLLECTION_NAME)


def delete_doc_vectors(client: QdrantClient, doc_id: int) -> None:
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=Filter(
            must=[
                FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
            ]
        ),
    )


def mark_document_synced(conn: psycopg.Connection, doc_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE documents
            SET
                sync_status = 'synced',
                last_synced_at = NOW() AT TIME ZONE 'UTC',
                sync_error = NULL
            WHERE id = %s
            """,
            (doc_id,),
        )


def mark_document_failed(conn: psycopg.Connection, doc_id: int, error_message: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE documents
            SET
                sync_status = 'failed',
                sync_error = %s
            WHERE id = %s
            """,
            (error_message[:1000], doc_id),
        )


def purge_deleted_document(conn: psycopg.Connection, doc_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM documents WHERE id = %s AND is_deleted = TRUE", (doc_id,))


def active_document_count(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS count FROM documents WHERE is_deleted = FALSE")
        return int(cur.fetchone()["count"])


def ingest(database_url: str) -> None:
    documents = fetch_documents_from_sql(database_url)

    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    ensure_collection(client)

    summary = {
        "processed": 0,
        "upserted": 0,
        "deleted": 0,
        "failed": 0,
    }

    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        if not documents:
            if active_document_count(conn) == 0:
                existing = [c.name for c in client.get_collections().collections]
                if COLLECTION_NAME in existing:
                    log.info("No active SQL documents remain. Resetting collection '%s'.", COLLECTION_NAME)
                    client.delete_collection(COLLECTION_NAME)
                    ensure_collection(client)
            log.info("No pending SQL document changes found.")
            print(json.dumps(summary))
            return

        log.info("Found %d pending document changes to sync from SQL.", len(documents))

        for doc in documents:
            doc_id = doc["id"]
            source_name = doc["filename"]
            summary["processed"] += 1

            try:
                delete_doc_vectors(client, doc_id)

                if doc["is_deleted"] or doc["sync_status"] == "pending_delete":
                    purge_deleted_document(conn, doc_id)
                    conn.commit()
                    summary["deleted"] += 1
                    log.info("Deleted vectors and purged document id=%s (%s).", doc_id, source_name)
                    continue

                text = (doc["content"] or "").strip()
                if not text:
                    raise ValueError(f"Document '{source_name}' (id={doc_id}) has no content to embed.")

                chunks = chunk_text(text)
                if not chunks:
                    raise ValueError(f"Document '{source_name}' (id={doc_id}) produced no valid chunks.")

                all_points = []
                for i, chunk in enumerate(chunks):
                    embedding = get_embedding(chunk)
                    all_points.append(
                        PointStruct(
                            id=str(uuid.uuid4()),
                            vector=embedding,
                            payload={
                                "text": chunk,
                                "source": source_name,
                                "doc_id": doc_id,
                                "content_hash": doc["content_hash"],
                                "chunk_index": i,
                            },
                        )
                    )

                    if len(all_points) >= 20:
                        client.upsert(collection_name=COLLECTION_NAME, points=all_points)
                        all_points = []

                if all_points:
                    client.upsert(collection_name=COLLECTION_NAME, points=all_points)

                mark_document_synced(conn, doc_id)
                conn.commit()
                summary["upserted"] += 1
                log.info("Synced document id=%s (%s) with %d chunks.", doc_id, source_name, len(chunks))
            except Exception as e:
                conn.rollback()
                mark_document_failed(conn, doc_id, str(e))
                conn.commit()
                summary["failed"] += 1
                log.error("Failed syncing document id=%s (%s): %s", doc_id, source_name, e)

    count = client.count(collection_name=COLLECTION_NAME).count
    log.info(
        "Incremental sync complete: %d chunks currently stored in Qdrant collection '%s'.",
        count,
        COLLECTION_NAME,
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest admin SQL documents into Qdrant"
    )
    parser.add_argument(
        "--database_url",
        default=DEFAULT_DATABASE_URL,
        help="PostgreSQL connection string (defaults to DATABASE_URL env var)",
    )
    args = parser.parse_args()
    ingest(args.database_url)
