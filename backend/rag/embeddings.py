"""Multilingual embedding model wrapper supporting BAAI/bge-m3."""

import logging
from typing import List, Optional

from langchain_core.embeddings import Embeddings

from backend.core.config import settings

logger = logging.getLogger(__name__)


class MultilingualEmbeddings(Embeddings):
    """Wraps BAAI/bge-m3 using sentence-transformers.

    Provides cross-lingual semantic matching between English queries and German passages.
    Includes a lightweight deterministic fallback when running in dry-run mode or offline tests.
    """

    def __init__(self, model_name: str = "BAAI/bge-m3", device: Optional[str] = None):
        self.model_name = model_name
        self.device = device
        self._model = None

    def _get_model(self):
        if self._model is None:
            if settings.GLOBAL_DRY_RUN:
                logger.info("GLOBAL_DRY_RUN active: using lightweight synthetic embedding provider.")
                return None

            try:
                from sentence_transformers import SentenceTransformer
                logger.info("Loading multilingual embedding model: %s", self.model_name)
                self._model = SentenceTransformer(self.model_name, device=self.device)
            except Exception as e:
                logger.warning(
                    "SentenceTransformer could not be loaded (%s). Operating in fallback embedding mode.",
                    e,
                )
                self._model = None
        return self._model

    def _mock_embed(self, text: str, dim: int = 1024) -> List[float]:
        """Generates deterministic pseudo-vector for offline tests/dry runs."""
        import hashlib
        import math
        hasher = hashlib.sha256(text.encode("utf-8"))
        seed = int(hasher.hexdigest()[:8], 16)
        vec = []
        for i in range(dim):
            val = math.sin(seed + i)
            vec.append(val)
        # Normalize
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [round(x / norm, 5) for x in vec]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        model = self._get_model()
        if model is not None:
            embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return embeddings.tolist()
        return [self._mock_embed(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        model = self._get_model()
        if model is not None:
            embedding = model.encode(text, normalize_embeddings=True, show_progress_bar=False)
            return embedding.tolist()
        return self._mock_embed(text)


embeddings_service = MultilingualEmbeddings()
