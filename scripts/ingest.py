"""
PVG College Knowledge Base Ingestion Script
Reads all .txt files from /data folder, chunks them,
generates Nomic embeddings via Ollama, and stores in Qdrant.

Usage:
    python scripts/ingest.py --data_dir ./data
"""

import argparse
import logging
import uuid
from pathlib import Path

import ollama
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── CONFIG ───────────────────────────────────────────────────────────────────
QDRANT_HOST       = "localhost"
QDRANT_PORT       = 6333
COLLECTION_NAME   = "pvg_college"
EMBED_MODEL       = "nomic-embed-text"
VECTOR_DIM        = 768
CHUNK_SIZE        = 400     # characters per chunk
CHUNK_OVERLAP     = 80      # overlap between chunks


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
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
                chunk = chunk[:last_period + 1]
                end = start + last_period + 1

        chunks.append(chunk.strip())
        start = end - overlap

    return [c for c in chunks if len(c.strip()) > 30]


def get_embedding(text: str) -> list[float]:
    """Get embedding from Ollama nomic-embed-text."""
    resp = ollama.embeddings(model=EMBED_MODEL, prompt=text)
    return resp["embedding"]


def ingest(data_dir: str):
    data_path = Path(data_dir)
    txt_files = list(data_path.glob("**/*.txt"))
    
    if not txt_files:
        log.error("No .txt files found in %s", data_dir)
        return

    log.info("Found %d .txt files to ingest.", len(txt_files))

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

    for txt_file in txt_files:
        log.info("Processing: %s", txt_file.name)
        try:
            text = txt_file.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            log.warning("Could not read %s: %s", txt_file, e)
            continue

        chunks = chunk_text(text)
        log.info("  → %d chunks", len(chunks))

        for i, chunk in enumerate(chunks):
            try:
                embedding = get_embedding(chunk)
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        "text": chunk,
                        "source": txt_file.name,
                        "chunk_index": i,
                    },
                )
                all_points.append(point)
                total_chunks += 1

                # Batch upsert every 20 points
                if len(all_points) >= 20:
                    client.upsert(collection_name=COLLECTION_NAME, points=all_points)
                    log.info("  Upserted batch of %d points (total: %d)", len(all_points), total_chunks)
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
    log.info("✅ Ingestion complete! %d chunks stored in Qdrant collection '%s'.", count, COLLECTION_NAME)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest college txt files into Qdrant")
    parser.add_argument("--data_dir", default="./data", help="Directory containing .txt files")
    args = parser.parse_args()
    ingest(args.data_dir)
