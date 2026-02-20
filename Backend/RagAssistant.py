from llama_index.llms.ollama import Ollama
from llama_index.core import VectorStoreIndex
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core.storage.storage_context import StorageContext
from llama_index.core.settings import Settings
from llama_index.embeddings.ollama import OllamaEmbedding

from qdrant_client import QdrantClient


class AIVoiceAssistant:

    def __init__(self):

        # Connect to LOCAL Qdrant
        self._client = QdrantClient(
            path="Documents/qdrant_storage"
        )

        # LLM
        self._llm = Ollama(
            model="qwen2.5:3b",
            base_url="http://localhost:11434",
            temperature=0.2,
            request_timeout=120.0
        )

        # Embedding model (MUST match chunking pipeline)
        Settings.embed_model = OllamaEmbedding(
            model_name="nomic-embed-text",
            base_url="http://localhost:11434"
        )

        Settings.llm = self._llm

        # Attach to existing collection
        vector_store = QdrantVectorStore(
            client=self._client,
            collection_name="college_semantic_kb"
        )

        storage_context = StorageContext.from_defaults(
            vector_store=vector_store
        )

        self._index = VectorStoreIndex.from_vector_store(
            vector_store,
            storage_context=storage_context
        )

        print("✅ Connected to Hybrid Semantic Knowledge Base")

        self._create_chat_engine()

    def _create_chat_engine(self):

        memory = ChatMemoryBuffer.from_defaults(
            token_limit=1500
        )

        self._chat_engine = self._index.as_chat_engine(
            chat_mode="context",
            memory=memory,
            system_prompt=self._prompt,
        )

    def interact_with_llm(self, query):
        response = self._chat_engine.chat(query)
        return response.response

    @property
    def _prompt(self):
        return """
You are an AI Assistant for PVG College.

You must answer ONLY PVG College-related questions.
This includes placements, departments, courses, facilities, faculty, policies, and events.

Use ONLY the provided context.

If the answer is not in the context, say:
"I'm sorry, I can only help with PVG College-related questions based on the available data."

Do NOT make up answers.
"""
