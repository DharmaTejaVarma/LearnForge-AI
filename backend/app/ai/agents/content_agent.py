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

    MAX_CHAPTERS = 24
    MAX_TOPICS_PER_CHAPTER = 12
    _META_SUBTOPICS = frozenset(["preview", "review", "summary", "exercises", "further reading"])

    @classmethod
    async def synthesize_course_outline(
        cls,
        doc_blueprint: Dict[str, Any],
        target_chapters_count: int = 18,
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
        category = domain.replace("_", " ").title() if domain != "general" else "General Studies"

        structure_chapters = cls._build_chapters_from_sections(
            sections=sections or [],
            detected_outline=doc_blueprint.get("detected_outline", []),
            target_chapters_count=min(max(1, target_chapters_count), cls.MAX_CHAPTERS),
        )

        description, objectives = await cls._generate_meta(
            clean_title=clean_title,
            domain=domain,
            difficulty=difficulty,
            chapters=structure_chapters,
            overview_text=doc_blueprint.get("sample_overview_text", "")[:1500],
        )

        prerequisites = cls._derive_prerequisites(domain, difficulty)
        total_lessons = sum(len(ch.get("topics", [])) for ch in structure_chapters)
        est_hours = max(1, round((total_lessons * 12) / 60))

        return {
            "title": clean_title,
            "description": description,
            "category": category,
            "prerequisites": prerequisites,
            "estimated_duration_hours": est_hours,
            "learning_objectives": objectives,
            "chapters": structure_chapters,
        }

    @staticmethod
    def _derive_prerequisites(domain: str, difficulty: str) -> List[str]:
        """Derive sensible course-level prerequisites from subject domain & difficulty."""
        diff = (difficulty or "intermediate").lower()
        if diff == "beginner":
            return ["Basic computer literacy and curiosity to learn", "No prior domain expertise required"]
        if domain == "computer_science":
            return [
                "Working familiarity with programming syntax and variables",
                "Basic understanding of command-line tools and HTTP concepts",
            ]
        if domain == "mathematics":
            return ["Foundational algebra and symbolic notation fluency"]
        return [f"Introductory familiarity with {domain.replace('_', ' ')} fundamentals"]

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
        """Convert extract_structure() output into module/chapter dicts."""
        import re
        from app.ai.rag.document_loader import DocumentLoader

        # Re-filter front/back matter safely (handles cached structure JSON from older uploads)
        clean_sections: List[Dict[str, Any]] = []
        skipped_lvl: Optional[int] = None
        for sec in sections:
            lvl = int(sec.get("level", 1))
            raw_title = str(sec.get("title", "")).strip()
            if not raw_title:
                continue
            if skipped_lvl is not None:
                if lvl > skipped_lvl:
                    continue
                skipped_lvl = None
            if DocumentLoader._is_frontback_matter(raw_title):
                skipped_lvl = lvl
                continue
            clean_sections.append(sec)

        if not clean_sections:
            return []

        # Detect textbook hierarchy: Part (level 1) -> Chapter (level 2) -> Topic (level 3+)
        has_parts = any(
            int(s.get("level", 1)) == 1
            and re.match(r"^(?:part|section|book|unit)\b", str(s.get("title", "")).strip(), re.IGNORECASE)
            for s in clean_sections
        )
        has_level2_chapters = any(
            int(s.get("level", 1)) == 2
            and re.match(r"^(?:chapter|module|\d+[\.\s])", str(s.get("title", "")).strip(), re.IGNORECASE)
            for s in clean_sections
        )
        if not has_level2_chapters and has_parts:
            has_level2_chapters = any(int(s.get("level", 1)) == 2 for s in clean_sections)

        if has_parts and has_level2_chapters:
            module_level = 2
            module_candidates = [
                s for s in clean_sections if int(s.get("level", 1)) == 2
            ][:max_chapters]
            topic_candidates = [
                s for s in clean_sections if int(s.get("level", 1)) == 3
            ]
            fallback_subtopics = [
                s for s in clean_sections if int(s.get("level", 1)) >= 4
            ]
        else:
            module_level = 1
            module_candidates = [
                s for s in clean_sections if int(s.get("level", 1)) <= 1
            ][:max_chapters]
            topic_candidates = [
                s for s in clean_sections if int(s.get("level", 1)) == 2
            ]
            fallback_subtopics = [
                s for s in clean_sections if int(s.get("level", 1)) >= 3
            ]

        seen_topic_titles = set()
        chapters = []
        for idx, ch in enumerate(module_candidates):
            ch_title = EducationalSanitizer.clean_title(ch.get("title", ""))
            if not ch_title or len(ch_title) < 3:
                continue

            ch_page_start = ch.get("page_start", 1)
            # Bound module end page by the next module so all nested subsections are captured
            next_mod_start = (
                module_candidates[idx + 1].get("page_start")
                if idx + 1 < len(module_candidates)
                else None
            )
            ch_page_end = ch.get("page_end")
            if next_mod_start:
                ch_page_end = max(ch_page_start, next_mod_start - 1)

            def _collect_topics() -> List[Dict[str, Any]]:
                collected: List[Dict[str, Any]] = []
                # Preserve exact source ordering inside [ch_page_start, ch_page_end]
                chap_indexed = [
                    (orig_idx, sub)
                    for orig_idx, sub in enumerate(clean_sections)
                    if ch_page_start <= sub.get("page_start", 0)
                    and (ch_page_end is None or sub.get("page_start", 0) <= ch_page_end)
                    and int(sub.get("level", 1)) >= (module_level + 1)
                ]
                chap_l3 = [(pos, sub) for pos, sub in chap_indexed if int(sub.get("level", 1)) == (module_level + 1)]

                for s3_i, (s3_pos, sub) in enumerate(chap_l3):
                    t_title = EducationalSanitizer.clean_title(sub.get("title", ""))
                    if not t_title or len(t_title) < 2:
                        continue
                    low = t_title.lower()
                    if low in cls._META_SUBTOPICS or low in seen_topic_titles:
                        continue

                    next_s3_pos = chap_l3[s3_i + 1][0] if s3_i + 1 < len(chap_l3) else 10**9
                    s3_start = sub.get("page_start", ch_page_start)
                    next_s3_page = chap_l3[s3_i + 1][1].get("page_start") if s3_i + 1 < len(chap_l3) else None
                    s3_end = sub.get("page_end") or ch_page_end or s3_start
                    if next_s3_page and s3_end >= next_s3_page:
                        s3_end = max(s3_start, next_s3_page)

                    # Find grandchild headings positioned strictly between s3_pos and next_s3_pos in TOC order
                    nested_l4 = [
                        g
                        for pos, g in chap_indexed
                        if s3_pos < pos < next_s3_pos
                        and int(g.get("level", 1)) >= (module_level + 2)
                        and EducationalSanitizer.clean_title(g.get("title", "")).lower() not in cls._META_SUBTOPICS
                    ]

                    span_pages = max(1, (s3_end or s3_start) - s3_start + 1)
                    if len(nested_l4) >= 4 and span_pages >= 3:
                        clusters = cls._cluster_subsections(t_title, nested_l4, s3_start, s3_end)
                        for cl in clusters:
                            cl_low = cl["title"].lower()
                            if cl_low in seen_topic_titles:
                                continue
                            seen_topic_titles.add(cl_low)
                            collected.append(cl)
                    else:
                        seen_topic_titles.add(low)
                        collected.append({
                            "title": t_title,
                            "page_start": s3_start,
                            "page_end": s3_end,
                            "printed_page_start": sub.get("printed_page_start"),
                            "printed_page_end": sub.get("printed_page_end"),
                            "subtopics": [
                                EducationalSanitizer.clean_title(g.get("title", ""))
                                for g in nested_l4
                                if g.get("title")
                            ],
                        })
                return collected

            topics = _collect_topics()
            if len(topics) < 2 and fallback_subtopics:
                for sub in fallback_subtopics:
                    s_start = sub.get("page_start", 0)
                    if ch_page_start <= s_start and (ch_page_end is None or s_start <= ch_page_end):
                        t_title = EducationalSanitizer.clean_title(sub.get("title", ""))
                        low = t_title.lower() if t_title else ""
                        if t_title and len(t_title) > 2 and low not in cls._META_SUBTOPICS and low not in seen_topic_titles:
                            seen_topic_titles.add(low)
                            topics.append({
                                "title": t_title,
                                "page_start": s_start,
                                "page_end": sub.get("page_end"),
                                "printed_page_start": sub.get("printed_page_start"),
                                "printed_page_end": sub.get("printed_page_end"),
                                "subtopics": [],
                            })
            topics = topics[: cls.MAX_TOPICS_PER_CHAPTER]

            if not topics:
                mid = None
                if ch_page_start is not None and ch_page_end is not None:
                    mid = (ch_page_start + ch_page_end) // 2
                fallback_pair = [
                    (f"{ch_title}: Core Architecture & Mechanics", ch_page_start, mid or ch_page_end),
                    (f"{ch_title}: Applied Implementation", (mid + 1) if mid else ch_page_start, ch_page_end),
                ]
                for ft, fps, fpe in fallback_pair:
                    if ft.lower() not in seen_topic_titles:
                        seen_topic_titles.add(ft.lower())
                        topics.append({"title": ft, "page_start": fps, "page_end": fpe})

            chapters.append({
                "title": ch_title,
                "description": f"Covers {', '.join(t['title'] for t in topics[:4])} with source-grounded explanations, examples, and practice.",
                "topics": topics,
                "page_start": ch_page_start,
                "page_end": ch_page_end,
                "printed_page_start": ch.get("printed_page_start"),
                "printed_page_end": ch.get("printed_page_end"),
            })

        return chapters

    @classmethod
    def _cluster_subsections(
        cls,
        parent_title: str,
        nested_l4: List[Dict[str, Any]],
        s3_start: int,
        s3_end: int,
    ) -> List[Dict[str, Any]]:
        """Group dense Level-4 subsections into cohesive 1-2 page learning units."""
        clusters: List[Dict[str, Any]] = []
        # First unit covers parent opening concept + first nested overview heading (including shared boundary page before HTTP)
        first = nested_l4[0]
        first_end = (
            min(s3_end, max(s3_start, nested_l4[1]["page_start"]))
            if len(nested_l4) > 1
            else (first.get("page_end") or s3_start)
        )
        clusters.append({
            "title": parent_title,
            "page_start": s3_start,
            "page_end": first_end,
            "printed_page_start": first.get("printed_page_start"),
            "printed_page_end": nested_l4[1].get("printed_page_start") if len(nested_l4) > 1 else first.get("printed_page_end"),
            "subtopics": [EducationalSanitizer.clean_title(first.get("title", ""))],
        })

        # Partition remaining Level-4 items by semantic grouping or pairs/triplets
        rest = nested_l4[1:]
        i = 0
        while i < len(rest):
            head = rest[i]
            group = [head]
            if i + 1 < len(rest):
                nxt = rest[i + 1]
                if (nxt["page_start"] - head["page_start"]) <= 2:
                    group.append(nxt)
                    i += 1
                    # Include trailing sibling when only 1 item would remain (e.g. JSON, JSON:API & GraphQL)
                    if i + 1 < len(rest) and len(rest) - (i + 1) == 1 and (rest[i + 1]["page_start"] - nxt["page_start"]) <= 1:
                        group.append(rest[i + 1])
                        i += 1
            i += 1

            titles = [EducationalSanitizer.clean_title(g.get("title", "")) for g in group if g.get("title")]
            if len(titles) == 1:
                unit_title = titles[0]
            elif len(titles) == 2:
                unit_title = f"{titles[0]} & {titles[1]}"
            else:
                unit_title = f"{titles[0]} ({titles[1]}, {titles[2]})"

            g_start = group[0].get("page_start", s3_start)
            g_end = max(g.get("page_end") or g.get("page_start") or g_start for g in group)
            p_start_lbl = str(group[0].get("printed_page_start") or "")
            p_end_lbl = str(group[-1].get("printed_page_end") or "")
            if (
                p_start_lbl.isdigit()
                and p_end_lbl.isdigit()
                and int(p_end_lbl) > int(p_start_lbl)
            ):
                g_end = max(g_end, g_start + (int(p_end_lbl) - int(p_start_lbl)))
            elif i >= len(rest) and s3_end and s3_end > g_end and (s3_end - g_start) <= 3:
                g_end = s3_end
            else:
                g_end = min(s3_end, max(g_start, g_end))
            clusters.append({
                "title": unit_title,
                "page_start": g_start,
                "page_end": g_end,
                "printed_page_start": group[0].get("printed_page_start"),
                "printed_page_end": group[-1].get("printed_page_end"),
                "subtopics": titles,
            })

        return clusters

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
        """Use LLM to write course description and learning objectives (uses fast deterministic summary when local-only)."""
        domain_label = domain.replace("_", " ").title()
        fallback_meta = (
            f"A {difficulty.lower()}-level course on {clean_title} covering {domain_label} "
            f"concepts across {len(chapters)} modules.",
            [
                f"Understand the core concepts and terminology of {clean_title}",
                "Apply the key methods and frameworks to practical problems",
                f"Analyze and evaluate {domain_label.lower()} systems and outcomes",
            ],
        )

        if model_router.is_local_only():
            return fallback_meta

        chapter_titles = "\n".join(f"- {c['title']}" for c in chapters)
        prompt = (
            f"You are writing course metadata for a course titled '{clean_title}'.\n"
            f"Subject domain: {domain_label}\n"
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
                max_tokens=300,
                format="json",
                allow_local_fallback=False,
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

        return fallback_meta
