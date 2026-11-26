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

        # Extract compact structured notes when cloud model is active
        notes_json: Dict[str, Any] = {}
        if source_text.strip() and not model_router.is_local_only():
            notes_json = await cls._extract_notes(source_text, topic_title, domain)

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

        # Validate Python code blocks (AST + undefined identifiers + isolated sandbox) with targeted single-block repair
        code_blocks = re.findall(r"```python\n(.*?)```", content, flags=re.DOTALL)
        if code_blocks and (domain == "computer_science" or content_type == "programming"):
            for blk in code_blocks:
                if "```" in blk or not blk.strip():
                    continue
                chk = CodeValidationPipeline.validate_code_block(blk, run_in_sandbox=True)
                if not chk.valid:
                    repaired, rep_chk = await CodeValidationPipeline.repair_code_block(
                        blk, chk.error_message or "Validation failed", topic_title, max_attempts=1
                    )
                    if rep_chk.valid and repaired != blk:
                        content = content.replace(blk, repaired, 1)
                        validation_checks["python_syntax_valid"] = True
                        validation_checks["code_repaired"] = True

        eval_report = LessonEvaluator.evaluate(
            topic_title=topic_title,
            lesson_content=content,
            source_text=source_text,
            subtopics=subtopics or [],
        )
        validation_ms = round((time.perf_counter() - t_val_start) * 1000, 1)

        summary = cls._extract_summary(content, topic_title)
        takeaways = cls._extract_takeaways(content)
        objectives = cls._extract_objectives(content, topic_title)
        word_count = len(content.split())

        structured_sections = cls._extract_structured_sections(content)
        interactive = InteractiveLearningBuilder.build(
            topic_title=topic_title,
            chapter_title=chapter_title,
            course_title=course_title,
            lesson_content=content,
            source_text=source_text,
            subtopics=subtopics or [],
            chapter_order=chapter_order,
            domain=domain,
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
            "validation_passed": validation_checks.get("passed", True),
            "validation_checks": validation_checks,
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
            source_limit = 1800
            target_tokens = 580
            max_attempts = 1
            min_words_accept = 120
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

        # 3. Prepend Learning Objectives deterministically when Hybrid Fast Local Mode omits them
        if "## Learning Objectives" not in cleaned:
            obj_items = [
                f"- Explain the core mechanisms and trade-offs of **{s}** in {chapter_title}."
                for s in (subtopics or [])[:3]
            ]
            if len(obj_items) < 3:
                obj_items.extend([
                    f"- Define and apply the key principles of **{topic_title}** ({pages_range}).",
                    f"- Trace inputs, processing, and outputs in a complete **{topic_title}** workflow.",
                    f"- Identify and fix common implementation mistakes related to **{topic_title}**.",
                ][: 3 - len(obj_items)])
            header = f"# {topic_title}\n\n## Learning Objectives\n\n" + "\n".join(obj_items) + "\n\n"
            cleaned = header + cleaned

        # 4. Auto-complete trailing Key Takeaways / Check Your Understanding if local model stopped early after Core Concepts & Example
        if "## Key Takeaways" not in cleaned:
            bold_defs = re.findall(r"\*\*([^*]{3,40})\*\*[:\-–]\s*([^\n.]{15,120})", cleaned)
            bullets = [f"- **{t.strip()}**: {d.strip().rstrip('.')}." for t, d in bold_defs[:4]]
            if not bullets:
                bullets = [
                    f"- **{topic_title}** defines explicit contracts and boundaries covered in {chapter_title} ({pages_range}).",
                    "- Separating validation, core logic, and error signaling prevents silent runtime failures.",
                ]
            cleaned += "\n\n## Key Takeaways\n\n" + "\n".join(bullets)

        if "## Check Your Understanding" not in cleaned:
            cleaned += (
                "\n\n## Check Your Understanding\n\n"
                f"1. **How does {topic_title} structure inputs and outputs?** By enforcing explicit contracts and clear responsibilities covered in {chapter_title}.\n"
                f"2. **What mistake should you avoid when applying {topic_title}?** Mixing unrelated concerns or skipping edge-case error checks.\n"
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
        if labels:
            return labels
        return [str(p) for p in (source_pages or [])]

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
