
# Query Script 

from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from langchain_ollama import OllamaEmbeddings


# ============================================================
# 1. Embedding Model , must be same as model used in chunking script.
# ============================================================

embedding_model = OllamaEmbeddings(
    model="nomic-embed-text"
)


# ============================================================
# 2. Connect to Existing Qdrant Storage
# ============================================================

client = QdrantClient(
    path="./qdrant_storage"   # SAME path as ingestion
)

collection_name = "college_semantic_kb"


vectorstore = QdrantVectorStore(
    client=client,
    collection_name=collection_name,
    embedding=embedding_model
)


# ============================================================
# 3. Retriever
# ============================================================

retriever = vectorstore.as_retriever(
    search_kwargs={"k": 3}
)


# ============================================================
# 4. Interactive Query Loop
# ============================================================

print("\nCollege KB Query Interface Ready")
print("Type 'exit' to quit\n")

while True:

    query = input("Enter query → ")

    if query.lower() == "exit":
        break

    retrieved_docs = retriever.invoke(query)

    print("\n#### Retrieved Chunks ####")

    for i, d in enumerate(retrieved_docs):

        print(f"\n--- Result {i+1} ---")
        print(d.page_content)
        print("Metadata:", d.metadata)

    print("\n" + "="*50 + "\n")

