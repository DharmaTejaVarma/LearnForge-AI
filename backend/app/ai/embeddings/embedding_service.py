import os
import threading
from typing import List
from app.core.config import settings
from app.core.logging import logger

# Prevent transformers from importing TensorFlow/Keras (~90s startup overhead on CPU)
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


class EmbeddingService:
    """Thread-safe, bounded Sentence Transformer embedding service."""

    _model = None
    _model_lock = threading.Lock()
    _encode_lock = threading.Lock()

    @classmethod
    def get_model(cls):
        if cls._model is None:
            with cls._model_lock:
                if cls._model is None:
                    logger.info(f"Loading local Sentence Transformer model: {settings.EMBEDDING_MODEL}")
                    try:
                        import torch
                        torch.set_num_threads(min(8, os.cpu_count() or 8))
                    except Exception:
                        pass
                    from sentence_transformers import SentenceTransformer
                    try:
                        cls._model = SentenceTransformer(settings.EMBEDDING_MODEL, local_files_only=True)
                    except Exception:
                        cls._model = SentenceTransformer(settings.EMBEDDING_MODEL)
                    logger.info("Sentence Transformer model loaded successfully.")
        return cls._model

    @classmethod
    def embed_texts(cls, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        model = cls.get_model()
        with cls._encode_lock:
            embeddings = model.encode(texts, batch_size=64, convert_to_numpy=True, show_progress_bar=False)
        return [emb.tolist() for emb in embeddings]

    @classmethod
    def embed_query(cls, query: str) -> List[float]:
        model = cls.get_model()
        with cls._encode_lock:
            embedding = model.encode(query, convert_to_numpy=True, show_progress_bar=False)
        return embedding.tolist()
