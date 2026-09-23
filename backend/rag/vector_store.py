"""Vector store management supporting PostgreSQL PGVector with in-memory fallback."""

import logging
from typing import List, Optional

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore, VectorStore

from backend.core.config import settings
from backend.rag.embeddings import embeddings_service

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """Manages vector store initialization, indexing, and retrieval connections."""

    def __init__(self):
        self._store: Optional[VectorStore] = None
        self._in_memory_fallback: Optional[InMemoryVectorStore] = None

    def get_vector_store(self) -> VectorStore:
        """Returns initialized PGVector store or in-memory fallback if PostgreSQL is unavailable."""
        if self._store is not None:
            return self._store

        if settings.GLOBAL_DRY_RUN or "sqlite" in settings.DATABASE_URL:
            logger.info("Using in-memory vector store for dry-run/local test.")
            if self._in_memory_fallback is None:
                self._in_memory_fallback = InMemoryVectorStore(embedding=embeddings_service)
            self._store = self._in_memory_fallback
            return self._store

        try:
            from langchain_postgres import PGEngine, PGVectorStore

            # Ensure URL has psycopg scheme
            conn_url = settings.DATABASE_URL
            if not conn_url.startswith("postgresql+psycopg://"):
                conn_url = conn_url.replace("postgresql://", "postgresql+psycopg://")

            engine = PGEngine.from_connection_string(conn_url)
            table_name = settings.PGVECTOR_COLLECTION

            # Dimension 1024 corresponds to BAAI/bge-m3
            try:
                engine.init_vectorstore_table(table_name=table_name, vector_size=1024)
            except Exception as e:
                logger.debug("Table init note: %s", e)

            self._store = PGVectorStore.create_sync(
                engine=engine,
                table_name=table_name,
                embedding_service=embeddings_service,
            )
            logger.info("Connected to PGVector store at table '%s'", table_name)
            return self._store

        except Exception as exc:
            logger.warning(
                "Could not connect to PostgreSQL PGVector (%s). Falling back to in-memory vector store.",
                exc,
            )
            if self._in_memory_fallback is None:
                self._in_memory_fallback = InMemoryVectorStore(embedding=embeddings_service)
            self._store = self._in_memory_fallback
            return self._store

    def add_documents(self, documents: List[Document]) -> List[str]:
        """Indexes documents into the vector store."""
        store = self.get_vector_store()
        return store.add_documents(documents)

    def as_retriever(self, k: int = 4):
        """Returns retriever interface."""
        store = self.get_vector_store()
        return store.as_retriever(search_kwargs={"k": k})


vector_store_manager = VectorStoreManager()
