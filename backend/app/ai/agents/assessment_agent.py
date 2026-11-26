import re
from typing import List, Dict, Any

_LETTER_PREFIX_RE = re.compile(r"^\s*([a-d])(?:[\.\)\:]\s*|\s*$)", re.IGNORECASE)
_STOP_WORDS = {"the", "a", "an", "is", "are", "was", "were", "of", "in", "to", "and", "or", "for", "with", "that", "this"}


class AssessmentAgent:
    """Scores MCQ, True/False, and Short-Answer quiz attempts and identifies weak concepts."""

    @staticmethod
    def is_correct(correct_answer: str, selected: str, question_type: str = "mcq") -> bool:
        """Check whether a student's selected or typed answer matches the reference answer."""
        if not selected or not correct_answer:
            return False

        s = selected.strip().lower()
        c = correct_answer.strip().lower()

        # Exact normalized match (handles full option text, True/False, etc.)
        if s == c:
            return True

        q_type = (question_type or "mcq").lower()
        if q_type == "true_false":
            t_vals = {"true", "t", "yes", "correct"}
            f_vals = {"false", "f", "no", "incorrect"}
            if c in t_vals and s in t_vals:
                return True
            if c in f_vals and s in f_vals:
                return True
            return False

        if q_type == "short_answer":
            c_tokens = [w for w in re.findall(r"\b[a-z0-9]{3,}\b", c) if w not in _STOP_WORDS]
            s_tokens = set(re.findall(r"\b[a-z0-9]{3,}\b", s))
            if not c_tokens:
                return c in s
            overlap = sum(1 for tok in c_tokens if tok in s_tokens)
            return overlap / len(c_tokens) >= 0.5

        # MCQ: compare leading option letter ("A. Foo" vs "A" or "A. Foo") safely via regex
        m_s = _LETTER_PREFIX_RE.match(s)
        m_c = _LETTER_PREFIX_RE.match(c)
        if m_s and m_c:
            return m_s.group(1).lower() == m_c.group(1).lower()

        # Strip optional letter prefixes and compare text bodies
        s_body = re.sub(r"^[a-d][\.\)\:]\s*", "", s).strip()
        c_body = re.sub(r"^[a-d][\.\)\:]\s*", "", c).strip()
        return bool(s_body and c_body and s_body == c_body)

    @staticmethod
    def _extract_concept_label(question_text: str, q_id: int) -> str:
        clean_q = re.sub(r"\s+", " ", (question_text or "").strip())
        # Extract quoted concept if present (e.g. 'Polymorphism')
        quoted = re.search(r"['\"]([^'\"]{3,60})['\"]", clean_q)
        if quoted:
            return quoted.group(1).strip()
        return clean_q[:80] if clean_q else f"Question {q_id}"

    @staticmethod
    def evaluate_quiz(
        questions: List[Dict[str, Any]],
        student_answers: Dict[int, str],
    ) -> Dict[str, Any]:
        total = len(questions)
        if total == 0:
            return {
                "score_percentage": 0.0,
                "correct_count": 0,
                "total": 0,
                "feedback": "No questions.",
                "incorrect_topics": [],
                "weak_concepts": [],
            }

        correct_count = 0
        incorrect_topics: List[str] = []

        for q in questions:
            q_id = q["id"]
            selected = student_answers.get(q_id, "") or student_answers.get(str(q_id), "")
            q_type = q.get("question_type", "mcq")
            if AssessmentAgent.is_correct(q["correct_answer"], selected, question_type=q_type):
                correct_count += 1
            else:
                incorrect_topics.append(AssessmentAgent._extract_concept_label(q.get("question_text", ""), q_id))

        score = round((correct_count / total) * 100, 2)

        if score >= 90:
            feedback = f"Exceptional! You scored {score}% — outstanding mastery of the material."
        elif score >= 80:
            feedback = f"Great work! You scored {score}% — solid understanding with minor gaps to review."
        elif score >= 60:
            feedback = f"Good effort ({score}%). Review the questions you missed to reinforce understanding."
        elif score >= 40:
            feedback = f"Needs improvement ({score}%). We recommend re-reading the relevant lessons and practicing flashcards."
        else:
            feedback = f"Score: {score}%. Review the lesson materials thoroughly and use flashcards before reattempting."

        # Preserve deduplicated weak concepts
        dedup_weak = list(dict.fromkeys(incorrect_topics))[:5]
        return {
            "score_percentage": score,
            "correct_count": correct_count,
            "total": total,
            "feedback": feedback,
            "incorrect_topics": dedup_weak[:3],
            "weak_concepts": dedup_weak,
        }
