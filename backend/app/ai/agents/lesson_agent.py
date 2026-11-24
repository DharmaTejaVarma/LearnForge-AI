"""
Lesson Generation Agent for LearnForge AI — Phase 5 rebuild.

Two-step generation:
  Step A (Extract): Local model extracts structured JSON notes from source chunks.
  Step B (Teach):   Cloud model writes the lesson in the teacher's own words.

No fallback template content. On failure → status="failed", content="".
"""
import json
import re
from typing import Dict, Any, List, Optional
from app.ai.models.model_router import model_router
from app.core.sanitizer import EducationalSanitizer
from app.core.logging import logger


class LessonAgent:
    """
    Generates clean, student-friendly lessons from page-scoped source chunks.
    Never copies verbatim text from the source or returns template filler.
    """

    @classmethod
    async def generate_lesson(
        cls,
        topic_title: str,
        chapter_title: str,
        course_title: str,
        passages: List[Dict[str, Any]],
        source_pages: List[int],
        doc_blueprint: Dict[str, Any],
        difficulty: str = "intermediate",
        page_start: Optional[int] = None,
        page_end: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Returns dict with keys: title, content, summary, key_takeaways, source_pages,
        generation_status ("ready" | "failed"), generation_error (str | None).
        """
        domain = doc_blueprint.get("subject_domain", "general")
        content_type = doc_blueprint.get("content_type", "theoretical")

        # Assemble source text from page-scoped chunks
        source_text = "\n\n".join(
            EducationalSanitizer.sanitize_educational_text(p["text"]) or p["text"]
            for p in passages
        ) if passages else ""

        pages_range = ""
        if page_start is not None and page_end is not None:
            pages_range = f"Pages {page_start}\u2013{page_end}"
        elif source_pages:
            pages_range = (
                f"Pages {min(source_pages)}\u2013{max(source_pages)}"
                if len(source_pages) > 1
                else f"Page {source_pages[0]}"
            )

        # --- Step A: Extract structured notes from source text (local model) ---
        notes_json = {}
        if source_text.strip():
            notes_json = await cls._extract_notes(source_text, topic_title, domain)

        # --- Step B: Write the lesson (cloud model) ---
        content, error = await cls._write_lesson(
            topic_title=topic_title,
            chapter_title=chapter_title,
            course_title=course_title,
            source_text=source_text,
            notes=notes_json,
            difficulty=difficulty,
            domain=domain,
            content_type=content_type,
            pages_range=pages_range,
        )

        if not content:
            return {
                "title": topic_title,
                "content": "",
                "summary": "",
                "key_takeaways": [],
                "source_pages": source_pages,
                "page_start": page_start,
                "page_end": page_end,
                "generation_status": "failed",
                "generation_error": error or "LLM returned empty content",
            }

        # Extract summary and key takeaways from generated content
        summary = cls._extract_summary(content, topic_title)
        takeaways = cls._extract_takeaways(content)

        return {
            "title": topic_title,
            "content": content,
            "summary": summary,
            "key_takeaways": takeaways,
            "source_pages": source_pages,
            "page_start": page_start,
            "page_end": page_end,
            "generation_status": "ready",
            "generation_error": None,
        }

    @classmethod
    async def _extract_notes(
        cls,
        source_text: str,
        topic_title: str,
        domain: str,
    ) -> Dict[str, Any]:
        """
        Step A: Ask local model to extract structured JSON notes from source.
        Returns parsed dict or empty dict on failure.
        """
        prompt = (
            f"You are a note-taking assistant. Extract key information about '{topic_title}' "
            f"from the following source text.\n\n"
            "Return ONLY a valid JSON object with these keys:\n"
            "{\n"
            '  "key_concepts": [{"term": "...", "explanation": "..."}],\n'
            '  "definitions": ["..."],\n'
            '  "important_points": ["..."],\n'
            '  "code_examples": [{"language": "...", "code": "...", "purpose": "..."}],\n'
            '  "prerequisites": ["..."]\n'
            "}\n\n"
            "If the source text is about something else or lacks relevant content, "
            "return an empty object: {}\n\n"
            f"Source text:\n{source_text[:2000]}"
        )
        try:
            res = await model_router.generate(
                prompt=prompt,
                task_type="extraction",
                temperature=0.1,
                format="json",
            )
            raw = res.get("content", "").strip()
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()
            return json.loads(raw) if raw else {}
        except Exception as e:
            logger.debug(f"Note extraction failed for '{topic_title}': {e}")
            return {}

    @classmethod
    async def _write_lesson(
        cls,
        topic_title: str,
        chapter_title: str,
        course_title: str,
        source_text: str,
        notes: Dict[str, Any],
        difficulty: str,
        domain: str,
        content_type: str,
        pages_range: str,
    ) -> tuple:
        """
        Step B: Write the full lesson using teacher voice (cloud model).
        Returns (content, error_message). Content is empty string on failure.
        """
        # Format extracted notes for the prompt
        notes_summary = ""
        if notes:
            concepts = notes.get("key_concepts", [])
            if concepts:
                notes_summary += "Key Concepts:\n" + "\n".join(
                    f"  - {c.get('term','')}: {c.get('explanation','')}" for c in concepts[:5]
                ) + "\n"
            defs = notes.get("definitions", [])
            if defs:
                notes_summary += "Definitions:\n" + "\n".join(f"  - {d}" for d in defs[:4]) + "\n"
            pts = notes.get("important_points", [])
            if pts:
                notes_summary += "Important Points:\n" + "\n".join(f"  - {p}" for p in pts[:5]) + "\n"

        # Domain-specific example guidance
        if domain == "computer_science" or content_type == "programming":
            example_guidance = (
                "In the Worked Example section, include a short, correct code snippet "
                "with a comment explaining each key line. Use Python unless the source specifies another language."
            )
        elif domain in ("mathematics", "engineering") or content_type == "mathematical":
            example_guidance = (
                "In the Worked Example section, show a step-by-step numerical calculation "
                "or formula derivation relevant to the topic."
            )
        else:
            example_guidance = (
                "In the Worked Example section, give a concrete real-world scenario "
                "that illustrates the concept in action."
            )

        system_message = (
            "You are an expert teacher writing a lesson for a student. "
            "Use ONLY the provided source material and extracted notes. "
            "Rewrite everything in your own clear words; never copy sentences verbatim. "
            "Do not mention 'the book', 'the author', 'this document', page numbers, "
            "or file names in the lesson body. Fix any broken formatting from PDF extraction. "
            "If the source lacks information on a section, write what you can from general knowledge "
            "in the same subject domain but do not invent facts. "
            "Use simple language first, then precise terminology. "
            "Include small concrete examples to aid understanding."
        )

        prompt = (
            f"Write a complete, student-friendly lesson on: **{topic_title}**\n"
            f"Course: {course_title} | Module: {chapter_title} | Level: {difficulty.title()}\n\n"
            "Use these EXACT markdown section headings (in this order):\n\n"
            f"# {topic_title}\n\n"
            "## Learning Objectives\n"
            "List 3-4 specific things the student will be able to do after this lesson.\n\n"
            "## Introduction\n"
            "Start with an engaging paragraph using a real-world analogy. "
            "Explain WHY this topic matters.\n\n"
            "## Core Concepts\n"
            "Explain the key ideas, definitions, and principles clearly. "
            "Use bold for important terms. Break complex ideas into digestible parts.\n\n"
            "## Worked Example\n"
            f"{example_guidance}\n\n"
            "## Common Mistakes\n"
            "List 2-3 frequent misunderstandings students have about this topic and how to avoid them.\n\n"
            "## Key Takeaways\n"
            "Bullet-point list of the 4-5 most important things to remember.\n\n"
            "## Check Your Understanding\n"
            "Write 2 short questions (with brief answers) to test comprehension.\n\n"
            "---\n\n"
            "RULES:\n"
            "- Write 400-800 words total.\n"
            "- Never use phrases like 'this book', 'the author', 'as mentioned', 'as described'.\n"
            "- Never include filenames like 'example.pdf' or 'notes.docx'.\n"
            "- Never copy sentences verbatim from the source.\n\n"
        )

        if notes_summary:
            prompt += f"Extracted Notes from Source:\n{notes_summary}\n\n"

        if source_text.strip():
            prompt += f"Source Material:\n{source_text[:3000]}"

        last_error = None
        for attempt in range(2):
            try:
                res = await model_router.generate(
                    prompt=prompt,
                    task_type="lesson_content",
                    temperature=0.4,
                    max_tokens=2000,
                    system_prompt=system_message,
                )
                content = res.get("content", "").strip()
                if content and len(content.split()) >= 150:
                    return content, None
                last_error = f"Content too short on attempt {attempt + 1}: {len(content.split())} words"
                logger.warning(f"Lesson generation attempt {attempt + 1} too short for '{topic_title}'")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Lesson generation attempt {attempt + 1} failed for '{topic_title}': {e}")

        return "", last_error

    @staticmethod
    def _extract_summary(content: str, topic_title: str) -> str:
        """Extract summary from Introduction section."""
        intro_match = re.search(r"## Introduction\n+(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if intro_match:
            intro = intro_match.group(1).strip()
            first_sentence = re.split(r"[.!?]\s", intro)[0]
            if len(first_sentence) > 30:
                return first_sentence.strip() + "."
        return f"A focused lesson on {topic_title} covering key concepts, examples, and practical takeaways."

    @staticmethod
    def _extract_takeaways(content: str) -> List[str]:
        """Extract bullet points from Key Takeaways section."""
        takeaways_match = re.search(
            r"## Key Takeaways\n+(.*?)(?=\n##|\Z)", content, re.DOTALL
        )
        if not takeaways_match:
            return []
        section = takeaways_match.group(1).strip()
        bullets = re.findall(r"[-*]\s+(.+)", section)
        return [b.strip() for b in bullets[:6] if len(b.strip()) > 10]
