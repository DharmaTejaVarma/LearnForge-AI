import re
from typing import List, Dict, Any, Optional
from app.core.sanitizer import EducationalSanitizer
from app.core.logging import logger

class DocumentAgent:
    """
    Intelligent Document Understanding Agent for LearnForge AI.
    Analyzes multi-page educational documents across different formats (PDF, DOCX, TXT, PPTX, MD)
    to classify subject domains, detect content types, discover chapter/topic hierarchies,
    and map source page citations without relying on fixed templates or hardcoded subjects.
    """

    # Domain keyword indicators
    DOMAIN_INDICATORS = {
        "computer_science": [
            r"\b(?:python|java|c\+\+|javascript|typescript|golang|rust|algorithm|function|class|method|variable|loop|recursion|data structure|api|database|sql|nosql|frontend|backend|framework|compiler|git|docker|linux|object-oriented|oop|asynchronous|concurrency|threading|pointer|array|hash table|graph|binary tree|stack|queue)\b"
        ],
        "mathematics": [
            r"\b(?:theorem|proof|lemma|corollary|calculus|derivative|integral|differential|matrix|matrices|vector space|eigenvalue|eigenvector|linear algebra|probability|discrete math|combinatorics|polynomial|equation|inequality|logarithm|trigonometry|geometric|convergence|divergence|limit|riemann|fourier|laplace)\b"
        ],
        "natural_sciences": [
            r"\b(?:molecule|atom|electron|proton|neutron|covalent|ionic|photosynthesis|dna|rna|gene|protein|cell membrane|enzyme|metabolism|thermodynamics|entropy|enthalpy|kinetic|gravitational|electromagnetic|optics|quantum|organism|ecosystem|species|evolution|respiration)\b"
        ],
        "engineering": [
            r"\b(?:circuit|resistor|capacitor|inductor|voltage|current|transistor|signal processing|stress|strain|shear force|bending moment|fluid dynamics|heat transfer|control system|cad|thermodynamic cycle|structural analysis|actuator|sensor|embedded system)\b"
        ],
        "business_economics": [
            r"\b(?:macroeconomics|microeconomics|inflation|gdp|supply and demand|elasticity|fiscal policy|monetary policy|cash flow|balance sheet|income statement|roi|ebitda|marketing|stakeholder|supply chain|valuation|equity|capital market|corporate governance|business model)\b"
        ],
        "humanities_social": [
            r"\b(?:historiography|renaissance|enlightenment|revolution|colonialism|democracy|sovereignty|constitution|epistemology|ethics|existentialism|utilitarianism|cognitive|behavioral|psychopathology|sociological|stratification|anthropology|jurisprudence|statute)\b"
        ],
    }

    # Content type indicators
    CONTENT_TYPE_INDICATORS = {
        "programming": [
            r"(?:def\s+\w+\(|class\s+\w+|import\s+\w+|function\s*\(|console\.log|System\.out|public\s+class|\b(?:return|while|for|if|else)\b.*:?|```\w*)",
        ],
        "mathematical": [
            r"(?:\$.*\$|\\frac\{|\\sum|\\int|f\(x\)\s*=|y\s*=|d[xy]/d[xy]|\b(?:sin|cos|tan|log|ln|lim_)\b|\b(?:theorem|definition|lemma|corollary)\s+\d+|\b(?:equation|matrix|matrices|eigenvalue|eigenvector|vector|integral|derivative|formula|proof|calculus|algebra)\b)",
        ],
        "scientific": [
            r"\b(?:hypothesis|experiment|observation|specimen|control group|reagent|reaction|concentration|velocity|acceleration|wavelength|frequency|catalyst)\b",
        ],
        "case_study": [
            r"\b(?:case study|background analysis|problem statement|recommendation|organizational context|implementation plan|key findings|client scenario)\b",
        ],
        "theoretical": [
            r"\b(?:paradigm|conceptual framework|theoretical foundation|philosophy of|taxonomy|epistemological|heuristic|axiological|underlying assumptions)\b",
        ]
    }

    @classmethod
    def analyze_document(
        cls,
        pages: List[Dict[str, Any]],
        filename: str,
        user_title_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Performs holistic structural and thematic analysis of the extracted pages.
        Returns a document blueprint containing:
        - subject_domain
        - content_type
        - clean_title
        - detected_outline (chapters & topic anchors with page numbers)
        - pedagogical_profile (recommended formatting and component mix)
        - total_pages
        - sample_overview_text
        """
        if not pages:
            return cls._empty_analysis(filename)

        total_pages = len(pages)
        full_text_sample = "\n\n".join(
            p.get("text", "")[:1000] for p in pages[:min(10, total_pages)]
        )
        clean_text_sample = EducationalSanitizer.sanitize_educational_text(full_text_sample)

        # 1. Subject Domain Classification
        subject_domain = cls._classify_domain(clean_text_sample)

        # 2. Content Type Detection
        content_type = cls._detect_content_type(clean_text_sample, domain=subject_domain)

        # 3. Structural Hierarchy Extraction (TOC, Headings, or Logical Sections)
        detected_outline = cls._extract_structural_outline(pages)

        # 4. Generate Clean Title
        clean_title = cls._determine_clean_title(filename, pages, user_title_hint)

        # 5. Build Pedagogical Profile
        pedagogical_profile = cls._build_pedagogical_profile(subject_domain, content_type)

        return {
            "clean_title": clean_title,
            "subject_domain": subject_domain,
            "content_type": content_type,
            "detected_outline": detected_outline,
            "pedagogical_profile": pedagogical_profile,
            "total_pages": total_pages,
            "has_formal_toc": any("toc" in p and len(p["toc"]) > 0 for p in pages),
            "sample_overview_text": clean_text_sample[:1500],
        }

    @classmethod
    def _classify_domain(cls, text: str) -> str:
        """Scores text against domain keyword sets to identify primary subject matter."""
        domain_scores = {d: 0 for d in cls.DOMAIN_INDICATORS}

        for domain, patterns in cls.DOMAIN_INDICATORS.items():
            for pat in patterns:
                matches = re.findall(pat, text, re.IGNORECASE)
                domain_scores[domain] += len(matches)

        top_domain = max(domain_scores, key=domain_scores.get)
        if domain_scores[top_domain] >= 2:
            return top_domain
        return "general"

    @classmethod
    def _detect_content_type(cls, text: str, domain: str = "general") -> str:
        """Identifies whether content is code-heavy, math-heavy, scientific, or conceptual."""
        type_scores = {t: 0 for t in cls.CONTENT_TYPE_INDICATORS}

        for c_type, patterns in cls.CONTENT_TYPE_INDICATORS.items():
            for pat in patterns:
                matches = re.findall(pat, text, re.IGNORECASE)
                type_scores[c_type] += len(matches)

        if domain == "mathematics" and type_scores["mathematical"] >= 1:
            return "mathematical"
        if domain == "computer_science" and type_scores["programming"] >= 1:
            return "programming"

        top_type = max(type_scores, key=type_scores.get)
        if type_scores[top_type] >= 2:
            return top_type
        return "theoretical"

    @classmethod
    def _extract_structural_outline(cls, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Discovers the document's natural chapters, sections, and topics.
        First checks for embedded PDF TOC, then heading anchors, then page clusters.
        """
        # Strategy A: Check for formal embedded TOC (from PDF metadata)
        all_toc_entries = []
        for p in pages:
            toc = p.get("toc", [])
            for item in toc:
                all_toc_entries.append(item)

        if len(all_toc_entries) >= 2:
            chapters = []
            current_chapter = None
            for item in all_toc_entries:
                lvl = item.get("level", 1)
                title = EducationalSanitizer.clean_title(item.get("title", ""))
                page_num = item.get("page", 1)

                if lvl == 1 or current_chapter is None:
                    current_chapter = {
                        "title": title,
                        "start_page": page_num,
                        "topics": []
                    }
                    chapters.append(current_chapter)
                else:
                    current_chapter["topics"].append({
                        "title": title,
                        "page": page_num
                    })

            if chapters:
                return chapters

        # Strategy B: Extract from detected headings across pages
        discovered_sections: List[Dict[str, Any]] = []
        for p in pages:
            page_num = p.get("page_number", 1)
            headings = p.get("headings", [])
            for h in headings:
                clean_h = EducationalSanitizer.clean_title(h)
                if len(clean_h) > 4 and not EducationalSanitizer.contains_metadata_leak(clean_h):
                    # Check if this heading represents a major chapter or module
                    is_chapter = bool(re.match(r"^(?:chapter|module|part|unit)\b", h, re.IGNORECASE))
                    discovered_sections.append({
                        "title": clean_h,
                        "page": page_num,
                        "is_major": is_chapter,
                    })

        # Group headings into chapters and topics
        if discovered_sections:
            chapters = []
            current_chap = None
            for sec in discovered_sections:
                if sec["is_major"] or current_chap is None or len(current_chap["topics"]) >= 4:
                    current_chap = {
                        "title": sec["title"],
                        "start_page": sec["page"],
                        "topics": []
                    }
                    chapters.append(current_chap)
                else:
                    if sec["title"] != current_chap["title"] and sec["title"] not in [t["title"] for t in current_chap["topics"]]:
                        current_chap["topics"].append({
                            "title": sec["title"],
                            "page": sec["page"]
                        })

            if chapters:
                return chapters

        # Strategy C: Multi-page proportional partition for unstructured documents
        total_pages = len(pages)
        if total_pages <= 3:
            return [{
                "title": "Comprehensive Overview & Core Principles",
                "start_page": 1,
                "topics": [{"title": "Fundamental Concepts", "page": 1}]
            }]

        num_sections = min(5, max(2, total_pages // 4))
        step = max(1, total_pages // num_sections)
        chapters = []
        for i in range(num_sections):
            start_p = i * step + 1
            chapters.append({
                "title": f"Module {i + 1}: Foundational Concepts Part {i + 1}",
                "start_page": start_p,
                "topics": [
                    {"title": f"Core Principles & Theory (Pages {start_p}-{min(total_pages, start_p + step - 1)})", "page": start_p}
                ]
            })

        return chapters

    @classmethod
    def _determine_clean_title(
        cls,
        filename: str,
        pages: List[Dict[str, Any]],
        user_title_hint: Optional[str] = None
    ) -> str:
        """Determines the most accurate academic title for the document."""
        if user_title_hint and len(user_title_hint.strip()) > 3:
            return EducationalSanitizer.clean_title(user_title_hint)

        clean_file_title = EducationalSanitizer.clean_title(filename)

        # Prefer clean filename title if it contains descriptive words and isn't a fallback placeholder
        if clean_file_title and clean_file_title != "Course Study Guide":
            return clean_file_title

        # Inspect page 1 for possible title heading (avoiding bare chapter titles)
        if pages and pages[0].get("headings"):
            first_heading = pages[0]["headings"][0]
            clean_heading = EducationalSanitizer.clean_title(first_heading)
            if len(clean_heading) > 4 and not EducationalSanitizer.contains_metadata_leak(clean_heading):
                return clean_heading

        return clean_file_title

    @classmethod
    def _build_pedagogical_profile(cls, domain: str, content_type: str) -> Dict[str, Any]:
        """Provides pedagogical scaffolding instructions based on document nature."""
        profile = {
            "requires_code_snippets": (domain == "computer_science" or content_type == "programming"),
            "requires_formula_derivations": (domain in ("mathematics", "engineering") or content_type == "mathematical"),
            "requires_step_by_step": (content_type in ("programming", "mathematical", "practical")),
            "requires_case_scenarios": (domain in ("business_economics", "humanities_social") or content_type == "case_study"),
            "tone": "rigorous academic and pedagogical",
            "recommended_lesson_components": [
                "Intuitive Overview",
                "Core Definitions",
                "Technical Analysis",
                "Practical Applications",
                "Common Misconceptions",
                "Key Takeaways",
                "Practice Questions",
            ]
        }

        if profile["requires_code_snippets"]:
            profile["recommended_lesson_components"].insert(4, "Code Implementation & Syntax Analysis")
        elif profile["requires_formula_derivations"]:
            profile["recommended_lesson_components"].insert(4, "Mathematical Derivations & Worked Examples")

        return profile

    @classmethod
    def _empty_analysis(cls, filename: str) -> Dict[str, Any]:
        return {
            "clean_title": EducationalSanitizer.clean_title(filename),
            "subject_domain": "general",
            "content_type": "theoretical",
            "detected_outline": [],
            "pedagogical_profile": cls._build_pedagogical_profile("general", "theoretical"),
            "total_pages": 0,
            "has_formal_toc": False,
            "sample_overview_text": "",
        }
