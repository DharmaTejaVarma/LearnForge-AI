import hashlib
import re
from typing import List, Dict, Any, Set
from app.ai.rag.text_cleaner import TextCleaner


class ChunkingService:
    """
    Structure-aware token/character chunking preserving:
    - Paragraph boundaries and fenced code/table blocks
    - Sliding-window overlap across consecutive chunks
    - Chapter / section headings and page numbers in metadata
    - Chunk deduplication across identical fragments
    """

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 150):
        self.chunk_size = max(100, int(chunk_size))
        self.chunk_overlap = max(0, min(int(chunk_overlap), self.chunk_size // 2))

    def chunk_pages(
        self,
        pages: List[Dict[str, Any]],
        document_id: int,
        user_id: int,
        filename: str,
    ) -> List[Dict[str, Any]]:
        chunks: List[Dict[str, Any]] = []
        seen_hashes: Set[str] = set()
        chunk_idx = 0
        active_chapter = ""
        active_section = ""

        for page in pages:
            page_num = page.get("page_number", 1)
            printed_page = str(page.get("printed_page") or page_num)
            raw_text = page.get("text", "")
            cleaned = TextCleaner.clean(raw_text)

            # Track structural headings across page boundaries
            for toc_entry in page.get("toc", []) or []:
                title = str(toc_entry.get("title", "")).strip()
                lvl = toc_entry.get("level", 1)
                if title:
                    if lvl == 1:
                        active_chapter = title[:140]
                    else:
                        active_section = title[:140]

            page_headings = [str(h).strip() for h in (page.get("headings") or []) if str(h).strip()]
            if page_headings:
                first_h = page_headings[0]
                if re.match(r"^(?:chapter|module|part|unit)\b", first_h, re.IGNORECASE) or not active_chapter:
                    active_chapter = first_h[:140]
                active_section = page_headings[-1][:140]

            if not cleaned:
                continue

            page_chunks = self._split_text(cleaned)
            for text_chunk in page_chunks:
                norm_key = re.sub(r"\s+", " ", text_chunk.strip().lower())
                c_hash = hashlib.sha256(norm_key.encode("utf-8")).hexdigest()[:24]
                if c_hash in seen_hashes:
                    continue
                seen_hashes.add(c_hash)

                chunk_id = f"doc_{document_id}_p{page_num}_c{chunk_idx}"
                chunks.append({
                    "chunk_id": chunk_id,
                    "text": text_chunk,
                    "metadata": {
                        "chunk_id": chunk_id,
                        "document_id": document_id,
                        "user_id": user_id,
                        "page_number": page_num,
                        "printed_page": printed_page,
                        "filename": filename,
                        "chapter": active_chapter,
                        "section": active_section,
                        "chunk_index": chunk_idx,
                        "char_count": len(text_chunk),
                        "chunk_hash": c_hash,
                    },
                })
                chunk_idx += 1

        return chunks

    @staticmethod
    def _group_atomic_blocks(text: str) -> List[str]:
        """Group fenced code blocks and markdown tables so they are not broken mid-block."""
        lines = text.split("\n")
        blocks: List[str] = []
        buf: List[str] = []
        in_code = False

        def flush_buf():
            if buf:
                block_text = "\n".join(buf).strip()
                if block_text:
                    blocks.append(block_text)
                buf.clear()

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                if not in_code:
                    flush_buf()
                    in_code = True
                    buf.append(line)
                else:
                    buf.append(line)
                    in_code = False
                    flush_buf()
                continue

            if in_code:
                buf.append(line)
            elif stripped == "":
                flush_buf()
            else:
                buf.append(line)

        flush_buf()
        return blocks

    def _apply_overlap(self, chunks: List[str]) -> List[str]:
        """Carry a clean sentence/word tail of up to chunk_overlap characters into the next chunk."""
        if self.chunk_overlap <= 0 or len(chunks) <= 1:
            return chunks

        overlapped = [chunks[0]]
        for idx in range(1, len(chunks)):
            prev_text = chunks[idx - 1]
            curr_text = chunks[idx]
            if len(prev_text) <= self.chunk_overlap:
                tail = prev_text
            else:
                raw_tail = prev_text[-self.chunk_overlap :]
                # Snap overlap start to a clean word boundary
                space_idx = raw_tail.find(" ")
                tail = raw_tail[space_idx + 1 :].strip() if space_idx > 0 else raw_tail.strip()

            if tail and not curr_text.startswith(tail) and len(tail) + len(curr_text) + 2 <= int(self.chunk_size * 1.25):
                overlapped.append(f"{tail}\n{curr_text}")
            else:
                overlapped.append(curr_text)
        return overlapped

    def _split_text(self, text: str) -> List[str]:
        if len(text) <= self.chunk_size:
            return [text]

        blocks = self._group_atomic_blocks(text)
        if not blocks:
            return []

        chunks: List[str] = []
        current_chunk = ""

        for block in blocks:
            if len(current_chunk) + len(block) + 2 <= self.chunk_size:
                current_chunk = f"{current_chunk}\n\n{block}" if current_chunk else block
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""

                # Preserve intact code/table blocks up to 1.5x chunk_size
                if (block.startswith("```") or block.startswith("|")) and len(block) <= int(self.chunk_size * 1.5):
                    chunks.append(block)
                elif len(block) > self.chunk_size:
                    chunks.extend(self._split_sentences(block))
                else:
                    current_chunk = block

        if current_chunk:
            chunks.append(current_chunk)

        return self._apply_overlap(chunks)

    def _split_sentences(self, text: str) -> List[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks: List[str] = []
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
                if len(s) > self.chunk_size:
                    # Hard wrap overly long single sentence/code line cleanly
                    for start in range(0, len(s), self.chunk_size):
                        chunks.append(s[start : start + self.chunk_size])
                    curr = ""
                else:
                    curr = s
        if curr:
            chunks.append(curr)
        return chunks
