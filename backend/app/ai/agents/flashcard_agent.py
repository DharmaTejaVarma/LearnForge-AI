import json
import re
from typing import List, Dict, Any, Optional
from app.ai.rag.retriever import RAGRetriever
from app.ai.models.model_router import model_router
from app.core.sanitizer import EducationalSanitizer
from app.core.logging import logger


class FlashcardAgent:
    """Generates high-impact, validated active-recall flashcards from course material."""

    @staticmethod
    async def generate_cards(
        user_id: int,
        document_id: Optional[int] = None,
        document_ids: Optional[List[int]] = None,
        count: int = 5,
        difficulty: str = "medium",
    ) -> List[Dict[str, str]]:
        # 1. Retrieve key passages via RAG (support both single doc and course-scoped multi-doc)
        passages = RAGRetriever.retrieve(
            query="Key definitions, core terminology, theoretical concepts, and principles",
            user_id=user_id,
            document_id=document_id,
            document_ids=document_ids,
            top_k=min(count + 3, 10),
        )

        # 2. Sanitize context to completely eliminate filenames, headers, and metadata
        clean_context = "\n\n".join(
            EducationalSanitizer.sanitize_educational_text(p["text"]) for p in passages
        )

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
            "5. Cards must be grounded in the provided reference text — do not invent topics.\n"
            "6. Respond ONLY with a valid JSON array matching this exact format:\n"
            '[\n'
            '  {"front": "What is a Python function?", "back": "A reusable block of code that performs a specific task, defined with the def keyword."},\n'
            '  {"front": "What is the purpose of a return statement?", "back": "It sends a computed result from a function back to the caller, ending function execution."}\n'
            ']\n\n'
            f"Course Material:\n{clean_context[:4000]}"
        )

        valid_cards: List[Dict[str, str]] = []
        try:
            res = await model_router.generate(
                prompt=prompt,
                task_type="flashcard",
                temperature=0.3,
                format="json"
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
                        if EducationalSanitizer.validate_flashcard(f_text, b_text):
                            valid_cards.append({"front": f_text, "back": b_text})
        except Exception as e:
            logger.warning(f"AI flashcard generation fallback: {e}")

        # 3. If AI produced fewer cards than requested, synthesize grounded, clean fallback cards
        if len(valid_cards) < count:
            fallback_cards = FlashcardAgent._generate_heuristic_cards(clean_context, count)
            for fc in fallback_cards:
                if len(valid_cards) >= count:
                    break
                if EducationalSanitizer.validate_flashcard(fc["front"], fc["back"]):
                    # Avoid duplicates
                    if not any(v["front"].lower() == fc["front"].lower() for v in valid_cards):
                        valid_cards.append(fc)

        # 4. Final safety guard if no cards could be extracted
        if not valid_cards:
            valid_cards = [
                {
                    "front": "What is the primary objective of active recall in learning?",
                    "back": "Active recall stimulates memory retention by retrieving information from memory during the testing process rather than passive review."
                },
                {
                    "front": "How do structured learning modules enhance knowledge retention?",
                    "back": "They sequence foundational definitions into progressive, practical applications, allowing students to build hierarchical understanding."
                }
            ]

        return valid_cards[:count]

    @staticmethod
    def _generate_heuristic_cards(text: str, target_count: int) -> List[Dict[str, str]]:
        """Synthesizes valid flashcards directly from conceptual text without metadata contamination."""
        cards = []
        sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 30]

        for s in sentences:
            match = re.search(r"\b([A-Z][a-zA-Z\s]{2,30})\s+(?:is defined as|is a|refers to|represents|means)\s+(.+)", s)
            if match:
                term = match.group(1).strip()
                definition = match.group(2).strip()
                if len(term) >= 3 and len(definition) >= 20:
                    cards.append({
                        "front": f"What is {term}?",
                        "back": f"{term} is {definition[:150]}."
                    })
            if len(cards) >= target_count:
                break

        return cards
