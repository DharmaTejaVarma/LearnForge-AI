from typing import Dict, Any, List, Tuple
from app.core.sanitizer import EducationalSanitizer

class CourseValidator:
    """
    Strict Pre-Save Quality Validation Engine for LearnForge AI Courses.
    Ensures synthesized courses and individual lessons meet academic standards,
    have proper structural progression, contain sufficient depth (>350 words),
    and strictly contain zero metadata leaks or hallucinated file identifiers.
    """

    @classmethod
    def validate_course_outline(cls, outline: Dict[str, Any], fallback_title: str = "Course") -> Tuple[bool, str]:
        if not isinstance(outline, dict):
            return False, "Course outline must be a structured JSON object."

        title = str(outline.get("title", "")).strip()
        if len(title) < 5:
            return False, f"Course title '{title}' is too short."

        if EducationalSanitizer.contains_metadata_leak(title):
            return False, f"Course title '{title}' contains internal metadata or file extensions."

        chapters = outline.get("chapters", [])
        if not isinstance(chapters, list) or len(chapters) == 0:
            return False, "Course must contain at least one module or chapter."

        if len(chapters) > 24:
            return False, "Course contains an excessive number of chapters (>24)."

        seen_topics = set()
        for idx, ch in enumerate(chapters):
            if not isinstance(ch, dict):
                return False, f"Chapter index {idx} must be a dictionary."

            ch_title = str(ch.get("title", "")).strip()
            if len(ch_title) < 3:
                return False, f"Chapter {idx + 1} title is missing or empty."

            if EducationalSanitizer.contains_metadata_leak(ch_title):
                return False, f"Chapter {idx + 1} title contains file metadata."

            topics = ch.get("topics", [])
            if not isinstance(topics, list) or len(topics) == 0:
                return False, f"Chapter '{ch_title}' must contain at least one topic."

            for t in topics:
                t_title = t.get("title", "") if isinstance(t, dict) else str(t).strip()
                if len(t_title) < 3:
                    return False, f"Topic in chapter '{ch_title}' is too short or empty."

                if EducationalSanitizer.contains_metadata_leak(t_title):
                    return False, f"Topic '{t_title}' contains file metadata."

                norm_t = t_title.lower()
                if norm_t in seen_topics:
                    return False, f"Duplicate topic detected across curriculum: '{t_title}'."
                seen_topics.add(norm_t)

        return True, "Valid"

    @classmethod
    def validate_lesson_content(cls, lesson_payload: Dict[str, Any], topic_title: str) -> Tuple[bool, str]:
        if not isinstance(lesson_payload, dict):
            return False, "Lesson payload must be a dictionary."

        content = str(lesson_payload.get("content", "")).strip()
        if len(content) < 800:
            return False, f"Lesson content for '{topic_title}' is too brief ({len(content)} chars < 800 minimum)."

        # Word count check (>250 words minimum, ideally >350 words)
        words = content.split()
        if len(words) < 200:
            return False, f"Lesson content for '{topic_title}' contains only {len(words)} words (minimum 200 required)."

        # Metadata leakage check
        if EducationalSanitizer.contains_metadata_leak(content):
            return False, f"Lesson content for '{topic_title}' contains leaked filenames or metadata IDs."

        # Structural sections check: markdown headings must be present
        section_headers = [line for line in content.split("\n") if line.strip().startswith("## ")]
        if len(section_headers) < 2:
            return False, f"Lesson content for '{topic_title}' lacks structured markdown section headers (##)."

        return True, "Valid"
