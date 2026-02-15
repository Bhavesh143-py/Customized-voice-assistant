from rich import print
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from langchain_community.embeddings import OllamaEmbeddings
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

import os
import pandas as pd

from agentic_chunker import AgenticChunker

# ---------------- LLM ----------------
local_llm = ChatOllama(
    model="qwen2.5:3b",
    temperature=0
)

# ============================================================
# Persistent RAG
# ============================================================

def collection_exists(client, name):
    collections = client.get_collections().collections
    return any(c.name == name for c in collections)


def rag(documents, collection_name):

    client = QdrantClient(
        path="./qdrant_storage"   # PERSISTENT
    )

    if not collection_exists(client, collection_name):

        print("Creating vector index...")

        vectorstore = QdrantVectorStore.from_documents(
            documents=documents,
            collection_name=collection_name,
            embedding=OllamaEmbeddings(
                model="nomic-embed-text"
            ),
            client=client
        )

    else:
        print("Loading existing vector index...")

        vectorstore = QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            embedding=OllamaEmbeddings(
                model="nomic-embed-text"
            )
        )

    retriever = vectorstore.as_retriever()

    prompt_template = """Answer the question based only on the following context:
{context}
Question: {question}
"""
    prompt = ChatPromptTemplate.from_template(prompt_template)

    chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | local_llm
        | StrOutputParser()
    )

    result = chain.invoke(
        "What is the use of Text Splitting?"
    )

    print(result)


# ============================================================
# TXT
# ============================================================

def load_txt_folder(folder_path):

    all_text = ""

    for file in os.listdir(folder_path):
        if file.endswith(".txt"):

            with open(
                os.path.join(folder_path, file),
                "r",
                encoding="utf-8"
            ) as f:
                all_text += f.read() + "\n\n"

    return all_text

# ============================================================
# Load Data
# ============================================================

txt_text = load_txt_folder(
    "/home/apollo/Z/1_work_Study/3-college/scraping_And_Semantic_Chuking/scraped_text"
)
text = txt_text 

paragraphs = text.split("\n\n")


# ============================================================
# Agentic Chunking (Persistent)
# ============================================================

ac = AgenticChunker()

CHUNK_PATH = "agentic_chunks.json"

if os.path.exists(CHUNK_PATH):

    print("Loading existing agentic chunks...")
    ac.load_chunks(CHUNK_PATH)

else:

    print("Running agentic chunking...")

    from typing import List

    def get_propositions(text):

        prompt = ChatPromptTemplate.from_template(
            """Break the following text into atomic factual propositions.

Text:
{text}

Return a list of clear standalone sentences."""
        )

        chain = prompt | local_llm

        output = chain.invoke(
            {"text": text}
        ).content

        lines = output.split("\n")

        return [
            line.strip("- ").strip()
            for line in lines
            if line.strip()
        ]

    text_propositions = []

    for para in paragraphs[:5]:
        props = get_propositions(para)
        text_propositions.extend(props)

    ac.add_propositions(text_propositions)

    ac.save_chunks(CHUNK_PATH)


# ============================================================
# Convert to Documents
# ============================================================

documents = [
    Document(
        page_content=" ".join(chunk["propositions"]),
        metadata={
            "chunk_id": chunk["chunk_id"],
            "title": chunk["title"],
            "summary": chunk["summary"],
            "source": "agentic"
        }
    )
    for chunk in ac.chunks.values()
]

# ============================================================
# Run RAG
# ============================================================

rag(documents, "agentic-chunks")
