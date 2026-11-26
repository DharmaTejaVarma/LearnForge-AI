import hashlib
import re
import time
from typing import List, Dict, Any, Optional, Tuple
from app.ai.embeddings.embedding_service import EmbeddingService
from app.ai.rag.vector_store import VectorStoreManager
from app.core.sanitizer import EducationalSanitizer
from app.core.logging import logger

# Bounded in-memory TTL cache for repeated semantic retrievals
_RETRIEVAL_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
_RETRIEVAL_CACHE_TTL = 600.0
_RETRIEVAL_CACHE_MAX = 256

STOP_WORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "and", "or", "is",
    "are", "was", "were", "what", "how", "why", "who", "which", "explain",
    "tell", "me", "about", "can", "you", "does", "do", "did", "this", "that",
    "these", "those", "it", "with", "from", "as", "by", "an", "be"
}

class RAGRetriever:
    """Retrieves context chunks with exact page references, similarity scoring, and user/course scoping."""

    @staticmethod
    def invalidate_cache() -> None:
        """Clear cached retrieval results (called on document deletion/reindexing)."""
        _RETRIEVAL_CACHE.clear()

    @staticmethod
    def retrieve(
        query: str,
        user_id: int,
        document_id: Optional[int] = None,
        document_ids: Optional[List[int]] = None,
        top_k: int = 4,
        min_similarity: float = 0.22,
    ) -> List[Dict[str, Any]]:
        cache_key = hashlib.sha256(
            f"{user_id}|{document_id}|{document_ids}|{top_k}|{min_similarity}|{query.strip().lower()}".encode("utf-8")
        ).hexdigest()[:24]
        now = time.monotonic()
        cached = _RETRIEVAL_CACHE.get(cache_key)
        if cached and (now - cached[0]) < _RETRIEVAL_CACHE_TTL:
            return [dict(item) for item in cached[1]]

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
            candidate_k = min(max(top_k * 2, top_k), 20)
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=candidate_k,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.warning(f"ChromaDB query error with filter {where_filter}: {e}")
            return []

        passages: List[Dict[str, Any]] = []
        seen_signatures = set()

        if not results or not results.get("documents") or not results["documents"][0]:
            return []

        doc_texts = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        query_terms = [
            w for w in re.findall(r"\b[a-zA-Z0-9]{3,}\b", query.lower())
            if w not in STOP_WORDS
        ]

        for text, meta, dist in zip(doc_texts, metadatas, distances):
            semantic_sim = max(0.0, 1.0 - dist)

            # Sanitize text so LLM prompts and citations never receive header/footer metadata
            clean_passage_text = EducationalSanitizer.sanitize_educational_text(text)
            effective_text = clean_passage_text if clean_passage_text else text
            raw_filename = meta.get("filename", "")
            display_title = EducationalSanitizer.clean_title(raw_filename)

            # Lexical keyword match ratio for hybrid ranking
            passage_lower = effective_text.lower()
            if query_terms:
                hits = sum(1 for term in query_terms if term in passage_lower)
                keyword_score = hits / len(query_terms)
            else:
                keyword_score = semantic_sim

            # Hybrid score blends semantic similarity and exact term overlap
            hybrid_score = round(min(1.0, 0.78 * semantic_sim + 0.22 * keyword_score), 4)
            best_score = round(max(semantic_sim, hybrid_score), 4)

            sig = re.sub(r"\s+", " ", passage_lower[:160])
            if sig in seen_signatures:
                continue

            # Evaluate relevance against query
            is_relevant = RAGRetriever.is_passage_relevant(query, effective_text, best_score, min_similarity)

            if is_relevant:
                seen_signatures.add(sig)
                passages.append({
                    "text": effective_text,
                    "document_id": meta.get("document_id"),
                    "filename": raw_filename,
                    "document_title": display_title,
                    "page_number": meta.get("page_number", 1),
                    "chapter": meta.get("chapter", ""),
                    "section": meta.get("section", ""),
                    "chunk_index": meta.get("chunk_index", 0),
                    "similarity_score": best_score,
                    "semantic_score": round(semantic_sim, 4),
                    "keyword_score": round(keyword_score, 4),
                    "distance": round(dist, 4),
                    "is_relevant": True,
                })

        passages.sort(key=lambda p: p["similarity_score"], reverse=True)
        passages = passages[:top_k]
        if len(_RETRIEVAL_CACHE) >= _RETRIEVAL_CACHE_MAX:
            _RETRIEVAL_CACHE.clear()
        _RETRIEVAL_CACHE[cache_key] = (now, [dict(item) for item in passages])
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
