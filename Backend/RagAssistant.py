from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from qdrant_client import QdrantClient
from llama_index.llms.ollama import Ollama
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core.storage.storage_context import StorageContext
from llama_index.core.settings import Settings

import warnings

warnings.filterwarnings("ignore")


class AIVoiceAssistant:
    def __init__(self):
        self._qdrant_url = "http://qdrant:6333"
        self._client = QdrantClient(url=self._qdrant_url, prefer_grpc=False)

        # Ollama LLM (CPU-only)
        self._llm = Ollama(
            model="qwen2.5:3b",
            base_url="http://ollama:11434",
            temperature=0.2,
            request_timeout=120.0
        )

        # Modern LlamaIndex configuration (NO ServiceContext)
        Settings.llm = self._llm
        Settings.embed_model = HuggingFaceEmbedding(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )

        self._index = None
        self._create_kb()
        self._create_chat_engine()

    def _create_chat_engine(self):
        memory = ChatMemoryBuffer.from_defaults(token_limit=1500)
        self._chat_engine = self._index.as_chat_engine(
            chat_mode="context",
            memory=memory,
            system_prompt=self._prompt,
        )

    def _create_kb(self):
        try:
            reader = SimpleDirectoryReader(input_files=["Documents/pvg.txt"])
            documents = reader.load_data()

            vector_store = QdrantVectorStore(
                client=self._client, collection_name="pvg_db"
            )

            storage_context = StorageContext.from_defaults(vector_store=vector_store)

            # NO service_context anymore
            self._index = VectorStoreIndex.from_documents(
                documents, storage_context=storage_context
            )

            print("Knowledgebase created successfully!")

        except Exception as e:
            print(f"Error while creating knowledgebase: {e}")

    def interact_with_llm(self, customer_query):
        response = self._chat_engine.chat(customer_query)
        return response.response

    @property
    def _prompt(self):
        return """
You are an AI Placement Assistant for a college.

You must answer ONLY placement-related questions.
Use ONLY the provided context.
If the answer is not available, say:
"I'm sorry, I can only help with placement-related questions based on available data."

Do NOT make up answers.
"""
