import time
from typing import List, Dict, Any, Optional
from app.ai.rag.retriever import RAGRetriever
from app.ai.models.model_router import model_router
from app.ai.agents.intent_detector import IntentDetector, TutorIntent
from app.core.sanitizer import EducationalSanitizer
from app.core.logging import logger

class TutorAgent:
    """Interactive Socratic AI Tutor with intelligent intent routing, conversation memory, and grounded citations."""

    @staticmethod
    async def respond_to_query(
        question: str,
        user_id: int,
        document_id: Optional[int] = None,
        document_ids: Optional[List[int]] = None,
        course_id: Optional[int] = None,
        course_title: Optional[str] = None,
        lesson_id: Optional[int] = None,
        lesson_title: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()

        # Step 1: Detect intent before doing any document retrieval
        intent_res = IntentDetector.detect_intent(
            message=question,
            history=history,
            course_title=course_title,
        )
        intent = intent_res.intent
        logger.info(f"Tutor query '{question[:40]}...' classified as intent: {intent} (conf: {intent_res.confidence})")

        # Step 2: Handle Greetings & General Conversation without RAG
        if intent in (TutorIntent.GREETING, TutorIntent.GENERAL_CONVERSATION):
            answer_text = IntentDetector.get_conversational_response(
                intent=intent,
                query=question,
                course_title=course_title,
            )
            elapsed = (time.perf_counter() - start_time) * 1000
            return {
                "answer": answer_text,
                "citations": [],
                "provider_used": "rule_based:conversational",
                "latency_ms": round(elapsed, 2),
                "intent": intent.value,
            }

        # Step 3: Handle Unrelated Queries
        if intent == TutorIntent.UNRELATED:
            answer_text = IntentDetector.get_conversational_response(
                intent=intent,
                query=question,
                course_title=course_title,
            )
            elapsed = (time.perf_counter() - start_time) * 1000
            return {
                "answer": answer_text,
                "citations": [],
                "provider_used": "rule_based:scope_guard",
                "latency_ms": round(elapsed, 2),
                "intent": intent.value,
            }

        # Step 4: For Educational Questions & Follow-ups, execute Course-Scoped RAG
        effective_query = intent_res.contextualized_query

        # Scope documents
        target_doc_ids = list(document_ids) if document_ids else []
        if document_id and document_id not in target_doc_ids:
            target_doc_ids.append(document_id)

        passages = RAGRetriever.retrieve(
            query=effective_query,
            user_id=user_id,
            document_id=document_id if not target_doc_ids else None,
            document_ids=target_doc_ids if target_doc_ids else None,
            top_k=4,
            min_similarity=0.22,
        )

        # Clean passages and filter out low-confidence matches
        clean_passages = []
        for p in passages:
            sanitized_txt = EducationalSanitizer.sanitize_educational_text(p["text"])
            if sanitized_txt and len(sanitized_txt) > 25:
                clean_passages.append({
                    "text": sanitized_txt,
                    "page_number": p["page_number"],
                    "document_id": p.get("document_id", 0),
                    "document_title": p.get("document_title", course_title or "Study Material"),
                    "similarity_score": p["similarity_score"],
                })

        max_similarity = max((cp["similarity_score"] for cp in clean_passages), default=0.0)
        has_relevant_context = len(clean_passages) > 0 and max_similarity >= 0.28

        # Build context blocks
        if has_relevant_context:
            context_blocks = [
                f"[Excerpt from {cp['document_title']}, Page {cp['page_number']}]:\n{cp['text']}"
                for cp in clean_passages
            ]
            context_str = "\n\n".join(context_blocks)
        else:
            context_str = "No matching excerpts found in your uploaded course materials for this query."

        # Step 5: Format Conversation History
        history_formatted = ""
        if history:
            history_lines = []
            for msg in history[-6:]:
                sender = "Student" if msg.get("role") in ("user", "student") else "Tutor"
                history_lines.append(f"{sender}: {msg.get('content', '')}")
            history_formatted = "Recent Conversation History:\n" + "\n".join(history_lines) + "\n\n"

        # Step 6: Formulate Socratic System Prompt
        clean_course = course_title or "Course"
        system_prompt = (
            f"You are LearnForge Tutor, a friendly, encouraging, and deeply pedagogical Socratic AI educator for {clean_course}. "
            "Your objective is to guide students to genuine understanding, not just reciting facts.\n\n"
            "Pedagogical Guidelines:\n"
            "1. Explain difficult concepts in clear, beginner-friendly language first, followed by technical precision.\n"
            "2. Provide practical examples, intuitive real-world analogies, and clean code or formulas where relevant.\n"
            "3. Ground explanations strictly in verified study material excerpts. Cite source pages naturally (e.g. '[Page 4]').\n"
            "4. Honest Boundaries: If the student's question is NOT covered in the provided study material, state honestly:\n"
            "   'I couldn't find sufficient information about this topic in your selected course material. "
            "   However, from general educational principles: [brief helpful explanation]. Please verify with your course textbook or instructor.'\n"
            "   NEVER claim information comes from the document when it was not in the excerpts.\n"
            "5. Maintain continuity: use recent conversation history to answer follow-up questions accurately.\n"
            "6. NEVER mention internal filenames, file extensions (.pdf, .docx), chunk IDs, UUIDs, or storage paths.\n"
            "7. Conclude with a thought-provoking Socratic question to check the student's understanding."
        )

        user_prompt = (
            f"{history_formatted}"
            f"Active Context: Course = {clean_course}"
            f"{f', Lesson = {lesson_title}' if lesson_title else ''}\n"
            f"Student Question: {question}\n\n"
            f"Verified Study Material Excerpts:\n"
            f"{context_str}\n\n"
            "Provide your structured educational explanation:"
        )

        try:
            ai_res = await model_router.generate(
                prompt=user_prompt,
                task_type="tutor_socratic",
                system_prompt=system_prompt,
                temperature=0.4,
                max_tokens=1000,
            )
            raw_answer = ai_res["content"].strip()
            # Clean any accidental metadata leakage
            if not EducationalSanitizer.contains_metadata_leak(raw_answer) and len(raw_answer) > 40:
                answer_text = raw_answer
            else:
                answer_text = EducationalSanitizer.sanitize_educational_text(raw_answer)
            provider = ai_res["provider_used"]
            latency = ai_res["latency_ms"]
        except Exception as e:
            logger.warning(f"AI generation failed for tutor: {e}")
            if has_relevant_context:
                top_page = clean_passages[0]["page_number"]
                clean_name = clean_passages[0]["document_title"]
                top_excerpt = clean_passages[0]["text"][:280].strip()
                answer_text = (
                    f"### Key Educational Insights ([Page {top_page}])\n\n"
                    f"Regarding your question about **{question}**, your study material on **{clean_name}** highlights:\n\n"
                    f"> \"{top_excerpt}...\"\n\n"
                    f"In practical terms, this concept emphasizes systematic understanding of foundational principles. "
                    f"Connect these ideas with the core objectives of your module.\n\n"
                    f"**Reflective Socratic Question**: How do you see this principle connecting with the practical examples in your course?"
                )
            else:
                answer_text = (
                    f"I couldn't find sufficient information about **'{question}'** in your selected course material.\n\n"
                    f"In general academic terms, this topic focuses on foundational mechanics and applied methods. "
                    f"To explore course-specific details, please ensure you have selected the appropriate learning material.\n\n"
                    f"**Reflective Question**: Would you like to connect this inquiry with any of your active course modules?"
                )
            provider = "heuristic:fallback"
            latency = (time.perf_counter() - start_time) * 1000

        # Construct clean, deduplicated citations
        citations = []
        seen_pages = set()
        if has_relevant_context:
            for cp in clean_passages:
                page_key = (cp["document_id"], cp["page_number"])
                if page_key not in seen_pages:
                    seen_pages.add(page_key)
                    citations.append({
                        "document_id": cp["document_id"],
                        "filename": cp["document_title"],
                        "page_number": cp["page_number"],
                        "similarity_score": cp["similarity_score"],
                    })
                if len(citations) >= 3:
                    break

        return {
            "answer": answer_text,
            "citations": citations,
            "provider_used": provider,
            "latency_ms": round(latency, 2),
            "intent": intent.value,
        }
