from typing import List
from app.core.config import settings
from app.core.logging import logger

class EmbeddingService:
    """Generates dense vector embeddings using local Sentence Transformers."""

    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            logger.info(f"Loading local Sentence Transformer model: {settings.EMBEDDING_MODEL}")
            from sentence_transformers import SentenceTransformer
            cls._model = SentenceTransformer(settings.EMBEDDING_MODEL)
            logger.info("Sentence Transformer model loaded successfully.")
        return cls._model

    @classmethod
    def embed_texts(cls, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        model = cls.get_model()
        embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return [emb.tolist() for emb in embeddings]

    @classmethod
    def embed_query(cls, query: str) -> List[float]:
        model = cls.get_model()
        embedding = model.encode(query, convert_to_numpy=True, show_progress_bar=False)
        return embedding.tolist()
