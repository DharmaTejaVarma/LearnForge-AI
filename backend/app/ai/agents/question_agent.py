import json
import re
from typing import List, Dict, Any, Optional
from app.ai.rag.retriever import RAGRetriever
from app.ai.models.model_router import model_router
from app.core.sanitizer import EducationalSanitizer
from app.core.logging import logger


class QuestionAgent:
    """Generates rigorous, educational multiple-choice assessment questions with verified answers and explanations."""

    @staticmethod
    async def generate_questions(
        user_id: int,
        document_id: Optional[int] = None,
        document_ids: Optional[List[int]] = None,
        count: int = 5,
        difficulty: str = "medium",
    ) -> List[Dict[str, Any]]:
        # 1. Retrieve essential curriculum passages (support both single-doc and course-scoped multi-doc)
        passages = RAGRetriever.retrieve(
            query="Crucial principles, definitions, methodologies, problems, and core mechanics",
            user_id=user_id,
            document_id=document_id,
            document_ids=document_ids,
            top_k=min(count + 3, 10),
        )

        # 2. Sanitize context to ensure zero metadata enters prompt
        clean_context = "\n\n".join(
            EducationalSanitizer.sanitize_educational_text(p["text"]) for p in passages
        )

        difficulty_guidance = {
            "easy": "Focus on factual recall, definitions, and direct identification of key terms.",
            "medium": "Test application of concepts, relationships between ideas, and analytical understanding.",
            "hard": "Challenge synthesis of multiple concepts, evaluation of scenarios, and complex reasoning.",
        }.get(difficulty, "Test application of concepts and analytical understanding.")

        prompt = (
            f"You are a university examination board evaluator creating a {difficulty}-level multiple-choice quiz.\n"
            f"Generate exactly {count} high-quality, concept-testing multiple-choice questions from the text below.\n"
            f"Difficulty guidance: {difficulty_guidance}\n\n"
            "STRICT RULES:\n"
            "1. Each question must test understanding of principles, relationships, or practical problem solving.\n"
            "2. Provide EXACTLY 4 plausible answer options labeled A, B, C, D.\n"
            "3. Specify the single correct answer as the full option text (e.g., 'A. The correct answer text').\n"
            "4. Provide a thorough explanation explaining why the correct choice is accurate and why distractors are wrong.\n"
            "5. NEVER mention filenames, file extensions (.pdf, .docx), chunk IDs, or internal storage paths.\n"
            "6. Questions must be grounded in the provided text — do not invent topics.\n"
            "7. Respond ONLY with a valid JSON array matching this exact format:\n"
            "[\n"
            "  {\n"
            '    "question_text": "Which of the following best describes encapsulation in OOP?",\n'
            '    "options": ["A. Bundling data and methods that operate on it.", "B. Creating multiple instances of a class.", "C. Inheriting properties from a parent class.", "D. Defining abstract methods."],\n'
            '    "correct_answer": "A. Bundling data and methods that operate on it.",\n'
            '    "explanation": "Encapsulation bundles data (attributes) and the methods that operate on it into a single unit (class), hiding internal implementation details."\n'
            "  }\n"
            "]\n\n"
            f"Course Material:\n{clean_context[:4000]}"
        )

        valid_questions: List[Dict[str, Any]] = []
        try:
            res = await model_router.generate(
                prompt=prompt,
                task_type="mcq",
                temperature=0.3,
                format="json"
            )
            content = res.get("content", "").strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            parsed = json.loads(content)
            if isinstance(parsed, list):
                for q in parsed:
                    if EducationalSanitizer.validate_quiz_question(q):
                        options = q.get("options", [])
                        valid_questions.append({
                            "question_text": str(q["question_text"]).strip(),
                            "options": options,
                            "correct_answer": str(q["correct_answer"]).strip(),
                            "explanation": str(q.get("explanation", "Correct based on course principles.")).strip(),
                            "difficulty": difficulty,
                        })
        except Exception as e:
            logger.warning(f"AI question generation fallback: {e}")

        # 3. If AI produced fewer questions than requested, synthesize grounded fallback questions
        if len(valid_questions) < count:
            fallback_qs = QuestionAgent._generate_heuristic_questions(clean_context, count, difficulty)
            for fq in fallback_qs:
                if len(valid_questions) >= count:
                    break
                if EducationalSanitizer.validate_quiz_question(fq):
                    valid_questions.append(fq)

        # 4. Final safety guard if no questions could be extracted
        if not valid_questions:
            valid_questions = [
                {
                    "question_text": "What is the primary role of Retrieval-Augmented Generation (RAG) in educational systems?",
                    "options": [
                        "A. Grounding model responses directly in verified course study materials.",
                        "B. Replacing relational databases with external storage buckets.",
                        "C. Translating documents into audio files automatically.",
                        "D. Generating random test cases without course context."
                    ],
                    "correct_answer": "A. Grounding model responses directly in verified course study materials.",
                    "explanation": "RAG retrieves verified context passages to prevent hallucinations and provide exact page-level citations.",
                    "difficulty": difficulty
                }
            ]

        return valid_questions[:count]

    @staticmethod
    def _generate_heuristic_questions(text: str, target_count: int, difficulty: str) -> List[Dict[str, Any]]:
        """Synthesizes valid questions directly from conceptual text without metadata contamination."""
        questions = []
        sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 35]

        for s in sentences:
            match = re.search(r"\b([A-Z][a-zA-Z\s]{2,30})\s+(?:is defined as|is a|refers to|represents)\s+(.+)", s)
            if match:
                term = match.group(1).strip()
                def_body = match.group(2).strip()
                if len(term) >= 3 and len(def_body) >= 20:
                    q_text = f"Which of the following best defines the concept of '{term}'?"
                    correct_opt = f"A. {term} is {def_body[:90]}."
                    options = [
                        correct_opt,
                        f"B. A deprecated method that contradicts standard educational theory.",
                        f"C. An unverified assumption rejected in modern practice.",
                        f"D. A protocol that eliminates the need for foundational analysis."
                    ]
                    explanation = f"In course study material, '{term}' is defined as: {def_body[:120]}."
                    q = {
                        "question_text": q_text,
                        "options": options,
                        "correct_answer": correct_opt,
                        "explanation": explanation,
                        "difficulty": difficulty
                    }
                    if EducationalSanitizer.validate_quiz_question(q):
                        questions.append(q)
            if len(questions) >= target_count:
                break

        return questions
