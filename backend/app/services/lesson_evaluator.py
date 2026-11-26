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
    ) -> Dict[str, Any]:
        reasons: List[str] = []
        lower = (lesson_content or "").lower()
        words = len((lesson_content or "").split())

        # 1. Source accuracy (25 pts)
        src_pts = 25.0
        if not ("[SOURCE-BASED]" in lesson_content or "[SUPPLEMENTARY EXPLANATION]" in lesson_content):
            src_pts -= 5.0
            reasons.append("Missing [SOURCE-BASED] / [SUPPLEMENTARY EXPLANATION] grounding tags")
        found_forbidden = [ph for ph in FORBIDDEN_PHRASES if ph in lower]
        if found_forbidden:
            src_pts -= 10.0
            reasons.append(f"Forbidden/filler phrases found: {found_forbidden[:3]}")
        if source_text:
            src_terms = set(re.findall(r"\b[a-z]{5,}\b", source_text.lower()))
            if src_terms:
                overlap = sum(1 for t in list(src_terms)[:30] if t in lower)
                ratio = overlap / min(30, len(src_terms))
                if ratio < 0.2:
                    src_pts -= 10.0
                    reasons.append(f"Low source terminology alignment ({ratio:.0%})")
        src_pts = max(0.0, round(src_pts, 1))

        # 2. Concept coverage (20 pts)
        subs = subtopics or []
        if subs:
            covered = [s for s in subs if any(tok in lower for tok in re.findall(r"[a-z0-9]{3,}", s.lower()))]
            cov_pts = round((len(covered) / len(subs)) * 20.0, 1)
            if len(covered) < len(subs):
                reasons.append(f"Subtopics covered: {len(covered)}/{len(subs)}")
        else:
            topic_toks = re.findall(r"[a-z0-9]{3,}", topic_title.lower())
            hits = sum(1 for tok in topic_toks if tok in lower)
            cov_pts = round((hits / max(1, len(topic_toks))) * 20.0, 1)

        # 3. Explanation quality (15 pts) — substance + prose balance, not raw word count
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
        if words >= 320:
            exp_pts += 2.0
        elif words < 200:
            reasons.append(f"Explanation too brief ({words} words)")
        exp_pts = min(15.0, round(exp_pts, 1))

        # 4. Technical correctness (15 pts)
        tech_pts = 0.0
        if "## Learning Objectives" in lesson_content:
            tech_pts += 5.0
        if "## Key Takeaways" in lesson_content:
            tech_pts += 5.0
        if "## Check Your Understanding" in lesson_content or "**Knowledge Check**" in lesson_content:
            tech_pts += 5.0
        if tech_pts < 15.0:
            reasons.append("Missing structured Learning Objectives / Key Takeaways / Knowledge Check")

        # 5. Code/example validity (15 pts)
        code_blocks = re.findall(r"```python\n(.*?)```", lesson_content or "", flags=re.DOTALL)
        code_valid_all = True
        code_reports: List[Dict[str, Any]] = []
        if code_blocks:
            for blk in code_blocks:
                rep = CodeValidationPipeline.validate_code_block(blk, run_in_sandbox=True)
                code_reports.append(rep.to_dict())
                if not rep.valid:
                    code_valid_all = False
                    reasons.append(f"Code validation failed: {rep.error_message}")
            code_pts = 15.0 if code_valid_all else 5.0
        else:
            # Conceptual non-code topics still get partial example credit if Worked Example exists
            code_pts = 10.0 if "## Worked Example" in lesson_content else 4.0
            if "## Worked Example" not in lesson_content:
                reasons.append("Missing ## Worked Example")

        # 6. Exercise relevance (10 pts)
        ex_list = exercises or []
        if ex_list:
            topic_words = set(re.findall(r"[a-z0-9]{3,}", topic_title.lower()))
            relevant = 0
            for ex in ex_list:
                blob = f"{ex.get('title', '')} {ex.get('prompt', '')}".lower()
                if any(w in blob for w in topic_words) or len(blob) > 40:
                    relevant += 1
            ex_pts = round((relevant / len(ex_list)) * 10.0, 1)
        else:
            ex_pts = 8.0  # Evaluated standalone before ExerciseAgent runs

        total = round(src_pts + cov_pts + exp_pts + tech_pts + code_pts + ex_pts, 1)
        critical_failures: List[str] = []
        if not code_valid_all:
            critical_failures.append("invalid_code_block")
        if found_forbidden:
            critical_failures.append("forbidden_filler_phrases")
        if src_pts < 15.0:
            critical_failures.append("low_source_accuracy")

        passed = total >= 70.0 and len(critical_failures) == 0
        return {
            "total_score": total,
            "passed": passed,
            "critical_failures": critical_failures,
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
