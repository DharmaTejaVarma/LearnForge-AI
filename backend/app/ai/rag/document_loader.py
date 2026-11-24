import io
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.core.exceptions import BadRequestException
from app.core.logging import logger

class DocumentLoader:
    """
    Universal Document Extraction Engine for LearnForge AI.
    Extracts text, structural hierarchy, headings, tables, code blocks,
    and page-level metadata from PDF, DOCX, TXT, PPTX, and Markdown documents.
    Supports scanned PDF OCR fallback and handles corrupted/empty files gracefully.
    """

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".pptx", ".md", ".markdown"}

    @staticmethod
    def detect_format(file_path: str, mime_type: Optional[str] = None) -> str:
        """Determines the document format using file extension and content inspection."""
        ext = Path(file_path).suffix.lower()
        if ext in DocumentLoader.SUPPORTED_EXTENSIONS:
            return ext

        mime = (mime_type or "").lower()
        if "pdf" in mime:
            return ".pdf"
        elif "word" in mime or "docx" in mime:
            return ".docx"
        elif "presentation" in mime or "powerpoint" in mime or "pptx" in mime:
            return ".pptx"
        elif "markdown" in mime or "md" in mime:
            return ".md"
        elif "text" in mime or "plain" in mime:
            return ".txt"

        raise BadRequestException(
            f"Unsupported document format '{ext or mime}'. Supported formats are: PDF, DOCX, TXT, PPTX, and Markdown."
        )

    # -------------------------------------------------------------------------
    # 1. PDF Extraction (PyMuPDF with Layout, TOC, and OCR Fallback)
    # -------------------------------------------------------------------------
    @staticmethod
    def extract_pdf(file_path: str) -> List[Dict[str, Any]]:
        import pymupdf

        path = Path(file_path)
        if not path.exists():
            raise BadRequestException(f"Document file does not exist: {path.name}")

        file_size = path.stat().st_size
        if file_size < 10:
            raise BadRequestException("The uploaded PDF file is empty or corrupted.")

        pages: List[Dict[str, Any]] = []
        try:
            doc = pymupdf.open(str(path))
        except Exception as e:
            logger.error(f"PyMuPDF open error for {path.name}: {e}")
            raise BadRequestException(
                f"Unable to read '{path.name}'. The PDF file may be corrupted or password-protected."
            )

        try:
            # Check for embedded PDF Table of Contents
            doc_toc = doc.get_toc()  # [[lvl, title, page], ...]
            toc_entries = []
            if doc_toc:
                for item in doc_toc:
                    if len(item) >= 3:
                        toc_entries.append({"level": item[0], "title": str(item[1]).strip(), "page": item[2]})

            total_text = ""
            for idx in range(len(doc)):
                page_num = idx + 1
                page = doc[idx]

                # Extract text using block extraction to preserve layout
                text = ""
                headings: List[str] = []
                try:
                    blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)
                    # Sort blocks vertically, then horizontally
                    sorted_blocks = sorted(blocks, key=lambda b: (b[1], b[0]))
                    block_texts = []
                    for b in sorted_blocks:
                        if b[6] == 0:  # text block
                            b_text = b[4].strip()
                            if b_text:
                                # Check if block appears to be a heading (short line, capitalized or numbered)
                                if len(b_text) < 90 and "\n" not in b_text and re.match(r"^(?:chapter|\d+\.|\d+\s+|module|[A-Z\s]{4,})", b_text, re.IGNORECASE):
                                    headings.append(b_text)
                                block_texts.append(b_text)
                    text = "\n\n".join(block_texts)
                except Exception:
                    text = page.get_text()

                # Scanned page check: if text is empty or very sparse (< 25 chars) and page has images, attempt OCR
                if len(text.strip()) < 25 and len(page.get_images()) > 0:
                    try:
                        # Attempt PyMuPDF OCR (requires Tesseract language support if installed)
                        tp = page.get_textpage_ocr(flags=0, dpi=150, full=True)
                        ocr_result = page.get_text(textpage=tp)
                        if len(ocr_result.strip()) > len(text.strip()):
                            text = ocr_result
                    except Exception as ocr_err:
                        logger.debug(f"OCR fallback not available for page {page_num}: {ocr_err}")

                pages.append({
                    "page_number": page_num,
                    "text": text,
                    "char_count": len(text),
                    "headings": headings,
                    "toc": [e for e in toc_entries if e["page"] == page_num]
                })
                total_text += text

            doc.close()

            if len(total_text.strip()) < 20:
                raise BadRequestException(
                    f"'{path.name}' appears to be a scanned image or empty document without selectable text. "
                    "Please upload a document with readable text or searchable OCR."
                )

            return pages
        except BadRequestException:
            raise
        except Exception as e:
            logger.error(f"Error extracting text from PDF '{path.name}': {e}")
            raise BadRequestException(f"Failed to process PDF '{path.name}': {str(e)}")

    # -------------------------------------------------------------------------
    # 2. DOCX Extraction (python-docx with Heading & Table Structuring)
    # -------------------------------------------------------------------------
    @staticmethod
    def extract_docx(file_path: str) -> List[Dict[str, Any]]:
        import docx

        path = Path(file_path)
        if not path.exists():
            raise BadRequestException(f"Document file does not exist: {path.name}")

        try:
            doc = docx.Document(str(path))
        except Exception as e:
            logger.error(f"python-docx open error for {path.name}: {e}")
            raise BadRequestException(
                f"Unable to read '{path.name}'. The Word document appears to be corrupted or invalid."
            )

        elements: List[str] = []
        headings: List[str] = []

        try:
            for p in doc.paragraphs:
                text = p.text.strip()
                if not text:
                    continue

                style_name = (p.style.name if p.style else "").lower()
                if "heading 1" in style_name:
                    elements.append(f"\n# {text}\n")
                    headings.append(text)
                elif "heading 2" in style_name:
                    elements.append(f"\n## {text}\n")
                    headings.append(text)
                elif "heading 3" in style_name:
                    elements.append(f"\n### {text}\n")
                    headings.append(text)
                elif "list" in style_name or "bullet" in style_name:
                    elements.append(f"- {text}")
                else:
                    elements.append(text)

            # Extract tables as formatted Markdown tables
            for table in doc.tables:
                rows_text = []
                for r_idx, row in enumerate(table.rows):
                    cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                    if any(cells):
                        rows_text.append("| " + " | ".join(cells) + " |")
                        if r_idx == 0:
                            rows_text.append("| " + " | ".join(["---"] * len(cells)) + " |")
                if rows_text:
                    elements.append("\n" + "\n".join(rows_text) + "\n")

            full_text = "\n\n".join(elements).strip()
            if len(full_text) < 15:
                raise BadRequestException(f"The Word document '{path.name}' contains no readable text.")

            # Partition long DOCX into logical pages (~2500 characters) preserving paragraph boundaries
            return DocumentLoader._paginate_text(full_text, headings=headings, page_char_limit=2500)
        except BadRequestException:
            raise
        except Exception as e:
            logger.error(f"Error parsing DOCX '{path.name}': {e}")
            raise BadRequestException(f"Failed to extract content from DOCX '{path.name}': {str(e)}")

    # -------------------------------------------------------------------------
    # 3. PPTX Presentation Extraction (python-pptx Slide-by-Slide)
    # -------------------------------------------------------------------------
    @staticmethod
    def extract_pptx(file_path: str) -> List[Dict[str, Any]]:
        try:
            from pptx import Presentation
        except ImportError:
            raise BadRequestException("PPTX presentation support is not installed.")

        path = Path(file_path)
        if not path.exists():
            raise BadRequestException(f"Presentation file does not exist: {path.name}")

        try:
            prs = Presentation(str(path))
        except Exception as e:
            logger.error(f"python-pptx open error for {path.name}: {e}")
            raise BadRequestException(
                f"Unable to read '{path.name}'. The presentation file may be corrupted or invalid."
            )

        pages: List[Dict[str, Any]] = []
        total_text = ""

        try:
            for idx, slide in enumerate(prs.slides):
                slide_num = idx + 1
                slide_lines = []
                headings: List[str] = []

                # Slide Title
                if slide.shapes.title and slide.shapes.title.text.strip():
                    title_text = slide.shapes.title.text.strip()
                    slide_lines.append(f"# Slide {slide_num}: {title_text}\n")
                    headings.append(title_text)

                # Shapes, text frames, and tables
                for shape in slide.shapes:
                    if shape == slide.shapes.title:
                        continue
                    if shape.has_text_frame:
                        for paragraph in shape.text_frame.paragraphs:
                            p_text = paragraph.text.strip()
                            if p_text:
                                level = paragraph.level or 0
                                indent = "  " * level
                                slide_lines.append(f"{indent}- {p_text}")
                    elif shape.has_table:
                        table = shape.table
                        for r_idx, row in enumerate(table.rows):
                            cells = [c.text.strip().replace("\n", " ") for c in row.cells]
                            if any(cells):
                                slide_lines.append("| " + " | ".join(cells) + " |")
                                if r_idx == 0:
                                    slide_lines.append("| " + " | ".join(["---"] * len(cells)) + " |")

                # Speaker notes if present
                try:
                    if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                        notes = slide.notes_slide.notes_text_frame.text.strip()
                        if notes:
                            slide_lines.append(f"\n*Speaker Notes:*\n{notes}")
                except Exception:
                    pass

                slide_text = "\n".join(slide_lines).strip()
                if not slide_text:
                    slide_text = f"Slide {slide_num} (Visual Diagram or Graphic)"

                pages.append({
                    "page_number": slide_num,
                    "text": slide_text,
                    "char_count": len(slide_text),
                    "headings": headings,
                })
                total_text += slide_text

            if len(total_text.strip()) < 15:
                raise BadRequestException(f"The presentation '{path.name}' contains no readable text.")

            return pages
        except BadRequestException:
            raise
        except Exception as e:
            logger.error(f"Error extracting PPTX '{path.name}': {e}")
            raise BadRequestException(f"Failed to extract content from presentation '{path.name}': {str(e)}")

    # -------------------------------------------------------------------------
    # 4. Plain Text (.txt) Extraction
    # -------------------------------------------------------------------------
    @staticmethod
    def extract_txt(file_path: str) -> List[Dict[str, Any]]:
        path = Path(file_path)
        if not path.exists():
            raise BadRequestException(f"Text file does not exist: {path.name}")

        content = None
        for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
            try:
                content = path.read_text(encoding=enc)
                break
            except (UnicodeDecodeError, Exception):
                continue

        if content is None:
            raise BadRequestException(f"Unable to decode text file '{path.name}'. Please save in UTF-8 format.")

        content = content.strip()
        if len(content) < 15:
            raise BadRequestException(f"The text file '{path.name}' is empty or contains insufficient content.")

        # Extract potential section headings
        headings = [
            line.strip() for line in content.split("\n")
            if line.strip() and len(line.strip()) < 80 and re.match(r"^(?:chapter|\d+\.|\d+\s+|module|[A-Z\s]{4,}:?)", line.strip(), re.IGNORECASE)
        ]

        return DocumentLoader._paginate_text(content, headings=headings, page_char_limit=2500)

    # -------------------------------------------------------------------------
    # 5. Markdown (.md) Extraction
    # -------------------------------------------------------------------------
    @staticmethod
    def extract_markdown(file_path: str) -> List[Dict[str, Any]]:
        path = Path(file_path)
        if not path.exists():
            raise BadRequestException(f"Markdown file does not exist: {path.name}")

        content = None
        for enc in ["utf-8", "utf-8-sig", "latin-1"]:
            try:
                content = path.read_text(encoding=enc)
                break
            except Exception:
                continue

        if content is None:
            raise BadRequestException(f"Unable to read Markdown file '{path.name}'.")

        content = content.strip()
        if len(content) < 15:
            raise BadRequestException(f"The Markdown file '{path.name}' contains no readable content.")

        # Extract markdown headings (#, ##, ###)
        headings = [
            re.sub(r"^#+\s*", "", line).strip()
            for line in content.split("\n")
            if line.strip().startswith("#")
        ]

        # Paginate on major headings or character boundaries
        return DocumentLoader._paginate_markdown(content, headings=headings, page_char_limit=2500)

    # -------------------------------------------------------------------------
    # Helper: Text Pagination for Continuous Formats
    # -------------------------------------------------------------------------
    @staticmethod
    def _paginate_text(text: str, headings: List[str], page_char_limit: int = 2500) -> List[Dict[str, Any]]:
        """Splits long continuous text into logical page blocks preserving paragraphs."""
        paragraphs = text.split("\n\n")
        pages: List[Dict[str, Any]] = []
        current_page_text: List[str] = []
        current_char_count = 0
        page_num = 1

        for p in paragraphs:
            p = p.strip()
            if not p:
                continue

            p_len = len(p)
            if current_char_count + p_len > page_char_limit and current_page_text:
                combined = "\n\n".join(current_page_text)
                p_headings = [h for h in headings if h in combined]
                pages.append({
                    "page_number": page_num,
                    "text": combined,
                    "char_count": len(combined),
                    "headings": p_headings,
                })
                page_num += 1
                current_page_text = [p]
                current_char_count = p_len
            else:
                current_page_text.append(p)
                current_char_count += p_len + 2

        if current_page_text:
            combined = "\n\n".join(current_page_text)
            p_headings = [h for h in headings if h in combined]
            pages.append({
                "page_number": page_num,
                "text": combined,
                "char_count": len(combined),
                "headings": p_headings,
            })

        return pages

    @staticmethod
    def _paginate_markdown(text: str, headings: List[str], page_char_limit: int = 2500) -> List[Dict[str, Any]]:
        """Splits markdown on top-level section headers (# or ##) without breaking code blocks."""
        # Split on markdown headings while keeping them
        sections = re.split(r"(?m)(?=^#{1,2}\s+)", text)
        pages: List[Dict[str, Any]] = []
        page_num = 1
        current_text = ""

        for sec in sections:
            sec = sec.strip()
            if not sec:
                continue

            if len(current_text) + len(sec) > page_char_limit and current_text:
                p_headings = [h for h in headings if h in current_text]
                pages.append({
                    "page_number": page_num,
                    "text": current_text,
                    "char_count": len(current_text),
                    "headings": p_headings,
                })
                page_num += 1
                current_text = sec
            else:
                current_text = f"{current_text}\n\n{sec}" if current_text else sec

        if current_text:
            p_headings = [h for h in headings if h in current_text]
            pages.append({
                "page_number": page_num,
                "text": current_text,
                "char_count": len(current_text),
                "headings": p_headings,
            })

        return pages

    # -------------------------------------------------------------------------
    # Document Structure Extraction (TOC / heading / window fallback)
    # -------------------------------------------------------------------------
    # Front/back-matter keywords to skip when building the outline
    _FRONTMATTER_KEYWORDS = frozenset([
        "preface", "foreword", "introduction", "table of contents", "contents",
        "acknowledgment", "acknowledgement", "copyright", "dedication",
        "about the author", "about the book", "colophon", "errata",
        "index", "appendix", "bibliography", "references", "glossary",
        "permissions", "legal notice", "trademark", "license",
    ])

    @classmethod
    def _is_frontback_matter(cls, title: str) -> bool:
        """Returns True if the section title looks like front/back matter."""
        t = title.strip().lower()
        return any(kw in t for kw in cls._FRONTMATTER_KEYWORDS)

    @classmethod
    def extract_structure(cls, file_path: str, mime_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Extract the document's section structure as a list of:
            {
                "title": str,
                "level": int,          # 1 = chapter, 2 = section, 3 = subsection
                "page_start": int,
                "page_end": int,       # exclusive end (or same as start for single-page sections)
            }

        Strategy order:
          1. PDF embedded TOC (get_toc)
          2. Heading detection from font size / bold flags
          3. Equal page-window fallback
        For DOCX, uses python-docx Heading styles.
        Returns [] if structure cannot be determined.
        """
        try:
            ext = cls.detect_format(file_path, mime_type)
        except Exception:
            return []

        try:
            if ext == ".pdf":
                return cls._extract_pdf_structure(file_path)
            elif ext == ".docx":
                return cls._extract_docx_structure(file_path)
            else:
                # For TXT / PPTX / MD, fall back to heading detection on loaded pages
                pages = cls.load_document(file_path, mime_type)
                return cls._heading_window_fallback(pages)
        except Exception as e:
            logger.warning(f"extract_structure failed for {file_path}: {e}")
            return []

    @classmethod
    def _extract_pdf_structure(cls, file_path: str) -> List[Dict[str, Any]]:
        import pymupdf
        doc = pymupdf.open(file_path)
        total_pages = len(doc)

        # --- Strategy 1: Embedded TOC ---
        toc = doc.get_toc()
        if toc:
            entries: List[Dict[str, Any]] = []
            for item in toc:
                if len(item) < 3:
                    continue
                level, title, page = int(item[0]), str(item[1]).strip(), int(item[2])
                if cls._is_frontback_matter(title):
                    continue
                if not title or page < 1:
                    continue
                entries.append({"title": title, "level": level, "page_start": page, "page_end": page})

            if entries:
                # Compute page_end from next section's page_start
                for i in range(len(entries) - 1):
                    entries[i]["page_end"] = max(entries[i]["page_start"], entries[i + 1]["page_start"] - 1)
                entries[-1]["page_end"] = total_pages
                doc.close()
                return entries

        # --- Strategy 2: Font-size / bold heading detection ---
        sections = cls._detect_headings_by_font(doc)
        doc.close()
        if sections:
            return sections

        # --- Strategy 3: Equal page-window fallback ---
        pages = []
        try:
            import pymupdf as fitz
            d = fitz.open(file_path)
            for idx in range(len(d)):
                pages.append({"page_number": idx + 1, "text": d[idx].get_text()})
            d.close()
        except Exception:
            pass
        return cls._heading_window_fallback(pages)

    @classmethod
    def _detect_headings_by_font(cls, doc) -> List[Dict[str, Any]]:
        """
        Detect section headings by analyzing font size relative to the median body
        font size across the document. Bold or significantly larger text is a heading.
        """
        import statistics

        # Collect all font sizes to determine body text baseline
        all_sizes = []
        for page in doc:
            try:
                blocks = page.get_text("dict").get("blocks", [])
                for block in blocks:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            sz = span.get("size", 0)
                            if sz > 4:
                                all_sizes.append(sz)
            except Exception:
                pass

        if not all_sizes:
            return []

        try:
            median_size = statistics.median(all_sizes)
        except Exception:
            return []

        heading_threshold = median_size * 1.15   # 15% larger than body = heading

        entries: List[Dict[str, Any]] = []
        total_pages = len(doc)

        for page_idx, page in enumerate(doc):
            page_num = page_idx + 1
            try:
                blocks = page.get_text("dict").get("blocks", [])
                for block in blocks:
                    for line in block.get("lines", []):
                        line_text = ""
                        max_size = 0
                        is_bold = False
                        for span in line.get("spans", []):
                            line_text += span.get("text", "")
                            sz = span.get("size", 0)
                            if sz > max_size:
                                max_size = sz
                            flags = span.get("flags", 0)
                            if flags & 0b10000:   # bold flag
                                is_bold = True

                        line_text = line_text.strip()
                        if not line_text or len(line_text) > 120:
                            continue

                        if cls._is_frontback_matter(line_text):
                            continue

                        if max_size >= heading_threshold or (is_bold and max_size >= median_size):
                            level = 1 if max_size >= median_size * 1.3 else 2
                            entries.append({
                                "title": line_text,
                                "level": level,
                                "page_start": page_num,
                                "page_end": page_num,
                            })
            except Exception:
                continue

        if not entries:
            return []

        # Deduplicate consecutive same-title entries and compute page_end
        deduplicated: List[Dict[str, Any]] = []
        for e in entries:
            if deduplicated and deduplicated[-1]["title"] == e["title"]:
                continue
            deduplicated.append(e)

        for i in range(len(deduplicated) - 1):
            deduplicated[i]["page_end"] = max(deduplicated[i]["page_start"], deduplicated[i + 1]["page_start"] - 1)
        if deduplicated:
            deduplicated[-1]["page_end"] = total_pages

        return deduplicated

    @classmethod
    def _extract_docx_structure(cls, file_path: str) -> List[Dict[str, Any]]:
        """Extract structure from DOCX using python-docx Heading styles."""
        try:
            from docx import Document as DocxDocument
        except ImportError:
            return []

        try:
            doc = DocxDocument(file_path)
        except Exception:
            return []

        entries: List[Dict[str, Any]] = []
        pseudo_page = 1
        chars_per_page = 2000

        char_count = 0
        for para in doc.paragraphs:
            style_name = para.style.name if para.style else ""
            text = para.text.strip()

            char_count += len(text) + 1
            pseudo_page = max(1, char_count // chars_per_page + 1)

            if style_name.startswith("Heading"):
                try:
                    level = int(style_name.split()[-1])
                except (ValueError, IndexError):
                    level = 1
                if text and not cls._is_frontback_matter(text):
                    entries.append({
                        "title": text,
                        "level": min(level, 3),
                        "page_start": pseudo_page,
                        "page_end": pseudo_page,
                    })

        # Compute page_end from next entry
        for i in range(len(entries) - 1):
            entries[i]["page_end"] = max(entries[i]["page_start"], entries[i + 1]["page_start"] - 1)

        return entries

    @classmethod
    def _heading_window_fallback(cls, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Last-resort: split document into equal page windows of ~4 pages each.
        Title each section from its first detected heading or first line.
        """
        total_pages = len(pages)
        if total_pages == 0:
            return []

        window_size = max(1, min(4, total_pages // 3 + 1))
        sections: List[Dict[str, Any]] = []

        for i in range(0, total_pages, window_size):
            window = pages[i:i + window_size]
            page_start = window[0].get("page_number", i + 1)
            page_end = window[-1].get("page_number", page_start + len(window) - 1)

            # Try to get a title from first heading in the window, else first non-empty line
            title = ""
            for p in window:
                headings = p.get("headings", [])
                if headings:
                    title = headings[0]
                    break
                first_lines = [l.strip() for l in p.get("text", "").split("\n") if l.strip()]
                if first_lines:
                    candidate = first_lines[0][:80]
                    if len(candidate) > 5 and not candidate.isdigit():
                        title = candidate
                        break

            if not title:
                title = f"Section {len(sections) + 1}"

            if cls._is_frontback_matter(title):
                continue

            sections.append({
                "title": title,
                "level": 1,
                "page_start": page_start,
                "page_end": page_end,
            })

        return sections

    # -------------------------------------------------------------------------
    # Unified Entry Point
    # -------------------------------------------------------------------------
    @classmethod
    def load_document(cls, file_path: str, mime_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Universal entry point. Detects format and delegates to the specialized extractor.
        Returns a list of structured page dictionaries:
        [{ "page_number": 1, "text": "...", "char_count": 1200, "headings": [...] }]
        """
        ext = cls.detect_format(file_path, mime_type)

        if ext == ".pdf":
            return cls.extract_pdf(file_path)
        elif ext == ".docx":
            return cls.extract_docx(file_path)
        elif ext == ".pptx":
            return cls.extract_pptx(file_path)
        elif ext == ".txt":
            return cls.extract_txt(file_path)
        elif ext in (".md", ".markdown"):
            return cls.extract_markdown(file_path)
        else:
            raise BadRequestException(f"Unsupported format: '{ext}'. Supported: PDF, DOCX, TXT, PPTX, Markdown.")
