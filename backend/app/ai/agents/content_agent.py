"""
Content Agent for LearnForge AI — Phase 5 rebuild.

Builds course structure from document's real extracted structure (TOC/headings).
LLM is used ONLY to:
  - Write course description and learning objectives

Never invents generic "Foundational Principles" or "Advanced Synthesis" chapters
unless the document actually contains those concepts.
"""
import json
from typing import Dict, Any, List, Optional
from app.ai.models.model_router import model_router
from app.core.sanitizer import EducationalSanitizer
from app.core.logging import logger


class ContentAgent:
    """
    Builds course outlines grounded in the document's actual structure.
    """

    MAX_CHAPTERS = 8
    MAX_TOPICS_PER_CHAPTER = 4

    @classmethod
    async def synthesize_course_outline(
        cls,
        doc_blueprint: Dict[str, Any],
        target_chapters_count: int = 3,
        difficulty: str = "intermediate",
        sections: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Build a course outline.
        
        Priority:
        1. If 'sections' provided (from extract_structure()), use them directly.
        2. Otherwise fall back to doc_blueprint['detected_outline'].
        3. Use LLM to enrich description/objectives.
        """
        clean_title = doc_blueprint.get("clean_title", "Course Study Guide")
        domain = doc_blueprint.get("subject_domain", "general")

        structure_chapters = cls._build_chapters_from_sections(
            sections=sections or [],
            detected_outline=doc_blueprint.get("detected_outline", []),
            target_chapters_count=min(target_chapters_count, cls.MAX_CHAPTERS),
        )

        description, objectives = await cls._generate_meta(
            clean_title=clean_title,
            domain=domain,
            difficulty=difficulty,
            chapters=structure_chapters,
            overview_text=doc_blueprint.get("sample_overview_text", "")[:1500],
        )

        return {
            "title": clean_title,
            "description": description,
            "learning_objectives": objectives,
            "chapters": structure_chapters,
        }

    @classmethod
    def _build_chapters_from_sections(
        cls,
        sections: List[Dict[str, Any]],
        detected_outline: List[Dict[str, Any]],
        target_chapters_count: int,
    ) -> List[Dict[str, Any]]:
        chapters: List[Dict[str, Any]] = []

        if sections:
            chapters = cls._sections_to_chapters(sections, target_chapters_count)

        if not chapters and detected_outline:
            chapters = cls._outline_to_chapters(detected_outline, target_chapters_count)

        if not chapters:
            return [{
                "title": "Overview",
                "description": "Introduction and core concepts from the document.",
                "topics": [
                    {"title": "Key Concepts", "page_start": 1, "page_end": None},
                    {"title": "Practical Applications", "page_start": 1, "page_end": None},
                ],
                "page_start": 1,
                "page_end": None,
            }]

        return chapters

    @classmethod
    def _sections_to_chapters(
        cls,
        sections: List[Dict[str, Any]],
        max_chapters: int,
    ) -> List[Dict[str, Any]]:
        """Convert extract_structure() output into chapter dicts."""
        level1 = [s for s in sections if s.get("level", 1) <= 1][:max_chapters]
        level2 = [s for s in sections if s.get("level", 1) == 2]

        chapters = []
        for ch in level1:
            ch_title = EducationalSanitizer.clean_title(ch.get("title", ""))
            if not ch_title or len(ch_title) < 3:
                continue

            ch_page_start = ch.get("page_start", 1)
            ch_page_end = ch.get("page_end")

            topics = []
            if ch_page_end is not None:
                for s2 in level2:
                    s2_start = s2.get("page_start", 0)
                    if ch_page_start <= s2_start <= ch_page_end:
                        t_title = EducationalSanitizer.clean_title(s2.get("title", ""))
                        if t_title and len(t_title) > 2:
                            topics.append({
                                "title": t_title,
                                "page_start": s2.get("page_start"),
                                "page_end": s2.get("page_end"),
                            })
            topics = topics[: cls.MAX_TOPICS_PER_CHAPTER]

            if not topics:
                mid = None
                if ch_page_start is not None and ch_page_end is not None:
                    mid = (ch_page_start + ch_page_end) // 2
                topics = [
                    {"title": f"{ch_title}: Concepts", "page_start": ch_page_start, "page_end": mid or ch_page_end},
                    {"title": f"{ch_title}: Applications", "page_start": (mid + 1) if mid else ch_page_start, "page_end": ch_page_end},
                ]

            chapters.append({
                "title": ch_title,
                "description": f"Key concepts and applications covered in {ch_title}.",
                "topics": topics,
                "page_start": ch_page_start,
                "page_end": ch_page_end,
            })

        return chapters

    @classmethod
    def _outline_to_chapters(
        cls,
        detected_outline: List[Dict[str, Any]],
        max_chapters: int,
    ) -> List[Dict[str, Any]]:
        """Convert DocumentAgent detected_outline into chapter dicts (fallback)."""
        chapters = []
        for idx, ch in enumerate(detected_outline[:max_chapters]):
            ch_title = EducationalSanitizer.clean_title(ch.get("title", f"Module {idx + 1}"))
            if not ch_title or len(ch_title) < 3:
                continue

            raw_topics = ch.get("topics", [])
            topics = []
            for t in raw_topics:
                t_name = t.get("title", "") if isinstance(t, dict) else str(t)
                t_clean = EducationalSanitizer.clean_title(t_name)
                if t_clean and len(t_clean) > 2:
                    topics.append({
                        "title": t_clean,
                        "page_start": t.get("page_start") if isinstance(t, dict) else None,
                        "page_end": t.get("page_end") if isinstance(t, dict) else None,
                    })

            if not topics:
                start_page = ch.get("start_page", 1)
                topics = [
                    {"title": f"{ch_title}: Concepts", "page_start": start_page, "page_end": None},
                    {"title": f"{ch_title}: Applications", "page_start": start_page, "page_end": None},
                ]

            chapters.append({
                "title": ch_title,
                "description": f"Core principles and practical applications of {ch_title}.",
                "topics": topics[: cls.MAX_TOPICS_PER_CHAPTER],
                "page_start": ch.get("start_page", 1),
                "page_end": ch.get("end_page"),
            })

        return chapters

    @classmethod
    async def _generate_meta(
        cls,
        clean_title: str,
        domain: str,
        difficulty: str,
        chapters: List[Dict[str, Any]],
        overview_text: str,
    ) -> tuple:
        """Use LLM to write course description and learning objectives."""
        chapter_titles = "\n".join(f"- {c['title']}" for c in chapters)
        prompt = (
            f"You are writing course metadata for a course titled '{clean_title}'.\n"
            f"Subject domain: {domain.replace('_', ' ').title()}\n"
            f"Difficulty: {difficulty.title()}\n"
            f"Chapters:\n{chapter_titles}\n\n"
            "Write a JSON object with:\n"
            "{\n"
            '  "description": "2-3 sentence academic overview of what this course teaches",\n'
            '  "learning_objectives": ["Objective 1", "Objective 2", "Objective 3"]\n'
            "}\n\n"
            "Objectives should be specific and start with action verbs.\n"
            f"Document excerpt:\n{overview_text[:800]}"
        )

        try:
            res = await model_router.generate(
                prompt=prompt,
                task_type="course_outline",
                temperature=0.3,
                format="json",
            )
            raw = res.get("content", "").strip()
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()
            parsed = json.loads(raw)
            desc = parsed.get("description", "")
            objs = parsed.get("learning_objectives", [])
            if desc and objs:
                return desc, objs[:5]
        except Exception as e:
            logger.debug(f"Meta generation failed for '{clean_title}': {e}")

        domain_label = domain.replace("_", " ").title()
        return (
            f"A {difficulty.lower()}-level course on {clean_title} covering {domain_label} "
            f"concepts across {len(chapters)} modules.",
            [
                f"Understand the core concepts and terminology of {clean_title}",
                "Apply the key methods and frameworks to practical problems",
                f"Analyze and evaluate {domain_label.lower()} systems and outcomes",
            ],
        )
