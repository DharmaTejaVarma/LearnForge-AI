import re
import unicodedata
from typing import List, Dict, Any, Set


# Lines that should never be treated as running headers/footers
_CODE_PREFIXES = ("    ", "\t", "|", "def ", "class ", "#!", "//", "/*", "* ", ">>>")
_PAGE_NUMBER_RE = re.compile(r"^\s*(?:page\s+)?\d{1,4}\s*$", re.IGNORECASE)
_HYPHEN_LINE_BREAK_RE = re.compile(r"(\w)-[ ]?\n(\w)")          # deploy-\nment  or  deploy- \nment
_HYPHEN_INLINE_RE = re.compile(r"(\w)-[ ]+(\w)")                # deploy- ment (space-separated)
_REPEATED_WS_RE = re.compile(r"[ \t]{2,}")
_EXCESSIVE_NEWLINES_RE = re.compile(r"\n{3,}")
_LIGATURE_MAP = str.maketrans({
    "\ufb00": "ff",   # ﬀ
    "\ufb01": "fi",   # ﬁ
    "\ufb02": "fl",   # ﬂ
    "\ufb03": "ffi",  # ﬃ
    "\ufb04": "ffl",  # ﬄ
    "\u2019": "'",    # right single quotation mark
    "\u2018": "'",    # left single quotation mark
    "\u201c": '"',    # left double quotation mark
    "\u201d": '"',    # right double quotation mark
    "\u2013": "-",    # en dash
    "\u2014": "--",   # em dash
    "\u00a0": " ",    # non-breaking space
    "\u200b": "",     # zero-width space
    "\ufeff": "",     # BOM
})

# Forbidden boilerplate phrases that should trigger quality rejection
FORBIDDEN_PHRASES = frozenset([
    "key concepts relating to",
    "in-depth educational overview",
    "this lesson explores key concepts",
    "this lesson explores",
    "as detailed in",
    "the author",
    "this book",
    "in-depth educational overview covering",
    "deploy- ment",   # hyphenation artifact
])


class TextCleaner:
    """
    Normalizes and cleans raw extracted document text across formats.
    
    Handles:
    - Hyphenated line-break rejoining (deploy-\\nment → deployment)
    - Running header/footer detection and removal
    - Hard-wrap paragraph merging
    - Unicode normalization and ligature expansion (ﬁ → fi)
    - Smart quotes, em-dashes to ASCII
    - Code block preservation (indented or monospace)
    - Noise chunk filtering
    """

    @staticmethod
    def _is_code_line(line: str) -> bool:
        """Returns True if the line looks like it belongs inside a code block."""
        return any(line.startswith(p) for p in _CODE_PREFIXES)

    @staticmethod
    def _is_page_number(line: str) -> bool:
        return bool(_PAGE_NUMBER_RE.match(line.strip()))

    @staticmethod
    def _normalize_unicode(text: str) -> str:
        """NFC-normalize unicode and expand common ligatures."""
        text = text.translate(_LIGATURE_MAP)
        return unicodedata.normalize("NFC", text)

    @staticmethod
    def _fix_hyphenation(text: str) -> str:
        """
        Rejoin words broken across lines by hyphens.
        Handles:
            deploy-\\nment  → deployment
            deploy- ment   → deployment     (space-separated)
        """
        # Hard line-break with hyphen
        text = _HYPHEN_LINE_BREAK_RE.sub(r"\1\2", text)
        # Same-line space-hyphen artifact from bad PDF extraction
        text = _HYPHEN_INLINE_RE.sub(lambda m: m.group(1) + m.group(2)
                                     if m.group(1).isalpha() and m.group(2).isalpha()
                                     else m.group(0), text)
        return text

    @staticmethod
    def _merge_hard_wrapped_lines(text: str) -> str:
        """
        Merge hard-wrapped prose lines (single \\n) into paragraphs.
        A blank line (\\n\\n) is a real paragraph break — preserved.
        Code blocks (indented lines) are NOT reflowed.
        """
        lines = text.split("\n")
        result: List[str] = []
        in_code_block = False

        for i, line in enumerate(lines):
            # Track fenced code blocks ```
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                result.append(line)
                continue

            if in_code_block or TextCleaner._is_code_line(line):
                result.append(line)
                continue

            stripped = line.strip()

            if not stripped:
                # Blank line = paragraph separator
                result.append("")
                continue

            # If the previous non-empty "result" line is a prose line (not code,
            # not a heading, not a blank), merge by joining with a space
            if (result and result[-1] != "" and
                    not result[-1].startswith("#") and
                    not TextCleaner._is_code_line(result[-1]) and
                    not result[-1].strip().startswith("```") and
                    # Previous line doesn't end with a period-like boundary
                    not re.search(r"[.!?:]\s*$", result[-1])):
                result[-1] = result[-1].rstrip() + " " + stripped
            else:
                result.append(stripped)

        return "\n".join(result)

    @staticmethod
    def clean(text: str) -> str:
        """
        Full single-string cleaning pipeline.
        Order: unicode → hyphenation → line-merge → noise strip → whitespace collapse
        """
        if not text:
            return ""

        # 1. Normalize unicode & expand ligatures
        text = TextCleaner._normalize_unicode(text)

        # 2. Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # 3. Fix hyphenated line-breaks BEFORE merging (must come first)
        text = TextCleaner._fix_hyphenation(text)

        # 4. Merge hard-wrapped lines into paragraphs, preserving code blocks
        text = TextCleaner._merge_hard_wrapped_lines(text)

        # 5. Remove lines that are only page numbers
        lines = [l for l in text.split("\n") if not TextCleaner._is_page_number(l)]
        text = "\n".join(lines)

        # 6. Collapse repeated inline whitespace (but not leading indent on code)
        lines = []
        for line in text.split("\n"):
            if TextCleaner._is_code_line(line):
                lines.append(line.rstrip())
            else:
                lines.append(_REPEATED_WS_RE.sub(" ", line).strip())
        text = "\n".join(lines)

        # 7. Collapse excessive blank lines
        text = _EXCESSIVE_NEWLINES_RE.sub("\n\n", text)

        return text.strip()

    @classmethod
    def clean_document_pages(cls, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Cleans a list of page dicts, removing running headers/footers that
        appear on >= 35% of pages (or >= 3 pages for short docs).
        Returns cleaned page dicts with the same structure.
        """
        if not pages:
            return []

        # --- Detect running headers / footers ---
        line_occurrences: Dict[str, int] = {}
        for p in pages:
            seen_in_page: Set[str] = set()
            for line in p.get("text", "").split("\n"):
                s = line.strip()
                # Only track short non-code, non-structural lines
                if 3 < len(s) < 100 and s not in seen_in_page:
                    if not any(s.startswith(pfx) for pfx in _CODE_PREFIXES):
                        seen_in_page.add(s)
                        line_occurrences[s] = line_occurrences.get(s, 0) + 1

        num_pages = len(pages)
        threshold = max(3, int(num_pages * 0.35))
        repeated_headers: Set[str] = {
            line for line, count in line_occurrences.items()
            if count >= threshold
        }

        # --- Apply cleaning to each page ---
        cleaned_pages = []
        for p in pages:
            page_text = p.get("text", "")

            # Remove detected headers/footers line by line
            if repeated_headers:
                kept_lines = [
                    l for l in page_text.split("\n")
                    if l.strip() not in repeated_headers and not cls._is_page_number(l)
                ]
                page_text = "\n".join(kept_lines)

            cleaned_text = cls.clean(page_text)

            # Filter out noise chunks (too short or mostly non-alpha)
            if cls._is_noise(cleaned_text):
                cleaned_text = ""

            cleaned_pages.append({
                "page_number": p.get("page_number", 1),
                "text": cleaned_text,
                "char_count": len(cleaned_text),
                "headings": p.get("headings", []),
                "toc": p.get("toc", []),
            })

        return cleaned_pages

    @staticmethod
    def _is_noise(text: str) -> bool:
        """Returns True if the chunk is too short or predominantly non-alphabetic.
        
        Note: Only filter clearly noisy chunks (numbers-only, symbols-only, very tiny fragments).
        Do not filter short but meaningful text that survived header/footer removal.
        """
        stripped = text.strip()
        # Only filter extremely tiny fragments with no alphabetic content worth keeping
        if len(stripped) < 5:
            return True
        # Must have at least 30% alpha characters (filters pure-number / symbol chunks)
        alpha_chars = sum(1 for c in stripped if c.isalpha())
        if len(stripped) >= 10 and alpha_chars / max(len(stripped), 1) < 0.3:
            return True
        return False

    @staticmethod
    def contains_forbidden_phrases(text: str) -> List[str]:
        """Return a list of forbidden phrases found in text (for quality gate)."""
        lower = text.lower()
        return [phrase for phrase in FORBIDDEN_PHRASES if phrase in lower]

    @staticmethod
    def has_hyphenation_artifacts(text: str) -> bool:
        """Check whether unfixed hyphenation artifacts remain (e.g. 'deploy- ment')."""
        return bool(re.search(r"\b\w+-\s+\w", text))


# Module-level convenience functions
def contains_forbidden_phrases(text: str) -> List[str]:
    return TextCleaner.contains_forbidden_phrases(text)


def has_hyphenation_artifacts(text: str) -> bool:
    return TextCleaner.has_hyphenation_artifacts(text)

