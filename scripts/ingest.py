"""
PVG College Knowledge Base Ingestion Script
Reads all .txt files from /data folder, chunks them,
generates Nomic embeddings via Ollama, and stores in Qdrant.

Usage:
    python scripts/ingest.py --data_dir ./data
"""

import argparse
import logging
import os
import uuid
from pathlib import Path

import ollama
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── CONFIG (env-overridable) ──────────────────────────────────────────────────
QDRANT_HOST     = os.getenv("QDRANT_HOST",       "localhost")
QDRANT_PORT     = int(os.getenv("QDRANT_PORT",   "6333"))
OLLAMA_HOST     = os.getenv("OLLAMA_HOST",        "localhost")
OLLAMA_PORT     = int(os.getenv("OLLAMA_PORT",    "11434"))
COLLECTION_NAME = "pvg_college"
EMBED_MODEL     = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
VECTOR_DIM      = 768
CHUNK_SIZE      = 400     # characters per chunk
CHUNK_OVERLAP   = 80      # overlap between chunks


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks with sentence-boundary awareness."""
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
                chunk = chunk[:last_period + 1]
                end = start + last_period + 1

        chunks.append(chunk.strip())
        start = end - overlap

    return [c for c in chunks if c]


def main():
    parser = argparse.ArgumentParser(description="Ingest college data into Qdrant")
    parser.add_argument("--data_dir", default="./data", help="Directory with .txt files")
    parser.add_argument("--reset", action="store_true", help="Delete and recreate the collection")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        log.error("Data directory not found: %s", data_dir)
        return

    txt_files = list(data_dir.glob("*.txt"))
    if not txt_files:
        log.warning("No .txt files found in %s", data_dir)
        return

    log.info("Found %d .txt files in %s", len(txt_files), data_dir)

    # ── Init clients ──────────────────────────────────────────────────────────
    qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    ollama_client = ollama.Client(host=f"http://{OLLAMA_HOST}:{OLLAMA_PORT}")

    # ── Collection setup ──────────────────────────────────────────────────────
    existing = [c.name for c in qdrant.get_collections().collections]

    if args.reset and COLLECTION_NAME in existing:
        qdrant.delete_collection(COLLECTION_NAME)
        log.info("Deleted existing collection '%s'", COLLECTION_NAME)
        existing = []

    if COLLECTION_NAME not in existing:
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        log.info("Created collection '%s'", COLLECTION_NAME)
    else:
        log.info("Using existing collection '%s'", COLLECTION_NAME)

    # ── Ingest files ──────────────────────────────────────────────────────────
    total_chunks = 0
    for txt_file in txt_files:
        log.info("Processing: %s", txt_file.name)
        text = txt_file.read_text(encoding="utf-8", errors="replace")
        chunks = chunk_text(text)
        log.info("  → %d chunks", len(chunks))

        points = []
        for chunk in chunks:
            try:
                emb_resp = ollama_client.embeddings(model=EMBED_MODEL, prompt=chunk)
                embedding = emb_resp["embedding"] if isinstance(emb_resp, dict) else emb_resp.embedding
                points.append(PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={"text": chunk, "source": txt_file.name},
                ))
            except Exception as e:
                log.warning("  Embedding failed for chunk: %s", e)

        if points:
            qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
            log.info("  → Upserted %d points", len(points))
            total_chunks += len(points)

    log.info("Ingestion complete. Total chunks: %d", total_chunks)


if __name__ == "__main__":
    main()
