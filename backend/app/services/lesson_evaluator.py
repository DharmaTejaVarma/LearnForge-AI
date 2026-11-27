"""100-Point Educational Quality Evaluator for generated lessons and exercises.

Rubric (100 points total):
  - Source accuracy:       25 pts
  - Concept coverage:      20 pts
  - Explanation quality:   15 pts
  - Technical correctness: 15 pts
  - Code/example validity: 15 pts
  - Exercise relevance:    10 pts
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.ai.rag.text_cleaner import FORBIDDEN_PHRASES
from app.services.code_validator import CodeValidationPipeline


class LessonEvaluator:
    """Evaluates generated lessons against the 100-point rubric with explicit failure reasons."""

    @classmethod
    def evaluate(
        cls,
        topic_title: str,
        lesson_content: str,
        source_text: str = "",
        subtopics: Optional[List[str]] = None,
        exercises: Optional[List[Dict[str, Any]]] = None,
        learning_objectives: Optional[List[str]] = None,
        technical_validation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        reasons: List[str] = []
        repair_suggestions: List[str] = []
        lower = (lesson_content or "").lower()
        words = len((lesson_content or "").split())

        # 1. Source accuracy (25 pts) — deterministic sorted term overlap including 3+ char tech terms
        src_pts = 25.0
        has_source_tag = "[SOURCE-BASED]" in lesson_content
        has_supp_tag = "[SUPPLEMENTARY EXPLANATION]" in lesson_content
        if not (has_source_tag or has_supp_tag):
            src_pts -= 5.0
            reasons.append("Missing [SOURCE-BASED] / [SUPPLEMENTARY EXPLANATION] grounding tags")
        found_forbidden = [ph for ph in FORBIDDEN_PHRASES if ph in lower]
        if found_forbidden:
            src_pts -= 10.0
            reasons.append(f"Forbidden/filler phrases found: {found_forbidden[:3]}")
        source_ratio = 1.0
        if source_text:
            src_terms = sorted(set(re.findall(r"\b[a-z0-9]{3,}\b", source_text.lower())))[:40]
            if src_terms:
                overlap = sum(1 for t in src_terms if re.search(rf"\b{re.escape(t)}\b", lower))
                source_ratio = overlap / len(src_terms)
                if source_ratio < 0.15:
                    src_pts -= 14.0
                    reasons.append(f"Low source terminology alignment ({source_ratio:.0%})")
                    repair_suggestions.append("Incorporate exact terminology and examples from the assigned source pages.")
                elif source_ratio < 0.25:
                    src_pts -= 7.0
                    reasons.append(f"Moderate source terminology alignment ({source_ratio:.0%})")
        src_pts = max(0.0, round(src_pts, 1))

        # 2. Concept & objective coverage (20 pts)
        subs = subtopics or []
        if subs:
            covered = [
                s for s in subs
                if any(re.search(rf"\b{re.escape(tok)}\b", lower) for tok in re.findall(r"[a-z0-9]{3,}", s.lower()))
            ]
            cov_pts = round((len(covered) / len(subs)) * 20.0, 1)
            if len(covered) < len(subs):
                reasons.append(f"Subtopics covered: {len(covered)}/{len(subs)}")
        else:
            topic_toks = re.findall(r"[a-z0-9]{3,}", topic_title.lower())
            hits = sum(1 for tok in topic_toks if re.search(rf"\b{re.escape(tok)}\b", lower))
            cov_pts = round((hits / max(1, len(topic_toks))) * 20.0, 1)

        if learning_objectives:
            obj_hits = 0
            for obj in learning_objectives:
                obj_toks = [t for t in re.findall(r"[a-z0-9]{4,}", obj.lower()) if t not in {"explain", "define", "trace", "apply", "differentiate"}]
                if not obj_toks or any(re.search(rf"\b{re.escape(t)}\b", lower) for t in obj_toks):
                    obj_hits += 1
            if obj_hits < len(learning_objectives):
                reasons.append(f"Learning objectives aligned: {obj_hits}/{len(learning_objectives)}")

        # 3. Explanation quality (15 pts)
        exp_pts = 0.0
        if "## Introduction" in lesson_content:
            exp_pts += 4.0
        else:
            reasons.append("Missing ## Introduction")
        if "## Core Concepts" in lesson_content:
            exp_pts += 6.0
        else:
            reasons.append("Missing ## Core Concepts")
        if "## Common Mistakes" in lesson_content or "## Real-World Application" in lesson_content:
            exp_pts += 3.0
        if words >= 260:
            exp_pts += 2.0
        elif words < 150:
            reasons.append(f"Explanation too brief ({words} words)")
        exp_pts = min(15.0, round(exp_pts, 1))

        # 4. Technical correctness & structure (15 pts)
        tech_pts = 0.0
        if "## Learning Objectives" in lesson_content:
            tech_pts += 4.0
        if "## Key Takeaways" in lesson_content:
            tech_pts += 4.0
        if "## Check Your Understanding" in lesson_content or "**Knowledge Check**" in lesson_content:
            tech_pts += 4.0
        tech_ok = True
        if technical_validation:
            if not technical_validation.get("technical_accuracy_ok", True):
                tech_ok = False
                reasons.append(f"Technical syntax/API errors: {technical_validation.get('syntax_errors')}")
            elif technical_validation.get("deprecated_warnings"):
                reasons.append(f"Deprecation notes: {technical_validation['deprecated_warnings'][0]}")
                tech_pts += 2.0
            else:
                tech_pts += 3.0
        else:
            tech_pts += 3.0
        tech_pts = min(15.0, round(tech_pts, 1))

        # 5. Code/example validity (15 pts) — AST + scope check without re-spawning slow subprocesses
        code_blocks = re.findall(r"```python[ \t]*\r?\n(.*?)```", lesson_content or "", flags=re.DOTALL)
        code_valid_all = True
        code_reports: List[Dict[str, Any]] = []
        if code_blocks:
            for blk in code_blocks:
                if "```" in blk or not blk.strip():
                    continue
                rep = CodeValidationPipeline.validate_code_block(blk, run_in_sandbox=False)
                code_reports.append(rep.to_dict())
                if not rep.valid:
                    code_valid_all = False
                    reasons.append(f"Code validation failed: {rep.error_message}")
            code_pts = 15.0 if code_valid_all else 5.0
        else:
            code_pts = 10.0 if "## Worked Example" in lesson_content else 4.0
            if "## Worked Example" not in lesson_content:
                reasons.append("Missing ## Worked Example")

        # 6. Exercise relevance (10 pts) — strict keyword alignment (no len > 40 bypass)
        ex_list = exercises or []
        unrelated_exercises = False
        if ex_list:
            topic_words = set(re.findall(r"[a-z0-9]{3,}", f"{topic_title} {' '.join(subs)}".lower()))
            relevant = 0
            for ex in ex_list:
                blob = f"{ex.get('title', '')} {ex.get('prompt', '')}".lower()
                if any(re.search(rf"\b{re.escape(w)}\b", blob) for w in topic_words):
                    relevant += 1
            ex_pts = round((relevant / len(ex_list)) * 10.0, 1)
            if relevant == 0:
                unrelated_exercises = True
                reasons.append("Exercises do not reference the lesson topic")
        else:
            ex_pts = 8.0

        total = round(src_pts + cov_pts + exp_pts + tech_pts + code_pts + ex_pts, 1)
        critical_failures: List[str] = []
        if not code_valid_all:
            critical_failures.append("invalid_code_block")
        if found_forbidden:
            critical_failures.append("forbidden_filler_phrases")
        if src_pts < 12.0 or (source_text and source_ratio == 0.0 and len(source_text) > 200):
            critical_failures.append("low_source_accuracy")
        if not tech_ok:
            critical_failures.append("technical_inaccuracy")
        if unrelated_exercises:
            critical_failures.append("unrelated_exercises")

        passed = total >= 70.0 and len(critical_failures) == 0
        return {
            "total_score": total,
            "passed": passed,
            "critical_failures": critical_failures,
            "reasons": reasons,
            "repair_suggestions": repair_suggestions,
            "breakdown": {
                "source_accuracy": src_pts,
                "concept_coverage": cov_pts,
                "explanation_quality": exp_pts,
                "technical_correctness": tech_pts,
                "code_validity": code_pts,
                "exercise_relevance": ex_pts,
            },
            "code_reports": code_reports,
            "failure_reasons": reasons,
        }
