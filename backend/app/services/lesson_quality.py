"""
Lesson Quality Gate for LearnForge AI Course Generation.

Validates generated lesson content against quality criteria before persisting.
"""
import re
from typing import List, Tuple
from app.ai.rag.text_cleaner import FORBIDDEN_PHRASES, has_hyphenation_artifacts


class LessonQualityGate:
    """
    Quality gate for AI-generated lessons.
    
    Checks:
    1. Required sections present (structural completeness)
    2. Word count within range (not too short / not bloated)
    3. No forbidden placeholder phrases
    4. No hyphenation artifacts from PDF extraction
    5. No raw filenames with extensions
    6. Verbatim shingle overlap < 25% (not copy-pasted from source)
    """

    MIN_WORDS = 200          # Must have at least 200 words
    MAX_WORDS = 2500         # Cap at 2500 words
    MAX_VERBATIM_SHINGLE_RATIO = 0.25
    SHINGLE_SIZE = 8         # 8-word n-gram overlap check

    REQUIRED_SECTIONS = [
        "## Learning Objectives",
        "## Introduction",
        "## Core Concepts",
        "## Key Takeaways",
        "## Check Your Understanding",
    ]

    # Fallback: also accept the older 10-section format from the original prompt
    LEGACY_SECTIONS = [
        "## 1.",
        "## 2.",
        "## 3.",
        "## 8. Key Takeaways",
        "## 9. Practice Review Questions",
    ]

    FILE_EXTENSION_RE = re.compile(r"\b\w+\.(pdf|docx|pptx|txt|md)\b", re.IGNORECASE)

    @classmethod
    def check(
        cls,
        lesson_content: str,
        source_text: str = "",
        subtopics: List[str] | None = None,
    ) -> Tuple[bool, List[str]]:
        """
        Returns (passed: bool, reasons: List[str]).
        
        'passed' is True only if ALL checks pass.
        'reasons' lists every failure reason (empty when passed).
        """
        reasons: List[str] = []

        # 1. Word count
        word_count = len(lesson_content.split())
        if word_count < cls.MIN_WORDS:
            reasons.append(f"Too short: {word_count} words (min {cls.MIN_WORDS})")
        if word_count > cls.MAX_WORDS:
            reasons.append(f"Too long: {word_count} words (max {cls.MAX_WORDS})")

        # 2. Required sections — accept either the new or the legacy section format
        has_new_sections = all(sec in lesson_content for sec in cls.REQUIRED_SECTIONS)
        has_legacy_sections = all(sec in lesson_content for sec in cls.LEGACY_SECTIONS)
        if not has_new_sections and not has_legacy_sections:
            missing = [s for s in cls.REQUIRED_SECTIONS if s not in lesson_content]
            reasons.append(f"Missing required sections: {missing}")

        # 3. Forbidden placeholder phrases
        lower = lesson_content.lower()
        found_forbidden = [ph for ph in FORBIDDEN_PHRASES if ph in lower]
        if found_forbidden:
            reasons.append(f"Forbidden phrases: {found_forbidden}")

        # 4. Hyphenation artifacts
        if has_hyphenation_artifacts(lesson_content):
            reasons.append("Contains hyphenation artifacts (e.g. 'deploy- ment')")

        # 5. Raw file extensions in lesson body
        ext_matches = cls.FILE_EXTENSION_RE.findall(lesson_content)
        if ext_matches:
            reasons.append(f"Raw file extensions found: {ext_matches}")

        # 6. Verbatim shingle overlap (only if source provided and long enough)
        if source_text and len(source_text.split()) > cls.SHINGLE_SIZE * 2:
            ratio = cls._shingle_overlap_ratio(lesson_content, source_text)
            if ratio > cls.MAX_VERBATIM_SHINGLE_RATIO:
                reasons.append(
                    f"Too much verbatim overlap with source: {ratio:.1%} (max {cls.MAX_VERBATIM_SHINGLE_RATIO:.0%})"
                )

        # 7. Subtopic coverage check (when source subtopics are specified)
        if subtopics:
            missing_subs = [
                s for s in subtopics
                if not any(tok in lower for tok in re.findall(r"[a-z0-9]{3,}", s.lower()))
            ]
            if len(missing_subs) > len(subtopics) // 2 and len(missing_subs) > 0:
                reasons.append(f"Missing coverage of source subtopics: {missing_subs}")

        passed = len(reasons) == 0
        return passed, reasons

    @classmethod
    def _shingle_overlap_ratio(cls, text_a: str, text_b: str) -> float:
        """Compute fraction of text_a's shingles that appear in text_b."""
        def shingles(text: str) -> set:
            words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
            return {" ".join(words[i : i + cls.SHINGLE_SIZE]) for i in range(len(words) - cls.SHINGLE_SIZE + 1)}

        shingles_a = shingles(text_a)
        if not shingles_a:
            return 0.0
        shingles_b = shingles(text_b)
        overlap = len(shingles_a & shingles_b)
        return overlap / len(shingles_a)
