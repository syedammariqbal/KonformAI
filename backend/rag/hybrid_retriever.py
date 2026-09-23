"""Hybrid RAG retriever fusing dense multilingual embeddings with per-language BM25 indexes."""

import logging
from typing import Dict, List, Optional

from langchain_community.retrievers import BM25Retriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

try:
    from langchain.retrievers import EnsembleRetriever
except ImportError:
    try:
        from langchain_classic.retrievers import EnsembleRetriever
    except Exception:
        class EnsembleRetriever(BaseRetriever):
            """Combines documents from multiple retrievers using Reciprocal Rank Fusion (RRF)."""

            retrievers: List[BaseRetriever]
            weights: List[float]
            c: int = 60

            def _get_relevant_documents(
                self, query: str, *, run_manager: Optional[CallbackManagerForRetrieverRun] = None
            ) -> List[Document]:
                all_docs: Dict[str, tuple[Document, float]] = {}
                total_weight = sum(self.weights) if self.weights else 1.0
                weights = [w / total_weight for w in self.weights] if self.weights else [1.0 / len(self.retrievers)] * len(self.retrievers)

                for retriever, weight in zip(self.retrievers, weights):
                    try:
                        docs = retriever.invoke(query)
                    except Exception as exc:
                        logger.warning("Sub-retriever %s failed in ensemble: %s", type(retriever).__name__, exc)
                        docs = []

                    for rank, doc in enumerate(docs):
                        key = doc.page_content
                        if key not in all_docs:
                            all_docs[key] = (doc, 0.0)
                        doc_obj, score = all_docs[key]
                        all_docs[key] = (doc_obj, score + weight * (1.0 / (rank + self.c)))

                sorted_docs = sorted(all_docs.values(), key=lambda x: x[1], reverse=True)
                return [doc for doc, _ in sorted_docs]

from backend.rag.vector_store import vector_store_manager

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Combines BM25 lexical search (separated by language) and dense PGVector retrieval."""

    def __init__(self):
        self.bm25_en: Optional[BM25Retriever] = None
        self.bm25_de: Optional[BM25Retriever] = None
        self._en_docs: List[Document] = []
        self._de_docs: List[Document] = []

    def build_bm25_indexes(self, documents: List[Document]) -> None:
        """Splits corpus by language tag and instantiates separate BM25 indices."""
        self._en_docs = [doc for doc in documents if doc.metadata.get("language", "en") == "en"]
        self._de_docs = [doc for doc in documents if doc.metadata.get("language", "en") == "de"]

        if self._en_docs:
            self.bm25_en = BM25Retriever.from_documents(self._en_docs)
            self.bm25_en.k = 4
            logger.info("Indexed %d English documents in BM25 English index.", len(self._en_docs))
        else:
            logger.warning("No English documents provided to BM25 English index.")

        if self._de_docs:
            self.bm25_de = BM25Retriever.from_documents(self._de_docs)
            self.bm25_de.k = 4
            logger.info("Indexed %d German documents in BM25 German index.", len(self._de_docs))
        else:
            logger.warning("No German documents provided to BM25 German index.")

    def get_ensemble_retriever(
        self,
        language: str = "en",
        dense_weight: float = 0.6,
        sparse_weight: float = 0.4,
        k: int = 4,
    ) -> EnsembleRetriever:
        """Builds an EnsembleRetriever combining dense vector search and language-specific BM25."""
        dense_retriever = vector_store_manager.as_retriever(k=k)

        # Select matching BM25 index based on target query language
        bm25_retriever = self.bm25_de if language == "de" else self.bm25_en

        # If language BM25 is not populated, fallback to whatever is available
        if bm25_retriever is None:
            bm25_retriever = self.bm25_en or self.bm25_de

        if bm25_retriever is None:
            # Fallback if no documents loaded into BM25 yet: create minimal dummy BM25
            dummy_doc = Document(
                page_content="Regulatory framework for AI in finance",
                metadata={"source_document": "seed", "language": language}
            )
            bm25_retriever = BM25Retriever.from_documents([dummy_doc])

        bm25_retriever.k = k

        return EnsembleRetriever(
            retrievers=[bm25_retriever, dense_retriever],
            weights=[sparse_weight, dense_weight],
            c=60,
        )

    def retrieve(
        self,
        query: str,
        language: str = "en",
        k: int = 4,
    ) -> List[Document]:
        """Queries the hybrid retrieval pipeline and returns ranked Document objects."""
        ensemble = self.get_ensemble_retriever(language=language, k=k)
        docs = ensemble.invoke(query)

        # Ensure all documents have standard metadata attributes
        for idx, doc in enumerate(docs):
            if "article_section_id" not in doc.metadata:
                doc.metadata["article_section_id"] = doc.metadata.get("section", f"Passage-{idx+1}")
            if "source_document" not in doc.metadata:
                doc.metadata["source_document"] = doc.metadata.get("source", "Regulatory Knowledge Base")
            if "language" not in doc.metadata:
                doc.metadata["language"] = language
            if "passage_id" not in doc.metadata:
                doc.metadata["passage_id"] = f"{doc.metadata['source_document']}::{doc.metadata['article_section_id']}"

        return docs


hybrid_retriever = HybridRetriever()
