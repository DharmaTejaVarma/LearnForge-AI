import asyncio
import json
import re
from typing import List, Dict, Any, Optional
from app.ai.rag.retriever import RAGRetriever
from app.ai.models.model_router import model_router
from app.core.sanitizer import EducationalSanitizer
from app.core.logging import logger


class QuestionAgent:
    """Generates grounded MCQ, True/False, and Short-Answer assessment questions from verified material."""

    @staticmethod
    async def generate_questions(
        user_id: int,
        document_id: Optional[int] = None,
        document_ids: Optional[List[int]] = None,
        count: int = 5,
        difficulty: str = "medium",
        question_type: str = "mcq",
    ) -> List[Dict[str, Any]]:
        q_type = (question_type or "mcq").lower()
        if q_type not in ("mcq", "true_false", "short_answer", "mixed"):
            q_type = "mcq"

        # 1. Retrieve essential curriculum passages (offloaded so embedding/Chroma never blocks event loop)
        passages = await asyncio.to_thread(
            RAGRetriever.retrieve,
            query="Crucial principles, definitions, methodologies, problems, and core mechanics",
            user_id=user_id,
            document_id=document_id,
            document_ids=document_ids,
            top_k=min(count + 4, 12),
        )
        # If semantic meta-query didn't match literal document vocabulary, sample document pages directly
        if not passages:
            target_id = document_id or (document_ids[0] if document_ids else None)
            if target_id:
                passages = await asyncio.to_thread(
                    RAGRetriever.get_chunks_for_pages,
                    document_id=target_id,
                    user_id=user_id,
                    page_start=1,
                    page_end=25,
                    max_chunks=min(count + 4, 12),
                )

        clean_context = "\n\n".join(
            EducationalSanitizer.sanitize_educational_text(p["text"]) for p in passages
        ).strip()
        if not clean_context:
            return []

        difficulty_guidance = {
            "easy": "Focus on factual recall, definitions, and direct identification of key terms.",
            "medium": "Test application of concepts, relationships between ideas, and analytical understanding.",
            "hard": "Challenge synthesis of multiple concepts, evaluation of scenarios, and complex reasoning.",
        }.get(difficulty, "Test application of concepts and analytical understanding.")

        type_instruction = {
            "mcq": 'Provide multiple-choice questions (`"question_type": "mcq"`) with EXACTLY 4 plausible options labeled A, B, C, D.',
            "true_false": 'Provide True/False statements (`"question_type": "true_false"`) with `"options": ["True", "False"]` and `"correct_answer"` equal to `"True"` or `"False"`.',
            "short_answer": 'Provide concise short-answer questions (`"question_type": "short_answer"`) with `"options": []` and `"correct_answer"` containing the concise key answer (1-12 words).',
            "mixed": 'Mix `"mcq"` (4 options A-D), `"true_false"` (options ["True", "False"]), and `"short_answer"` (options []) questions.',
        }[q_type]

        prompt = (
            f"You are a university examination board evaluator creating a {difficulty}-level quiz.\n"
            f"Generate up to {count} high-quality, concept-testing questions strictly from the text below.\n"
            f"Difficulty guidance: {difficulty_guidance}\n"
            f"Question format: {type_instruction}\n\n"
            "STRICT RULES:\n"
            "1. Every question MUST be directly supported by the text below — never invent unrelated topics.\n"
            "2. Provide a clear explanation citing the underlying principle.\n"
            "3. NEVER mention filenames, file extensions (.pdf, .docx), chunk IDs, or internal storage paths.\n"
            "4. Respond ONLY with a valid JSON array matching:\n"
            '[{"question_text": "...", "question_type": "mcq", "options": ["A. ...", "B. ...", "C. ...", "D. ..."], "correct_answer": "A. ...", "explanation": "..."}]\n\n'
            f"Course Material:\n{clean_context[:3500]}"
        )

        valid_questions: List[Dict[str, Any]] = []
        seen_q_texts = set()
        try:
            res = await model_router.generate(
                prompt=prompt,
                task_type="mcq",
                temperature=0.3,
                format="json",
            )
            content = res.get("content", "").strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            parsed = json.loads(content)
            if isinstance(parsed, list):
                for q in parsed:
                    if not isinstance(q, dict):
                        continue
                    item_type = str(q.get("question_type") or ("mcq" if q_type == "mixed" else q_type)).lower()
                    if item_type == "true_false" and not q.get("options"):
                        q["options"] = ["True", "False"]
                    elif item_type == "short_answer":
                        q["options"] = []
                    q["question_type"] = item_type

                    norm_qt = re.sub(r"\s+", " ", str(q.get("question_text", "")).lower().strip())
                    if norm_qt and norm_qt not in seen_q_texts and EducationalSanitizer.validate_quiz_question(q):
                        seen_q_texts.add(norm_qt)
                        valid_questions.append({
                            "question_text": str(q["question_text"]).strip(),
                            "question_type": item_type,
                            "options": q.get("options", []),
                            "correct_answer": str(q["correct_answer"]).strip(),
                            "explanation": str(q.get("explanation", "Supported by the study material.")).strip(),
                            "difficulty": difficulty,
                        })
        except Exception as e:
            logger.warning(f"AI question generation fallback: {e}")

        # 3. Grounded extraction from retrieved passages when LLM returns fewer questions
        if len(valid_questions) < count:
            fallback_qs = QuestionAgent._generate_heuristic_questions(
                clean_context, count - len(valid_questions) + 2, difficulty, q_type
            )
            for fq in fallback_qs:
                if len(valid_questions) >= count:
                    break
                norm_qt = re.sub(r"\s+", " ", fq["question_text"].lower().strip())
                if norm_qt not in seen_q_texts and EducationalSanitizer.validate_quiz_question(fq):
                    seen_q_texts.add(norm_qt)
                    valid_questions.append(fq)

        return valid_questions[:count]

    @staticmethod
    def _generate_heuristic_questions(
        text: str,
        target_count: int,
        difficulty: str,
        question_type: str = "mcq",
    ) -> List[Dict[str, Any]]:
        """Synthesizes grounded questions directly from retrieved study sentences (never unrelated trivia)."""
        questions: List[Dict[str, Any]] = []
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 30]
        def_re = re.compile(
            r"\b([A-Za-z][A-Za-z0-9\s\(\)\-]{2,40}?)\s+(?:is defined as|is a|is an|is the|are|refers to|represents|manages|enables|provides)\s+(.+)",
            re.IGNORECASE,
        )

        for idx, s in enumerate(sentences):
            effective_type = question_type
            if question_type == "mixed":
                effective_type = ("mcq", "true_false", "short_answer")[idx % 3]

            match = def_re.search(s)
            if match:
                term = match.group(1).strip(" :,-")
                def_body = match.group(2).strip()
            else:
                words = re.findall(r"\b[A-Za-z][A-Za-z0-9\-]{3,}\b", s)
                if len(words) < 5:
                    continue
                term = " ".join(words[:2])
                def_body = s

            if len(term) < 3 or len(def_body) < 15 or EducationalSanitizer.contains_metadata_leak(s):
                continue

            if effective_type == "true_false":
                q = {
                    "question_text": f"True or False: According to the study material, {s[:180]}",
                    "question_type": "true_false",
                    "options": ["True", "False"],
                    "correct_answer": "True",
                    "explanation": f"Verified directly in your study material: {s[:160]}",
                    "difficulty": difficulty,
                }
            elif effective_type == "short_answer":
                q = {
                    "question_text": f"Briefly explain the role or definition of '{term}' based on your study material.",
                    "question_type": "short_answer",
                    "options": [],
                    "correct_answer": def_body[:120],
                    "explanation": f"From the study material: {s[:160]}",
                    "difficulty": difficulty,
                }
            else:
                correct_text = f"{def_body[:95].rstrip('.')}."
                raw_opts = [
                    correct_text,
                    f"It operates independently without interacting with '{term}'.",
                    "It is an unrelated mechanism excluded from this topic.",
                    "It prevents structured processing within this domain.",
                ]
                shift = idx % len(raw_opts)
                rotated = raw_opts[shift:] + raw_opts[:shift]
                labels = ("A", "B", "C", "D")
                labeled_opts = [f"{labels[i]}. {txt}" for i, txt in enumerate(rotated)]
                correct_opt = labeled_opts[rotated.index(correct_text)]
                q = {
                    "question_text": f"Which statement accurately describes '{term}' in the study material?",
                    "question_type": "mcq",
                    "options": labeled_opts,
                    "correct_answer": correct_opt,
                    "explanation": f"In the study material: {s[:160]}",
                    "difficulty": difficulty,
                }

            if EducationalSanitizer.validate_quiz_question(q):
                questions.append(q)
            if len(questions) >= target_count:
                break

        return questions
