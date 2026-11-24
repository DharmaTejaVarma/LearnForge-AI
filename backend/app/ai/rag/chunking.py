from typing import List, Dict, Any
from app.ai.rag.text_cleaner import TextCleaner

class ChunkingService:
    """Performs semantic and recursive token-aware chunking preserving paragraph boundaries and metadata."""

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 150):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_pages(
        self,
        pages: List[Dict[str, Any]],
        document_id: int,
        user_id: int,
        filename: str,
    ) -> List[Dict[str, Any]]:
        chunks: List[Dict[str, Any]] = []
        chunk_idx = 0

        for page in pages:
            page_num = page.get("page_number", 1)
            raw_text = page.get("text", "")
            cleaned = TextCleaner.clean(raw_text)

            if not cleaned:
                continue

            page_chunks = self._split_text(cleaned)
            for text_chunk in page_chunks:
                chunk_id = f"doc_{document_id}_p{page_num}_c{chunk_idx}"
                chunks.append({
                    "chunk_id": chunk_id,
                    "text": text_chunk,
                    "metadata": {
                        "chunk_id": chunk_id,
                        "document_id": document_id,
                        "user_id": user_id,
                        "page_number": page_num,
                        "filename": filename,
                        "chunk_index": chunk_idx,
                        "char_count": len(text_chunk),
                    }
                })
                chunk_idx += 1

        return chunks

    def _split_text(self, text: str) -> List[str]:
        if len(text) <= self.chunk_size:
            return [text]

        splits = text.split("\n\n")
        chunks = []
        current_chunk = ""

        for paragraph in splits:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            if len(current_chunk) + len(paragraph) + 2 <= self.chunk_size:
                current_chunk = f"{current_chunk}\n\n{paragraph}" if current_chunk else paragraph
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                
                # If paragraph itself is longer than chunk_size, split by sentences
                if len(paragraph) > self.chunk_size:
                    sentence_chunks = self._split_sentences(paragraph)
                    chunks.extend(sentence_chunks)
                    current_chunk = ""
                else:
                    current_chunk = paragraph

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        sentences = text.replace(". ", ".\n").split("\n")
        chunks = []
        curr = ""
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            if len(curr) + len(s) + 1 <= self.chunk_size:
                curr = f"{curr} {s}" if curr else s
            else:
                if curr:
                    chunks.append(curr)
                curr = s
        if curr:
            chunks.append(curr)
        return chunks
