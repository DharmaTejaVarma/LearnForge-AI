import re
from typing import Optional, List, Dict, Any

class EducationalSanitizer:
    """
    Centralized Sanitization and Quality Control Engine for LearnForge AI.
    Prevents leakage of internal filenames, filesystem paths, UUIDs, chunk IDs,
    and metadata into user-facing content (Courses, Lessons, Tutor, Flashcards, Quizzes).
    """

    # Patterns indicating raw filenames, metadata, and noise
    METADATA_PATTERNS = [
        re.compile(r"[\w\.-]+\.(?:pdf|docx|txt|py|html|json|md|csv)\b", re.IGNORECASE),
        re.compile(r"\bdoc_\d+_p\d+_c\d+\b", re.IGNORECASE),
        re.compile(r"\b(?:chunk[_\s-]*\d+|chunk_\w+)\b", re.IGNORECASE),
        re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE),
        re.compile(r"\b[0-9a-f]{32}\b", re.IGNORECASE),
        re.compile(r"\b(?:uploads[\\/]|chroma_data[\\/]|learnforge\.db)\b", re.IGNORECASE),
        re.compile(r"\b(?:nbsped|isbn(?:-1[03])?:?)\s*[\d-]+\b", re.IGNORECASE),
        re.compile(r"\b(?:http[s]?://(?:localhost|127\.0\.0\.1)[^\s]*)\b", re.IGNORECASE),
        re.compile(r"^page\s+\d+(\s+of\s+\d+)?$", re.IGNORECASE),
    ]

    @classmethod
    def clean_title(cls, raw: str, fallback_prefix: str = "Course") -> str:
        """
        Transforms messy filenames (e.g. '1nbsped-1098135504-9781098135508.pdf' or
        'CS101_Lecture_01_final.pdf') into clean, professional titles.
        """
        if not raw:
            return f"{fallback_prefix} Study Guide"

        # Strip file extension
        title = re.sub(r"\.(pdf|docx|txt|md)$", "", raw, flags=re.IGNORECASE).strip()

        # Check if the title is mostly random digits, ISBNs, or hash artifacts
        clean_check = re.sub(r"[\d\-_]", "", title)
        if len(clean_check) < 4 or re.match(r"^(?:nbsped|isbn|\d+)", title, re.IGNORECASE):
            return f"{fallback_prefix} Study Guide"

        # Replace underscores and hyphens with spaces
        title = re.sub(r"[-_]+", " ", title)

        # Remove repetitive prefixes like "Lecture", numbers at the very start
        title = re.sub(r"^\d+\s*", "", title)

        # Capitalize words neatly
        words = title.split()
        capitalized = [w.capitalize() if not w.isupper() else w for w in words]
        clean_result = " ".join(capitalized).strip()

        return clean_result if len(clean_result) > 3 else f"{fallback_prefix} Study Guide"

    @classmethod
    def contains_metadata_leak(cls, text: str) -> bool:
        """Checks if a string contains internal filenames, chunk IDs, or technical paths."""
        if not text:
            return False
        for pattern in cls.METADATA_PATTERNS:
            if pattern.search(text):
                return True
        return False

    @classmethod
    def sanitize_educational_text(cls, text: str) -> str:
        """
        Removes file paths, raw metadata IDs, and publisher noise from extracted text
        before presenting it to the user or sending it to LLM generation prompts.
        """
        if not text:
            return ""

        lines = text.split("\n")
        cleaned_lines = []

        for line in lines:
            stripped = line.strip()
            # Drop lines that are pure page numbers or metadata tags
            if re.match(r"^(?:page\s+\d+(\s+of\s+\d+)?|p\.\s*\d+|\d+\s*/\s*\d+|-\s*\d+\s*-)$", stripped, re.IGNORECASE):
                continue
            if re.match(r"^(?:isbn|copyright|all rights reserved|printed in|downloaded from)\b", stripped, re.IGNORECASE):
                continue
            if re.search(r"\[chunk\s+\d+", stripped, re.IGNORECASE):
                continue
            if re.search(r"\.(?:pdf|docx|tmp)\b", stripped, re.IGNORECASE) and len(stripped) < 80:
                continue
            if "nbsped-" in stripped.lower():
                continue

            cleaned_lines.append(line)

        result = "\n".join(cleaned_lines)
        # Collapse excessive whitespace
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result.strip()

    @classmethod
    def validate_flashcard(cls, front: str, back: str) -> bool:
        """
        Strict validation for flashcards. Rejects cards with metadata,
        meaningless single words, boilerplate templates, or file identifiers.
        """
        if not front or not back:
            return False

        front = front.strip()
        back = back.strip()

        # Length bounds
        if len(front) < 8 or len(front) > 300:
            return False
        if len(back) < 8 or len(back) > 1000:
            return False

        # Reject if either side contains metadata leakage
        if cls.contains_metadata_leak(front) or cls.contains_metadata_leak(back):
            return False

        # Reject template filler patterns
        filler_patterns = [
            r"^what is the significance of\s*:\s*\.{3}",
            r"^according to page\s+\d+\s*:",
            r"^concept\s+\d+\s*\?",
            r"^\d+\s*$",
        ]
        for pat in filler_patterns:
            if re.search(pat, front, re.IGNORECASE) or re.search(pat, back, re.IGNORECASE):
                return False

        return True

    @classmethod
    def validate_quiz_question(cls, q: Dict[str, Any]) -> bool:
        """
        Validates a multiple-choice question.
        Ensures exactly 4 valid options, correct answer presence, and zero metadata leakage.
        """
        if not isinstance(q, dict):
            return False

        q_text = str(q.get("question_text", "")).strip()
        options = q.get("options", [])
        correct = str(q.get("correct_answer", "")).strip()
        explanation = str(q.get("explanation", "")).strip()

        if len(q_text) < 15 or len(correct) < 1 or len(explanation) < 10:
            return False

        if not isinstance(options, list) or len(options) != 4:
            return False

        # Check options are non-empty and unique
        cleaned_options = [str(opt).strip() for opt in options if str(opt).strip()]
        if len(cleaned_options) != 4 or len(set(cleaned_options)) != 4:
            return False

        # Verify no metadata leakage in question or options
        if cls.contains_metadata_leak(q_text) or cls.contains_metadata_leak(explanation):
            return False
        for opt in cleaned_options:
            if cls.contains_metadata_leak(opt):
                return False

        # Verify correct answer matches one of the options
        # Handle cases where correct is 'A', 'B', 'C', 'D' or matches the option text
        valid_match = False
        letter_map = {"a": 0, "b": 1, "c": 2, "d": 3}
        clean_correct = correct.strip().lower()

        if clean_correct in letter_map:
            valid_match = True
        elif clean_correct.startswith(("a)", "b)", "c)", "d)")):
            valid_match = True
        else:
            for opt in cleaned_options:
                if clean_correct in opt.lower() or opt.lower() in clean_correct:
                    valid_match = True
                    break

        return valid_match
