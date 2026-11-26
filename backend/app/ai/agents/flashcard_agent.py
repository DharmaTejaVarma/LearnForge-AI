import asyncio
import json
import re
from typing import List, Dict, Optional, Set
from app.ai.rag.retriever import RAGRetriever
from app.ai.models.model_router import model_router
from app.core.sanitizer import EducationalSanitizer
from app.core.logging import logger


class FlashcardAgent:
    """Generates high-impact, deduplicated active-recall flashcards grounded in course material."""

    @staticmethod
    def _norm_front(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()

    @staticmethod
    async def generate_cards(
        user_id: int,
        document_id: Optional[int] = None,
        document_ids: Optional[List[int]] = None,
        count: int = 5,
        difficulty: str = "medium",
        existing_fronts: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        # 1. Retrieve key passages via RAG (offloaded so embedding/Chroma never blocks event loop)
        passages = await asyncio.to_thread(
            RAGRetriever.retrieve,
            query="Key definitions, core terminology, theoretical concepts, and principles",
            user_id=user_id,
            document_id=document_id,
            document_ids=document_ids,
            top_k=min(count + 4, 12),
        )
        # If semantic meta-query didn't match literal document vocabulary, sample document pages directly
        if not passages:
            target_id = document_id or (document_ids[0] if document_ids else None)
            if target_id:
                passages = await asyncio.to_thread(
                    RAGRetriever.get_chunks_for_pages,
                    document_id=target_id,
                    user_id=user_id,
                    page_start=1,
                    page_end=25,
                    max_chunks=min(count + 4, 12),
                )

        # 2. Sanitize context to eliminate filenames, headers, and metadata
        clean_context = "\n\n".join(
            EducationalSanitizer.sanitize_educational_text(p["text"]) for p in passages
        ).strip()
        if not clean_context:
            return []

        seen_fronts: Set[str] = {FlashcardAgent._norm_front(f) for f in (existing_fronts or []) if f}

        difficulty_guidance = {
            "easy": "Focus on straightforward definitions, key terms, and factual recall. Keep answers concise.",
            "medium": "Test understanding of concepts, relationships between ideas, and practical applications.",
            "hard": "Challenge synthesis of multiple concepts, edge cases, comparisons, and nuanced distinctions.",
        }.get(difficulty, "Test understanding of concepts and practical applications.")

        prompt = (
            f"You are an expert educator creating an active-recall flashcard study deck ({difficulty} level).\n"
            f"Generate exactly {count} distinct, high-impact flashcards from the following course material.\n"
            f"Difficulty guidance: {difficulty_guidance}\n\n"
            "STRICT RULES:\n"
            "1. Each card MUST have a clear, specific question or term on the front.\n"
            "2. The back MUST contain a concise, precise, and accurate explanation or definition (1-3 sentences).\n"
            "3. NEVER mention filenames, extensions (e.g. .pdf, .docx), chunk IDs, page numbers, or internal metadata.\n"
            "4. NEVER generate cards with vague templates like 'What is the significance of: ...?'.\n"
            "5. Cards must be grounded strictly in the provided reference text — do not invent topics.\n"
            "6. Respond ONLY with a valid JSON array matching this exact format:\n"
            '[\n'
            '  {"front": "What is a Python function?", "back": "A reusable block of code that performs a specific task, defined with the def keyword."},\n'
            '  {"front": "What is the purpose of a return statement?", "back": "It sends a computed result from a function back to the caller, ending function execution."}\n'
            ']\n\n'
            f"Course Material:\n{clean_context[:3500]}"
        )

        valid_cards: List[Dict[str, str]] = []
        try:
            res = await model_router.generate(
                prompt=prompt,
                task_type="flashcard",
                temperature=0.3,
                format="json",
            )
            content = res.get("content", "").strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            parsed = json.loads(content)
            if isinstance(parsed, list):
                for card in parsed:
                    if isinstance(card, dict) and "front" in card and "back" in card:
                        f_text = str(card["front"]).strip()
                        b_text = str(card["back"]).strip()
                        norm_f = FlashcardAgent._norm_front(f_text)
                        if norm_f and norm_f not in seen_fronts and EducationalSanitizer.validate_flashcard(f_text, b_text):
                            seen_fronts.add(norm_f)
                            valid_cards.append({"front": f_text, "back": b_text, "difficulty": difficulty})
        except Exception as e:
            logger.warning(f"AI flashcard generation fallback: {e}")

        # 3. Synthesize grounded cards directly from retrieved passages when LLM returns fewer cards
        if len(valid_cards) < count:
            fallback_cards = FlashcardAgent._generate_heuristic_cards(clean_context, count - len(valid_cards) + 3)
            for fc in fallback_cards:
                if len(valid_cards) >= count:
                    break
                norm_f = FlashcardAgent._norm_front(fc["front"])
                if norm_f and norm_f not in seen_fronts and EducationalSanitizer.validate_flashcard(fc["front"], fc["back"]):
                    seen_fronts.add(norm_f)
                    valid_cards.append({**fc, "difficulty": difficulty})

        return valid_cards[:count]

    @staticmethod
    def _generate_heuristic_cards(text: str, target_count: int) -> List[Dict[str, str]]:
        """Synthesizes grounded flashcards directly from retrieved document sentences without fabricating unrelated topics."""
        cards: List[Dict[str, str]] = []
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 25]

        def_re = re.compile(
            r"\b([A-Za-z][A-Za-z0-9\s\(\)\-]{2,42}?)\s+(?:is defined as|is an|is the|is a|are|refers to|represents|means|enables|manages|provides)\s+(.+)",
            re.IGNORECASE,
        )
        for s in sentences:
            match = def_re.search(s)
            if match:
                term = match.group(1).strip(" :,-")
                definition = match.group(2).strip()
                if len(term) >= 3 and len(definition) >= 15 and not EducationalSanitizer.contains_metadata_leak(term):
                    cards.append({
                        "front": f"How does your study material explain {term}?",
                        "back": f"{term} {match.group(0)[len(match.group(1)):].strip()[:220]}",
                    })
            if len(cards) >= target_count:
                break

        # If sentences lacked classic 'is a' phrasing, extract concise grounded comprehension cards
        if len(cards) < target_count:
            for idx, s in enumerate(sentences):
                words = [w for w in re.findall(r"\b[A-Za-z][A-Za-z0-9\-]{3,}\b", s)]
                if len(words) >= 5 and len(s) >= 35:
                    topic_phrase = " ".join(words[:3])
                    cards.append({
                        "front": f"What key point is stated regarding {topic_phrase}?",
                        "back": s[:240],
                    })
                if len(cards) >= target_count:
                    break

        return cards
