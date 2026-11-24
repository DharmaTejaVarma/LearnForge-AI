import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.learning_tools import TutorConversation
from app.db.models.course import Course, Lesson
from app.db.models.document import UploadedDocument
from app.schemas.learning_tools import TutorChatRequest, TutorChatResponse, TutorConversationItem
from app.ai.agents.tutor_agent import TutorAgent
from app.core.exceptions import NotFoundException, ForbiddenException
from app.core.logging import logger

class TutorService:
    """Orchestrates AI Tutor conversation flow, validation, RAG context, and SQLite history persistence."""

    @staticmethod
    async def chat(db: AsyncSession, user_id: int, req: TutorChatRequest) -> TutorChatResponse:
        course_title: Optional[str] = None
        lesson_title: Optional[str] = None
        target_doc_ids: List[int] = []

        # 1. Validate Course Context & Ownership
        if req.course_id:
            course_res = await db.execute(select(Course).where(Course.id == req.course_id))
            course = course_res.scalars().first()
            if not course:
                raise NotFoundException("Specified course not found")
            if course.user_id != user_id:
                raise ForbiddenException("Unauthorized course access")
            course_title = course.title
            if course.document_id:
                target_doc_ids.append(course.document_id)

        # 2. Validate Document Context & Ownership
        if req.document_id:
            doc_res = await db.execute(select(UploadedDocument).where(UploadedDocument.id == req.document_id))
            doc = doc_res.scalars().first()
            if not doc:
                raise NotFoundException("Specified document not found")
            if doc.user_id != user_id:
                raise ForbiddenException("Unauthorized document access")
            if doc.id not in target_doc_ids:
                target_doc_ids.append(doc.id)

        # 3. Validate Lesson Context
        if req.lesson_id:
            lesson_res = await db.execute(select(Lesson).where(Lesson.id == req.lesson_id))
            lesson = lesson_res.scalars().first()
            if lesson:
                lesson_title = lesson.title

        # 4. Resolve or generate conversation_id session
        conversation_id = req.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"

        # 5. Fetch Recent Conversation History for Context Continuity
        history_query = (
            select(TutorConversation)
            .where(TutorConversation.user_id == user_id)
            .order_by(TutorConversation.id.desc())
            .limit(6)
        )
        if req.conversation_id:
            history_query = history_query.where(TutorConversation.conversation_id == req.conversation_id)
        elif req.course_id:
            history_query = history_query.where(TutorConversation.course_id == req.course_id)
        elif req.document_id:
            history_query = history_query.where(TutorConversation.document_id == req.document_id)

        history_res = await db.execute(history_query)
        past_conversations = list(reversed(history_res.scalars().all()))

        formatted_history = []
        for conv in past_conversations:
            formatted_history.append({"role": "user", "content": conv.question})
            formatted_history.append({"role": "assistant", "content": conv.answer})

        # 6. Execute Socratic Tutor Agent with Intent Routing & RAG
        agent_res = await TutorAgent.respond_to_query(
            question=req.question,
            user_id=user_id,
            document_id=req.document_id,
            document_ids=target_doc_ids,
            course_id=req.course_id,
            course_title=course_title,
            lesson_id=req.lesson_id,
            lesson_title=lesson_title,
            history=formatted_history,
        )

        # 7. Persist turn into SQLite database
        new_conv = TutorConversation(
            user_id=user_id,
            document_id=req.document_id,
            course_id=req.course_id,
            conversation_id=conversation_id,
            intent=agent_res.get("intent", "educational_question"),
            question=req.question,
            answer=agent_res["answer"],
            citations=agent_res.get("citations", []),
        )
        db.add(new_conv)
        await db.commit()
        await db.refresh(new_conv)

        return TutorChatResponse(
            answer=agent_res["answer"],
            citations=agent_res.get("citations", []),
            provider_used=agent_res.get("provider_used", "unknown"),
            latency_ms=agent_res.get("latency_ms", 0.0),
            conversation_id=conversation_id,
            intent=agent_res.get("intent"),
        )

    @staticmethod
    async def get_history(
        db: AsyncSession,
        user_id: int,
        conversation_id: Optional[str] = None,
        course_id: Optional[int] = None,
        document_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[TutorConversationItem]:
        query = (
            select(TutorConversation)
            .where(TutorConversation.user_id == user_id)
            .order_by(TutorConversation.id.asc())
            .limit(limit)
        )
        if conversation_id:
            query = query.where(TutorConversation.conversation_id == conversation_id)
        else:
            if course_id:
                query = query.where(TutorConversation.course_id == course_id)
            if document_id:
                query = query.where(TutorConversation.document_id == document_id)

        res = await db.execute(query)
        records = res.scalars().all()

        return [TutorConversationItem.model_validate(r) for r in records]

    @staticmethod
    async def clear_history(
        db: AsyncSession,
        user_id: int,
        conversation_id: Optional[str] = None,
        course_id: Optional[int] = None,
        document_id: Optional[int] = None,
    ) -> Dict[str, str]:
        stmt = delete(TutorConversation).where(TutorConversation.user_id == user_id)
        if conversation_id:
            stmt = stmt.where(TutorConversation.conversation_id == conversation_id)
        if course_id:
            stmt = stmt.where(TutorConversation.course_id == course_id)
        if document_id:
            stmt = stmt.where(TutorConversation.document_id == document_id)

        await db.execute(stmt)
        await db.commit()
        return {"message": "Tutor conversation history cleared successfully"}

    @staticmethod
    async def get_suggested_questions(
        db: AsyncSession,
        user_id: int,
        course_id: Optional[int] = None,
        lesson_id: Optional[int] = None,
    ) -> List[str]:
        """Generates dynamic suggested questions tailored to the active course or lesson."""
        if lesson_id:
            l_res = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
            lesson = l_res.scalars().first()
            if lesson:
                return [
                    f"Explain '{lesson.title}' in simple terms.",
                    f"Give me a practical real-world example of '{lesson.title}'.",
                    f"What are the key takeaways from this lesson?",
                    f"Test my understanding of '{lesson.title}' with a question.",
                ]

        if course_id:
            c_res = await db.execute(select(Course).where(Course.id == course_id))
            course = c_res.scalars().first()
            if course:
                suggestions = [
                    f"What are the foundational concepts in {course.title}?",
                    f"Give me an intuitive real-world overview of this course.",
                    f"Summarize the main learning objectives.",
                    f"What should I study first to master this material?",
                ]
                if course.learning_objectives and len(course.learning_objectives) > 0:
                    suggestions[2] = f"Explain: {course.learning_objectives[0][:60]}..."
                return suggestions

        return [
            "Explain the first concept from my study materials.",
            "Give me a practical example of a key concept.",
            "Summarize the main topics in my uploaded document.",
            "Quiz me with a question to test my understanding.",
        ]
