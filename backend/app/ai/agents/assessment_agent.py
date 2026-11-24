from typing import List, Dict, Any


class AssessmentAgent:
    """Scores quiz attempts, analyzes incorrect responses, and generates feedback."""

    @staticmethod
    def is_correct(correct_answer: str, selected: str) -> bool:
        """Check whether a selected answer matches the correct answer."""
        if not selected:
            return False
        s = selected.strip().lower()
        c = correct_answer.strip().lower()
        # Full match
        if s == c:
            return True
        # First character match (e.g., "A" == "A. Full text")
        if s and c and s[0] == c[0]:
            return True
        return False

    @staticmethod
    def evaluate_quiz(
        questions: List[Dict[str, Any]],
        student_answers: Dict[int, str],
    ) -> Dict[str, Any]:
        total = len(questions)
        if total == 0:
            return {"score_percentage": 0.0, "correct_count": 0, "total": 0, "feedback": "No questions."}

        correct_count = 0
        incorrect_topics = []

        for q in questions:
            q_id = q["id"]
            selected = student_answers.get(q_id, "")
            if AssessmentAgent.is_correct(q["correct_answer"], selected):
                correct_count += 1
            else:
                incorrect_topics.append(q.get("question_text", f"Question {q_id}"))

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

        return {
            "score_percentage": score,
            "correct_count": correct_count,
            "total": total,
            "feedback": feedback,
            "incorrect_topics": incorrect_topics[:3]
        }
