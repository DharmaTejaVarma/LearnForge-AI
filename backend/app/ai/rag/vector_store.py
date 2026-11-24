from pathlib import Path
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.core.config import settings
from app.core.logging import logger

COLLECTION_NAME = "learnforge_knowledge"

class VectorStoreManager:
    """Persistent ChromaDB vector store manager with user and document level isolation."""

    _client: Optional[chromadb.PersistentClient] = None

    @classmethod
    def get_client(cls) -> chromadb.PersistentClient:
        if cls._client is None:
            persist_dir = Path(settings.CHROMA_PERSIST_DIRECTORY)
            persist_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Initializing local persistent ChromaDB at {persist_dir.resolve()}")
            cls._client = chromadb.PersistentClient(path=str(persist_dir.resolve()))
        return cls._client

    @classmethod
    def get_collection(cls):
        client = cls.get_client()
        return client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )

    @classmethod
    def index_document_chunks(
        cls,
        user_id: int,
        document_id: int,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
    ) -> int:
        if not chunks:
            return 0

        collection = cls.get_collection()

        ids = [c["chunk_id"] for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        # Chroma requires metadata values to be str, int, float, or bool
        sanitized_metadatas = []
        for m in metadatas:
            sanitized = {
                "user_id": int(m["user_id"]),
                "document_id": int(m["document_id"]),
                "page_number": int(m["page_number"]),
                "chunk_index": int(m["chunk_index"]),
                "filename": str(m["filename"]),
                "char_count": int(m["char_count"]),
            }
            sanitized_metadatas.append(sanitized)

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=sanitized_metadatas,
        )

        logger.info(f"Indexed {len(ids)} chunks in ChromaDB for document id={document_id} (user_id={user_id})")
        return len(ids)

    @classmethod
    def delete_document_vectors(cls, user_id: int, document_id: int) -> int:
        collection = cls.get_collection()
        try:
            # Query IDs to delete
            existing = collection.get(
                where={"$and": [{"user_id": {"$eq": user_id}}, {"document_id": {"$eq": document_id}}]}
            )
            ids_to_delete = existing.get("ids", [])
            if ids_to_delete:
                collection.delete(ids=ids_to_delete)
                logger.info(f"Deleted {len(ids_to_delete)} vector records from ChromaDB for document id={document_id}")
            return len(ids_to_delete)
        except Exception as e:
            logger.warning(f"Error deleting document vectors from ChromaDB: {e}")
            return 0
