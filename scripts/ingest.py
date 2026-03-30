"""
PVG College Knowledge Base Ingestion Script.
Reads uploaded documents from PostgreSQL, chunks them,
generates Nomic embeddings via Ollama, and stores in Qdrant.

Usage:
    python admin/backend/ingest.py
"""

import argparse
import logging
import os
import uuid

import ollama
import psycopg
from psycopg.rows import dict_row
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

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
                SELECT id, filename, extension, content
                FROM documents
                ORDER BY id ASC
                """
            )
            return cur.fetchall()


def ingest(database_url: str) -> None:
    documents = fetch_documents_from_sql(database_url)

    if not documents:
        log.error("No documents found in SQL database at %s", database_url)
        return

    log.info("Found %d documents to ingest from SQL.", len(documents))

    # ── Connect to Qdrant ────────────────────────────────────────────────────
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    # ── Recreate collection ──────────────────────────────────────────────────
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME in existing:
        log.info("Deleting existing collection '%s'...", COLLECTION_NAME)
        client.delete_collection(COLLECTION_NAME)

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
    )
    log.info("Created collection '%s'.", COLLECTION_NAME)

    # ── Process files ────────────────────────────────────────────────────────
    all_points = []
    total_chunks = 0

    for doc in documents:
        source_name = doc["filename"]
        text = (doc["content"] or "").strip()
        if not text:
            log.warning("Skipping empty document: %s (id=%s)", source_name, doc["id"])
            continue

        log.info("Processing: %s", source_name)
        chunks = chunk_text(text)
        log.info("  -> %d chunks", len(chunks))

        for i, chunk in enumerate(chunks):
            try:
                embedding = get_embedding(chunk)
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        "text": chunk,
                        "source": source_name,
                        "doc_id": doc["id"],
                        "chunk_index": i,
                    },
                )
                all_points.append(point)
                total_chunks += 1

                # Batch upsert every 20 points
                if len(all_points) >= 20:
                    client.upsert(collection_name=COLLECTION_NAME, points=all_points)
                    log.info(
                        "  Upserted batch of %d points (total: %d)",
                        len(all_points),
                        total_chunks,
                    )
                    all_points = []

            except Exception as e:
                log.error("  Error embedding chunk %d: %s", i, e)
                continue

    # Upsert remaining
    if all_points:
        client.upsert(collection_name=COLLECTION_NAME, points=all_points)
        log.info("Upserted final batch of %d points.", len(all_points))

    # ── Summary ──────────────────────────────────────────────────────────────
    count = client.count(collection_name=COLLECTION_NAME).count
    log.info(
        "Ingestion complete: %d chunks stored in Qdrant collection '%s'.",
        count,
        COLLECTION_NAME,
    )


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
