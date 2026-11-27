"""Lesson Generation Agent for LearnForge AI — Grounded & Interactive Architecture.

Generates comprehensive, structured, source-grounded lessons with:
- Complete Code Examples (imports, defined variables, expected output, execution notes)
- Real-World Architectural Application
- Interactive Concept Cards, Selectable Architecture Diagrams, Simulators & Project Milestones
- Pre-save completeness and code-validity checks (no mid-sentence truncation)
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import time
from typing import Any, Dict, List, Optional

from app.ai.agents.interactive_builder import InteractiveLearningBuilder
from app.ai.models.model_router import model_router
from app.core.config import settings
from app.core.logging import logger
from app.core.sanitizer import EducationalSanitizer
from app.services.code_validator import CodeValidationPipeline
from app.services.lesson_evaluator import LessonEvaluator


class LessonAgent:
    """Generates student-friendly, technically complete lessons from page-scoped source chunks."""

    PROMPT_VERSION = "v4.0"

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
        subtopics: Optional[List[str]] = None,
        printed_pages: Optional[List[str]] = None,
        chapter_order: int = 0,
        doc_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return lesson payload + interactive structured_sections + validation metadata."""
        domain = doc_blueprint.get("subject_domain", "general")
        content_type = doc_blueprint.get("content_type", "theoretical")
        resolved_printed = printed_pages or cls._extract_printed_pages(passages, source_pages)

        source_text = (
            "\n\n".join(
                EducationalSanitizer.sanitize_educational_text(p["text"]) or p["text"]
                for p in passages
            )
            if passages
            else ""
        )

        if resolved_printed:
            pages_range = (
                f"Book Pages {resolved_printed[0]}–{resolved_printed[-1]}"
                if len(resolved_printed) > 1
                else f"Book Page {resolved_printed[0]}"
            )
        elif page_start is not None and page_end is not None:
            pages_range = f"Pages {page_start}–{page_end}"
        else:
            pages_range = "Course Source Material"

        # Extract compact structured notes only when a non-OTPM-capped cloud model is active
        notes_json: Dict[str, Any] = {}
        if source_text.strip() and not model_router.is_local_only() and not settings.GROQ_API_KEY:
            notes_json = await cls._extract_notes(source_text, topic_title, domain)

        # Build deterministic source-grounded Lesson Knowledge Map (0 extra LLM calls)
        knowledge_map = cls._build_knowledge_map(
            topic_title=topic_title,
            chapter_title=chapter_title,
            source_text=source_text,
            subtopics=subtopics or [],
            domain=domain,
            notes=notes_json,
        )

        t_inf_start = time.perf_counter()
        content, error, provider_used = await cls._write_lesson(
            topic_title=topic_title,
            chapter_title=chapter_title,
            course_title=course_title,
            source_text=source_text,
            notes=notes_json,
            difficulty=difficulty,
            domain=domain,
            content_type=content_type,
            pages_range=pages_range,
            subtopics=subtopics or [],
            knowledge_map=knowledge_map,
        )
        inference_ms = round((time.perf_counter() - t_inf_start) * 1000, 1)

        if not content:
            return {
                "title": topic_title,
                "content": "",
                "summary": "",
                "key_takeaways": [],
                "learning_objectives": [],
                "prerequisites": [],
                "estimated_minutes": 10,
                "structured_sections": {},
                "source_pages": source_pages,
                "printed_pages": resolved_printed,
                "page_start": page_start,
                "page_end": page_end,
                "generation_status": "failed",
                "generation_error": error or "LLM returned empty content",
            }

        t_val_start = time.perf_counter()
        content, validation_checks = cls._finalize_and_validate_content(
            content=content,
            topic_title=topic_title,
            chapter_title=chapter_title,
            pages_range=pages_range,
            source_text=source_text,
            subtopics=subtopics or [],
        )

        # Validate Python code blocks (AST + undefined identifiers; skip slow subprocess sandbox in fast Groq mode)
        code_blocks = re.findall(r"```python\n(.*?)```", content, flags=re.DOTALL)
        if code_blocks and (domain == "computer_science" or content_type == "programming"):
            use_sandbox = not bool(settings.GROQ_API_KEY)
            for blk in code_blocks:
                if "```" in blk or not blk.strip():
                    continue
                chk = CodeValidationPipeline.validate_code_block(blk, run_in_sandbox=use_sandbox)
                if not chk.valid:
                    repaired, rep_chk = await CodeValidationPipeline.repair_code_block(
                        blk, chk.error_message or "Validation failed", topic_title, max_attempts=1
                    )
                    if rep_chk.valid and repaired != blk:
                        content = content.replace(blk, repaired, 1)
                        validation_checks["python_syntax_valid"] = True
                        validation_checks["code_repaired"] = True

        tech_validation = CodeValidationPipeline.validate_technical_claims(
            content=content,
            domain=domain,
            source_text=source_text,
        )
        objectives = cls._extract_objectives(content, topic_title)

        eval_report = LessonEvaluator.evaluate(
            topic_title=topic_title,
            lesson_content=content,
            source_text=source_text,
            subtopics=subtopics or [],
            learning_objectives=objectives,
            technical_validation=tech_validation,
        )
        validation_ms = round((time.perf_counter() - t_val_start) * 1000, 1)

        summary = cls._extract_summary(content, topic_title)
        takeaways = cls._extract_takeaways(content)
        word_count = len(content.split())

        structured_sections = cls._extract_structured_sections(content)
        structured_sections["knowledge_map"] = knowledge_map
        interactive = InteractiveLearningBuilder.build(
            topic_title=topic_title,
            chapter_title=chapter_title,
            course_title=course_title,
            lesson_content=content,
            source_text=source_text,
            subtopics=subtopics or [],
            chapter_order=chapter_order,
            domain=domain,
            knowledge_map=knowledge_map,
        )
        structured_sections.update(interactive)
        structured_sections["subtopics"] = subtopics or []
        card_count = len(interactive.get("concept_cards") or [])
        estimated_minutes = max(6, min(35, round(word_count / 110) + card_count + 4))
        structured_sections["grounding_map"] = {
            "chapter": chapter_title,
            "printed_pages": resolved_printed,
            "pdf_pages": source_pages,
            "objectives": objectives,
            "subtopics": subtopics or [],
            "chunks": [
                {
                    "page_number": p.get("page_number"),
                    "printed_page": p.get("printed_page"),
                    "preview": (p.get("text") or "").strip()[:200],
                }
                for p in (passages or [])[:6]
            ],
        }
        structured_sections["performance_metrics"] = {
            "inference_ms": inference_ms,
            "validation_ms": validation_ms,
            "word_count": word_count,
            "provider": provider_used,
        }
        structured_sections["validation_meta"] = {
            "doc_hash": doc_hash,
            "chapter_title": chapter_title,
            "author": doc_blueprint.get("author", ""),
            "prompt_version": cls.PROMPT_VERSION,
            "model_used": provider_used,
            "source_pages": source_pages,
            "printed_pages": resolved_printed,
            "validation_passed": validation_checks.get("passed", True) and tech_validation.get("technical_accuracy_ok", True),
            "validation_checks": validation_checks,
            "technical_validation": tech_validation,
        }
        structured_sections["quality_evaluation"] = eval_report

        return {
            "title": topic_title,
            "content": content,
            "summary": summary,
            "key_takeaways": takeaways,
            "learning_objectives": objectives,
            "prerequisites": notes_json.get("prerequisites") or [f"Prior concepts from {chapter_title}"],
            "estimated_minutes": estimated_minutes,
            "structured_sections": structured_sections,
            "source_pages": source_pages,
            "printed_pages": resolved_printed,
            "page_start": page_start,
            "page_end": page_end,
            "generation_status": "ready",
            "generation_error": None,
        }

    @staticmethod
    def compute_cache_key(
        doc_hash: Optional[str],
        page_start: Optional[int],
        page_end: Optional[int],
        topic_title: str,
        difficulty: str,
    ) -> str:
        raw = f"{LessonAgent.PROMPT_VERSION}|{doc_hash or 'nohash'}|{page_start}|{page_end}|{topic_title.strip().lower()}|{(difficulty or 'intermediate').lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    @classmethod
    async def _extract_notes(
        cls,
        source_text: str,
        topic_title: str,
        domain: str,
    ) -> Dict[str, Any]:
        prompt = (
            f"Extract structured factual notes about '{topic_title}' strictly from the source text below.\n\n"
            "Return ONLY valid JSON with:\n"
            "{\n"
            '  "key_concepts": [{"term": "...", "explanation": "..."}],\n'
            '  "definitions": ["..."],\n'
            '  "important_points": ["..."],\n'
            '  "code_examples": [{"language": "...", "code": "...", "purpose": "..."}],\n'
            '  "prerequisites": ["..."]\n'
            "}\n\n"
            f"Source text:\n{source_text[:2800]}"
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
    def _build_knowledge_map(
        cls,
        topic_title: str,
        chapter_title: str,
        source_text: str,
        subtopics: List[str],
        domain: str,
        notes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Deterministically extract concepts, terminology, and code patterns from source_text."""
        concepts: List[Dict[str, str]] = []
        terminology: List[str] = []
        seen_terms = set()

        if notes:
            for c in (notes.get("key_concepts") or [])[:6]:
                term = str(c.get("term") or "").strip()
                expl = str(c.get("explanation") or "").strip()
                if term and expl and term.lower() not in seen_terms:
                    seen_terms.add(term.lower())
                    concepts.append({"term": term, "definition": expl})
                    terminology.append(term)

        # Extract Backticked/CamelCase/Capitalized terms and definitional sentences from source_text
        if source_text:
            sentences = re.split(r"(?<=[.!?])\s+", source_text.strip())
            def_patterns = [
                re.compile(r"^([A-Z][A-Za-z0-9_:/\-\s]{2,38}?)\s+(?:is|are|refers to|represents|means|provides|allows)\s+([^.!?]{15,160}[.!?])"),
                re.compile(r"`([A-Za-z0-9_.\-/]{2,32})`"),
            ]
            for sent in sentences[:60]:
                s_clean = " ".join(sent.split()).strip()
                if len(s_clean) < 20 or len(s_clean) > 220:
                    continue
                m = def_patterns[0].match(s_clean)
                if m:
                    term = m.group(1).strip(" :-")
                    if term.lower() not in seen_terms and len(term.split()) <= 5:
                        seen_terms.add(term.lower())
                        concepts.append({"term": term, "definition": s_clean})
                        terminology.append(term)
                if len(concepts) >= 6:
                    break

        for sub in (subtopics or [])[:6]:
            s_clean = sub.strip()
            if s_clean and s_clean.lower() not in seen_terms:
                seen_terms.add(s_clean.lower())
                terminology.append(s_clean)

        code_patterns = re.findall(r"(?:from\s+\S+\s+import\s+\S+|def\s+\w+\(|class\s+\w+|@\w+\.\w+)", source_text or "")[:6]
        return {
            "topic": topic_title,
            "chapter": chapter_title,
            "domain": domain,
            "concepts": concepts[:6],
            "terminology": terminology[:10],
            "subtopics": list(subtopics or []),
            "code_patterns": list(dict.fromkeys(code_patterns)),
            "prerequisites": (notes or {}).get("prerequisites") or [f"Prior concepts from {chapter_title}"],
        }

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
        subtopics: List[str],
        knowledge_map: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, Optional[str], str]:
        """Write a complete, source-grounded lesson. Returns (content, error_message, provider_used)."""
        notes_summary = ""
        if notes:
            concepts = notes.get("key_concepts", [])
            if concepts:
                notes_summary += "Key Concepts:\n" + "\n".join(
                    f"  - {c.get('term', '')}: {c.get('explanation', '')}" for c in concepts[:6]
                ) + "\n"
            defs = notes.get("definitions", [])
            if defs:
                notes_summary += "Definitions:\n" + "\n".join(f"  - {d}" for d in defs[:5]) + "\n"
            pts = notes.get("important_points", [])
            if pts:
                notes_summary += "Important Points:\n" + "\n".join(f"  - {p}" for p in pts[:6]) + "\n"

        if domain == "computer_science" or content_type == "programming":
            example_guidance = (
                "Include a COMPLETE, runnable Python code snippet with ALL imports, defined variables/functions, "
                "zero undefined external placeholders (do not invent undefined `backend_service` objects), sample output, "
                "and line-by-line execution notes. Explicitly mark whether the example is adapted directly from the source or an additional explanatory example."
            )
        elif domain in ("mathematics", "engineering") or content_type == "mathematical":
            example_guidance = (
                "Include a complete step-by-step derivation or numerical calculation with defined variables and final result."
            )
        else:
            example_guidance = (
                "Include a concrete technical scenario tracing inputs, mechanisms, and verified outcomes step by step."
            )

        subtopics_clause = (
            f"Cover EVERY one of these source subtopics explicitly: {', '.join(subtopics)}.\n"
            if subtopics
            else ""
        )

        local_only = model_router.is_local_only()
        if local_only:
            # Hybrid Fast Local Mode: LLM writes the high-value teaching core (~550 tokens),
            # while _finalize_and_validate_content deterministically supplies Learning Objectives,
            # Key Takeaways, and Check Your Understanding from source + interactive cards (~3x faster on CPU).
            system_message = (
                "Senior technical educator. Teach concepts thoroughly from the source excerpt—no filler analogies "
                "('Imagine a city...'), no filenames. Tag sections with [SOURCE-BASED] or [SUPPLEMENTARY EXPLANATION]. "
                "Put Python code ONLY inside ```python fences and sample output in plain ``` fences."
            )
            source_limit = 1400
            target_tokens = 450
            max_attempts = 1
            min_words_accept = 110
            prompt = (
                f"Teach **{topic_title}** (Module: {chapter_title} | {pages_range} | {difficulty.title()})\n"
                f"{subtopics_clause}\n"
                "Write ONLY these 4 sections in order:\n\n"
                "## Introduction\n"
                "[SOURCE-BASED] 3 sentences: what it is, why it matters, where it is used.\n\n"
                "## Core Concepts\n"
                "[SOURCE-BASED] Teach each concept/subtopic clearly with bold terms (`**Term**: explanation`), how it works, comparisons, and 1 inline **Knowledge Check**.\n\n"
                "## Worked Example\n"
                f"[SUPPLEMENTARY EXPLANATION] {example_guidance}\n\n"
                "## Common Mistakes\n"
                "- **Mistake** -> **Why** -> **Fix** (2 bullets).\n\n"
                "Target 340-480 dense, complete words."
            )
        else:
            system_message = (
                "You are a senior technical educator creating a comprehensive, source-grounded lesson strictly based on the supplied source excerpt.\n"
                "CRITICAL ACCURACY & PEDAGOGY RULES:\n"
                "1. Teach concepts completely with definitions, plain-language intuition, technical mechanics, trade-offs, and comparisons — NEVER write a terse keyword list or summary.\n"
                "2. NO generic motivational analogies (never start with 'Imagine a city...', 'Imagine a restaurant...', or 'Think of a house...').\n"
                "3. Distinguish clearly between [SOURCE-BASED] facts from the excerpt, [SUPPLEMENTARY EXPLANATION] examples/walkthroughs added for clarity, and [ADVANCED EXTENSION] beyond-source notes.\n"
                "4. Never invent behavior that code does not perform, never use undefined external placeholders, and never mention filenames (.pdf, .docx) or 'this book'/'the author'.\n"
                "5. Complete EVERY section cleanly through Check Your Understanding — never stop mid-sentence or leave unclosed code fences."
            )
            if settings.GROQ_API_KEY:
                word_rule = "Write 280-380 focused, complete words. Keep code examples short (<=10 lines) so every section finishes cleanly."
                source_limit = 1400
                target_tokens = 600
                max_attempts = 2
                min_words_accept = 80
            else:
                word_rule = "Write 750-1250 words with rich technical depth, step-by-step traces, and complete examples."
                source_limit = 4500
                target_tokens = 2000
                max_attempts = 2
                min_words_accept = 120
            prompt = (
                f"Write a comprehensive, technically accurate lesson on: **{topic_title}**\n"
                f"Course: {course_title} | Module: {chapter_title} | Level: {difficulty.title()} | Source: {pages_range}\n"
                f"{subtopics_clause}\n"
                "Use these EXACT markdown headings in this exact order, and mark sections/examples with [SOURCE-BASED], [SUPPLEMENTARY EXPLANATION], or [ADVANCED EXTENSION]:\n\n"
                f"# {topic_title}\n\n"
                "## Learning Objectives\n"
                "- 3-5 measurable action-verb objectives (e.g. Differentiate, Implement, Trace) tied directly to the concepts taught.\n\n"
                "## Introduction\n"
                "[SOURCE-BASED] Concise technical overview: what the concept is, why it matters, where it is used, and how it connects to surrounding topics.\n\n"
                "## Core Concepts\n"
                "[SOURCE-BASED] Teach EVERY concept and subtopic thoroughly using complete prose paragraphs and structured comparisons (NOT just a bullet list): definition, simple explanation, technical mechanics, why it is needed, advantages/limitations, and comparison with related concepts.\n"
                "Include a brief inline **Knowledge Check** question + answer right after the main concepts.\n\n"
                "## Worked Example\n"
                f"[SUPPLEMENTARY EXPLANATION] {example_guidance}\n"
                "Include a numbered step-by-step execution trace showing inputs, processing, and outputs.\n\n"
                "## Real-World Application\n"
                "[SUPPLEMENTARY EXPLANATION] Trace a realistic software workflow end-to-end (components, responsibilities, data flow, inputs/outputs, and failure cases).\n\n"
                "## Common Mistakes\n"
                "- **Mistake**: What goes wrong -> **Why**: Root cause -> **Correct Approach**: Fix.\n\n"
                "## Key Takeaways\n"
                "- 4-5 concrete technical takeaways summarizing the concepts taught (do not copy Learning Objectives).\n\n"
                "## Check Your Understanding\n"
                "2-3 specific technical check questions with brief verified answers.\n\n"
                "---\n"
                f"- {word_rule}\n"
            )

        if notes_summary:
            prompt += f"\nExtracted Notes:\n{notes_summary}\n"
        elif knowledge_map and (knowledge_map.get("terminology") or knowledge_map.get("concepts")):
            km_terms = ", ".join((knowledge_map.get("terminology") or [])[:8])
            if km_terms:
                prompt += f"\nKey Source Terms to Teach: {km_terms}\n"
        if source_text.strip():
            prompt += f"\nSource Material ({pages_range}):\n{source_text[:source_limit]}"

        last_error: Optional[str] = None
        for attempt in range(max_attempts):
            try:
                res = await model_router.generate(
                    prompt=prompt,
                    task_type="lesson_content",
                    temperature=0.35,
                    max_tokens=target_tokens,
                    system_prompt=system_message,
                )
                content = (res.get("content") or "").strip()
                provider = str(res.get("provider_used") or "unknown")
                if content and len(content.split()) >= min_words_accept:
                    return content, None, provider
                last_error = f"Content too short on attempt {attempt + 1}: {len(content.split())} words"
                logger.warning(f"Lesson generation attempt {attempt + 1} too short for '{topic_title}'")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Lesson generation attempt {attempt + 1} failed for '{topic_title}': {e}")

        return "", last_error, "none"

    @classmethod
    def _finalize_and_validate_content(
        cls,
        content: str,
        topic_title: str,
        chapter_title: str,
        pages_range: str,
        source_text: str,
        subtopics: List[str],
    ) -> tuple[str, Dict[str, Any]]:
        """Close dangling fences/mid-sentence clips, validate Python examples via AST, and check completeness."""
        cleaned = content.strip()

        # 1. Close unclosed markdown code fence if model stopped inside a code block
        if cleaned.count("```") % 2 == 1:
            cleaned += "\n```"

        # 2. Repair mid-sentence truncation cleanly (does not rewrite educational prose)
        last_line = cleaned.splitlines()[-1].strip() if cleaned.splitlines() else ""
        if last_line and not last_line.startswith("#") and not last_line.endswith((".", "!", "?", "`", ":", ")", "]")):
            cleaned = cleaned.rstrip(",;:- ") + "."

        # 3. Prepend measurable, topic-specific Learning Objectives when omitted
        if "## Learning Objectives" not in cleaned:
            action_verbs = ("Differentiate", "Explain", "Trace", "Apply", "Evaluate")
            obj_items: List[str] = []
            for idx, s in enumerate((subtopics or [])[:3]):
                verb = action_verbs[idx % len(action_verbs)]
                obj_items.append(
                    f"- {verb} how **{s}** works in **{topic_title}** ({pages_range})."
                )
            if len(obj_items) < 3:
                defaults = [
                    f"- Define the core principles and purpose of **{topic_title}** ({pages_range}).",
                    f"- Trace a concrete example demonstrating **{topic_title}** step by step.",
                    f"- Identify and avoid common pitfalls when applying **{topic_title}**.",
                ]
                obj_items.extend(defaults[: 3 - len(obj_items)])
            header = f"# {topic_title}\n\n## Learning Objectives\n\n" + "\n".join(obj_items) + "\n\n"
            cleaned = header + cleaned

        # 4. Auto-complete trailing Key Takeaways / Check Your Understanding from source sentences (avoid repeating Core Concepts verbatim)
        if "## Key Takeaways" not in cleaned:
            src_sents = [
                " ".join(s.split()).strip()
                for s in re.split(r"(?<=[.!?])\s+", (source_text or "").strip())
                if 35 <= len(s.strip()) <= 160
            ]
            bullets = [f"- {s.rstrip('.')}." for s in src_sents[:3]]
            if not bullets:
                bullets = [
                    f"- **{topic_title}** builds directly on the concepts covered in {chapter_title} ({pages_range}).",
                ]
            cleaned += "\n\n## Key Takeaways\n\n" + "\n".join(bullets)

        if "## Check Your Understanding" not in cleaned:
            focus_term = (subtopics[0] if subtopics else topic_title)
            cleaned += (
                "\n\n## Check Your Understanding\n\n"
                f"1. **What problem does {focus_term} solve in {topic_title}?** Review the Core Concepts and Worked Example above.\n"
                f"2. **What happens if {topic_title} is misapplied?** Check the Common Mistakes section for the root cause and fix.\n"
            )

        missing_sections = [
            sec for sec in (
                "## Learning Objectives",
                "## Introduction",
                "## Core Concepts",
                "## Key Takeaways",
                "## Check Your Understanding",
            )
            if sec not in cleaned
        ]

        # 4. Validate Python fenced code blocks with ast.parse & flag undefined external placeholders
        code_valid = True
        code_blocks = re.findall(r"```python\n(.*?)```", cleaned, flags=re.DOTALL)
        for blk in code_blocks:
            if "```" in blk:
                continue
            try:
                ast.parse(blk)
            except SyntaxError:
                code_valid = False

        # Subtopic coverage telemetry
        lower_body = cleaned.lower()
        covered = [s for s in subtopics if any(tok in lower_body for tok in re.findall(r"[a-z0-9]{3,}", s.lower()))]

        checks = {
            "passed": len(missing_sections) == 0 and code_valid,
            "missing_sections": missing_sections,
            "python_syntax_valid": code_valid,
            "subtopics_total": len(subtopics),
            "subtopics_covered": len(covered),
            "word_count": len(cleaned.split()),
        }
        return cleaned, checks

    @staticmethod
    def _extract_summary(content: str, topic_title: str) -> str:
        intro_match = re.search(r"## Introduction\n+(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if intro_match:
            intro = intro_match.group(1).strip()
            first_sentence = re.split(r"[.!?]\s", intro)[0]
            if len(first_sentence) > 25:
                return first_sentence.strip().rstrip(".") + "."
        return f"Focused technical guide to {topic_title} grounded in source concepts, complete examples, and practice."

    @staticmethod
    def _extract_takeaways(content: str) -> List[str]:
        takeaways_match = re.search(r"## Key Takeaways\n+(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if not takeaways_match:
            return []
        section = takeaways_match.group(1).strip()
        bullets = re.findall(r"[-*]\s+(.+)", section)
        return [b.strip() for b in bullets[:6] if len(b.strip()) > 10]

    @staticmethod
    def _extract_objectives(content: str, topic_title: str) -> List[str]:
        match = re.search(r"## Learning Objectives\n+(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if match:
            bullets = re.findall(r"(?:[-*]|\d+\.)\s+(.+)", match.group(1).strip())
            clean = [b.strip() for b in bullets[:5] if len(b.strip()) > 8]
            if clean:
                return clean
        return [f"Explain and apply the technical mechanisms of {topic_title}"]

    @staticmethod
    def _extract_printed_pages(passages: List[Dict[str, Any]], source_pages: List[int]) -> List[str]:
        labels: List[str] = []
        for p in passages or []:
            lbl = str(p.get("printed_page") or p.get("page_number") or "").strip()
            if lbl and lbl not in labels:
                labels.append(lbl)
        if not labels:
            labels = [str(p) for p in sorted(set(source_pages or []))]
        def _sort_key(val: str) -> tuple[int, str]:
            return (0, f"{int(val):08d}") if val.isdigit() else (1, val)
        return sorted(set(labels), key=_sort_key)

    @staticmethod
    def _extract_structured_sections(content: str) -> Dict[str, Any]:
        headings = re.findall(r"^##\s+(.+)$", content, flags=re.MULTILINE)
        toc = [
            {
                "title": h.strip(),
                "slug": re.sub(r"[^a-z0-9]+", "-", h.strip().lower()).strip("-"),
            }
            for h in headings
        ]
        return {
            "toc": toc,
            "has_code": "```" in content,
            "has_mermaid": "```mermaid" in content,
            "word_count": len(content.split()),
        }
