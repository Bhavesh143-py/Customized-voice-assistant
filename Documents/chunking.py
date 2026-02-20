# ============================================================
# 0. Imports
# ============================================================

import os
import re
import json
import hashlib

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from langchain_ollama import OllamaEmbeddings

from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import TextNode
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core.storage.storage_context import StorageContext
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core.settings import Settings


# ============================================================
# 1. Embedding Models
# ============================================================

# Langchain embedding — only for SemanticChunker
lc_embedding = OllamaEmbeddings(model="nomic-embed-text")
test_vec = lc_embedding.embed_query("dimension test")
EMBEDDING_DIM = len(test_vec)
print(f"Embedding dimension detected → {EMBEDDING_DIM}")

# LlamaIndex embedding — for storing into Qdrant
Settings.embed_model = OllamaEmbedding(
    model_name="nomic-embed-text",
    base_url="http://localhost:11434"
)


# ============================================================
# 2. Persistence Helpers
# ============================================================

HASH_FILE = "./qdrant_storage/chunked_files.json"

def compute_file_hash(filepath):
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()

def load_hashes():
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE, "r") as f:
            return json.load(f)
    return {}

def save_hashes(hashes):
    os.makedirs(os.path.dirname(HASH_FILE), exist_ok=True)
    with open(HASH_FILE, "w") as f:
        json.dump(hashes, f, indent=2)

def get_changed_files(folder_path, stored_hashes):
    changed = []
    current_hashes = {}
    for file in os.listdir(folder_path):
        if file.endswith(".txt"):
            path = os.path.join(folder_path, file)
            file_hash = compute_file_hash(path)
            current_hashes[file] = file_hash
            if stored_hashes.get(file) != file_hash:
                changed.append({"path": path, "file": file, "hash": file_hash})
    return changed, current_hashes


# ============================================================
# 3. Chunking Helpers
# ============================================================

def split_by_headings(text):
    sections = re.split(r"\n(?=[A-Z][A-Z\s]{3,}\n)|\n(?=.*:)", text)
    return [s.strip() for s in sections if s.strip()]

recursive_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " ", ""]
)

semantic_splitter = SemanticChunker(
    lc_embedding,
    breakpoint_threshold_type="percentile"
)

def chunk_document(text, source):
    chunks = []
    sections = split_by_headings(text)
    for section in sections:
        rec_chunks = recursive_splitter.split_text(section)
        sem_docs = semantic_splitter.create_documents(rec_chunks)
        for chunk in sem_docs:
            if chunk.page_content.strip():
                # ✅ TextNode is what llama_index stores/reads natively
                chunks.append(TextNode(
                    text=chunk.page_content,
                    metadata={"source": source, "type": "txt"}
                ))
    return chunks


# ============================================================
# 4. Qdrant Setup
# ============================================================

collection_name = "college_semantic_kb"

client = QdrantClient(path="./qdrant_storage")

existing_collections = [c.name for c in client.get_collections().collections]

if collection_name not in existing_collections:
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )
    print(f"Created collection → {collection_name}")
else:
    print(f"Collection already exists → {collection_name}")

vector_store = QdrantVectorStore(client=client, collection_name=collection_name)
storage_context = StorageContext.from_defaults(vector_store=vector_store)


# ============================================================
# 5. Main — Only Process Changed Files
# ============================================================

stored_hashes = load_hashes()
changed_files, current_hashes = get_changed_files("scraped_text", stored_hashes)

if not changed_files:
    print("\n✅ No new or modified files detected. Skipping chunking.")
else:
    print(f"\n🔄 {len(changed_files)} file(s) changed. Processing...")

    all_new_chunks = []

    for file_info in changed_files:
        print(f"  Chunking → {file_info['file']}")
        with open(file_info["path"], "r", encoding="utf-8") as f:
            text = f.read()
        chunks = chunk_document(text, file_info["file"])
        all_new_chunks.extend(chunks)
        print(f"    → {len(chunks)} chunks")

    # ✅ Store using llama_index format — compatible with RagAssistant.py
    VectorStoreIndex(
        nodes=all_new_chunks,
        storage_context=storage_context,
        show_progress=True
    )

    print(f"\n✅ Added {len(all_new_chunks)} chunks to Qdrant.")
    save_hashes(current_hashes)
    print("💾 File hashes saved.")

print(f"\nTotal vectors in collection: {client.count(collection_name).count}")