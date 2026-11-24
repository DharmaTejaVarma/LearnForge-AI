import re
from typing import List, Dict, Any, Optional
from app.ai.embeddings.embedding_service import EmbeddingService
from app.ai.rag.vector_store import VectorStoreManager
from app.core.sanitizer import EducationalSanitizer
from app.core.logging import logger

STOP_WORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "and", "or", "is",
    "are", "was", "were", "what", "how", "why", "who", "which", "explain",
    "tell", "me", "about", "can", "you", "does", "do", "did", "this", "that",
    "these", "those", "it", "with", "from", "as", "by", "an", "be"
}

class RAGRetriever:
    """Retrieves context chunks with exact page references, similarity scoring, and user/course scoping."""

    @staticmethod
    def retrieve(
        query: str,
        user_id: int,
        document_id: Optional[int] = None,
        document_ids: Optional[List[int]] = None,
        top_k: int = 4,
        min_similarity: float = 0.22,
    ) -> List[Dict[str, Any]]:
        collection = VectorStoreManager.get_collection()
        query_embedding = EmbeddingService.embed_query(query)

        # Build metadata filter enforcing user authorization and document/course scoping
        target_ids = []
        if document_ids:
            target_ids = [int(did) for did in document_ids if did]
        elif document_id is not None:
            target_ids = [int(document_id)]

        if len(target_ids) == 1:
            where_filter = {
                "$and": [
                    {"user_id": {"$eq": user_id}},
                    {"document_id": {"$eq": target_ids[0]}},
                ]
            }
        elif len(target_ids) > 1:
            where_filter = {
                "$and": [
                    {"user_id": {"$eq": user_id}},
                    {"document_id": {"$in": target_ids}},
                ]
            }
        else:
            # Fallback to all documents owned by user
            where_filter = {"user_id": {"$eq": user_id}}

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.warning(f"ChromaDB query error with filter {where_filter}: {e}")
            return []

        passages: List[Dict[str, Any]] = []

        if not results or not results.get("documents") or not results["documents"][0]:
            return []

        doc_texts = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for text, meta, dist in zip(doc_texts, metadatas, distances):
            similarity = round(max(0.0, 1.0 - dist), 4)

            # Sanitize text so LLM prompts and citations never receive header/footer metadata
            clean_passage_text = EducationalSanitizer.sanitize_educational_text(text)
            raw_filename = meta.get("filename", "")
            display_title = EducationalSanitizer.clean_title(raw_filename)

            # Evaluate relevance against query
            is_relevant = RAGRetriever.is_passage_relevant(query, clean_passage_text or text, similarity, min_similarity)

            if is_relevant:
                passages.append({
                    "text": clean_passage_text if clean_passage_text else text,
                    "document_id": meta.get("document_id"),
                    "filename": raw_filename,
                    "document_title": display_title,
                    "page_number": meta.get("page_number", 1),
                    "chunk_index": meta.get("chunk_index", 0),
                    "similarity_score": similarity,
                    "distance": round(dist, 4),
                    "is_relevant": True,
                })

        logger.info(f"Retrieved {len(passages)} relevant passages for user_id={user_id} (docs={target_ids})")
        return passages

    @staticmethod
    def get_chunks_for_pages(
        document_id: int,
        user_id: int,
        page_start: int,
        page_end: int,
        max_chunks: int = 12,
    ) -> List[Dict[str, Any]]:
        """
        Returns ChromaDB chunks for the given document within [page_start, page_end].
        Uses metadata filter and returns chunks ordered by chunk_index.
        Does NOT use similarity search — returns all chunks in the page range.
        """
        collection = VectorStoreManager.get_collection()
        where_filter = {
            "$and": [
                {"user_id": {"$eq": user_id}},
                {"document_id": {"$eq": document_id}},
                {"page_number": {"$gte": page_start}},
                {"page_number": {"$lte": page_end}},
            ]
        }
        try:
            results = collection.get(
                where=where_filter,
                include=["documents", "metadatas"],
                limit=max_chunks,
            )
        except Exception as e:
            logger.warning(f"get_chunks_for_pages error doc={document_id} pages={page_start}-{page_end}: {e}")
            return []

        if not results or not results.get("documents"):
            return []

        chunks = []
        for text, meta in zip(results["documents"], results["metadatas"]):
            clean_text = EducationalSanitizer.sanitize_educational_text(text) or text
            chunks.append({
                "text": clean_text,
                "document_id": meta.get("document_id"),
                "page_number": meta.get("page_number", page_start),
                "chunk_index": meta.get("chunk_index", 0),
                "similarity_score": 1.0,
                "is_relevant": True,
            })

        # Sort by page then chunk index for natural reading order
        chunks.sort(key=lambda c: (c["page_number"], c["chunk_index"]))
        logger.info(
            f"get_chunks_for_pages: {len(chunks)} chunks for doc={document_id} "
            f"user={user_id} pages={page_start}-{page_end}"
        )
        return chunks[:max_chunks]

    @staticmethod
    def is_passage_relevant(
        query: str,
        passage_text: str,
        similarity: float,
        min_similarity: float = 0.22,
    ) -> bool:
        """Evaluates whether retrieved passage is meaningfully relevant to the student query."""
        if similarity < min_similarity:
            return False

        # If similarity is sufficiently high, accept
        if similarity >= 0.40:
            return True

        # Extract content words from query (min 3 chars, not in stop words)
        words = re.findall(r"\b[a-zA-Z]{3,}\b", query.lower())
        content_words = [w for w in words if w not in STOP_WORDS]

        if not content_words:
            return similarity >= min_similarity

        # Check keyword matches in passage
        passage_lower = passage_text.lower()
        matches = sum(1 for w in content_words if w in passage_lower)

        # If at least 1 keyword matches and similarity meets threshold
        return matches >= 1 and similarity >= min_similarity
