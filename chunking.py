# ============================================================
# 0. Imports
# ============================================================

import os
import re
import pandas as pd

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

from langchain_ollama import OllamaEmbeddings


# ============================================================
# 1. Embedding Model (LOCAL)
# ============================================================

embedding_model = OllamaEmbeddings(
    model="nomic-embed-text"
)

# Detect embedding dimension dynamically
test_vec = embedding_model.embed_query("dimension test")
EMBEDDING_DIM = len(test_vec)

print(f"Embedding dimension detected → {EMBEDDING_DIM}")


# ============================================================
# 2. Load Multiple TXT Files
# ============================================================

def load_txt_folder(folder_path):

    docs = []

    for file in os.listdir(folder_path):

        if file.endswith(".txt"):

            path = os.path.join(folder_path, file)

            with open(path, "r", encoding="utf-8") as f:
                text = f.read()

            docs.append({
                "text": text,
                "source": file,
                "type": "txt"
            })

            print(f"Loaded TXT → {file}")

    return docs
# ============================================================
# 4. Combine Corpus
# ============================================================

txt_docs = load_txt_folder("scraped_text")
all_docs = txt_docs
print(f"\nTotal raw docs: {len(all_docs)}")


# ============================================================
# 5. TRUE HYBRID CHUNKING (Structure + Recursive + Semantic)
# ============================================================

print("\n#### Hybrid Semantic Chunking ####")

import re
from langchain_experimental.text_splitter import SemanticChunker


# ---------- 1. Heading Split ----------
def split_by_headings(text):

    sections = re.split(
        r"\n(?=[A-Z][A-Z\s]{3,}\n)|\n(?=.*:)",
        text
    )

    return [s.strip() for s in sections if s.strip()]


# ---------- 2. Recursive Split ----------
from langchain_text_splitters import RecursiveCharacterTextSplitter

recursive_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " ", ""]
)


# ---------- 3. Semantic Refinement ----------
semantic_splitter = SemanticChunker(
    embedding_model,
    breakpoint_threshold_type="percentile"
)


chunked_documents = []

for doc in all_docs:

    # ---- Structure split ----
    sections = split_by_headings(doc["text"])

    for section in sections:

        # ---- Size control ----
        rec_chunks = recursive_splitter.split_text(section)

        # ---- Semantic refinement ----
        sem_docs = semantic_splitter.create_documents(rec_chunks)

        for chunk in sem_docs:

            chunked_documents.append(
                Document(
                    page_content=chunk.page_content,
                    metadata={
                        "source": doc["source"],
                        "type": doc["type"]
                    }
                )
            )

print(f"Total hybrid semantic chunks: {len(chunked_documents)}")


# ============================================================
# 6. Create / Connect Qdrant Collection
# ============================================================

collection_name = "college_semantic_kb"

client = QdrantClient(
    path="./qdrant_storage"
)

existing_collections = [
    c.name for c in client.get_collections().collections
]

if collection_name not in existing_collections:

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=EMBEDDING_DIM,
            distance=Distance.COSINE
        ),
    )

    print(f"Created collection → {collection_name}")

else:
    print(f"Collection already exists → {collection_name}")


vectorstore = QdrantVectorStore(
    client=client,
    collection_name=collection_name,
    embedding=embedding_model
)

vectorstore.add_documents(chunked_documents)

print("\nEmbeddings stored in Qdrant.")

# ============================================================
# 8. RAW CHUNK OUTPUT (Debug View)
# ============================================================

print("\n#### RAW HYBRID CHUNKS ####")

for i, chunk in enumerate(chunked_documents[:10]):

    print(f"\n--- Chunk {i+1} (len={len(chunk.page_content)}) ---\n")
    print(chunk.page_content)
    print("\nMetadata:", chunk.metadata)

