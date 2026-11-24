import json
import re
from typing import List, Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import NotFoundException, ForbiddenException, BadRequestException
from app.core.logging import logger
from app.core.sanitizer import EducationalSanitizer
from app.core.course_validator import CourseValidator
from app.db.models.course import Course, Chapter, Topic, Lesson
from app.db.models.document import UploadedDocument
from app.schemas.course import CourseGenerateRequest, CourseResponse, CourseDetailResponse, LessonResponse
from app.ai.rag.retriever import RAGRetriever
from app.ai.rag.document_loader import DocumentLoader
from app.ai.rag.text_cleaner import TextCleaner
from app.ai.agents.document_agent import DocumentAgent
from app.ai.agents.content_agent import ContentAgent
from app.ai.agents.lesson_agent import LessonAgent
from app.services.lesson_quality import LessonQualityGate

class CourseService:
    @staticmethod
    async def generate_course(
        db: AsyncSession,
        user_id: int,
        req: CourseGenerateRequest,
    ) -> CourseDetailResponse:
        # 1. Fetch document and check ownership
        doc_res = await db.execute(
            select(UploadedDocument).where(UploadedDocument.id == req.document_id)
        )
        doc = doc_res.scalars().first()
        if not doc:
            raise NotFoundException("Document not found")
        if doc.user_id != user_id:
            raise ForbiddenException("Unauthorized document access")

        # 2. Extract pages and generate document blueprint via DocumentAgent
        pages = DocumentLoader.load_document(doc.file_path, doc.mime_type)
        cleaned_pages = TextCleaner.clean_document_pages(pages)
        doc_blueprint = DocumentAgent.analyze_document(cleaned_pages, doc.original_filename)

        # 2b. Extract document structure (TOC/headings) and persist
        extracted_sections = DocumentLoader.extract_structure(doc.file_path, doc.mime_type)
        if extracted_sections:
            doc.structure = extracted_sections
            await db.commit()

        # 3. Synthesize structured syllabus via ContentAgent
        outline = await ContentAgent.synthesize_course_outline(
            doc_blueprint=doc_blueprint,
            target_chapters_count=req.target_chapters_count or 3,
            difficulty=req.difficulty_level or "intermediate",
            sections=extracted_sections,
        )

        final_title = outline.get("title", doc_blueprint.get("clean_title", "Course Study Guide"))
        final_description = outline.get("description", f"Comprehensive study course for {final_title}.")
        final_objectives = outline.get("learning_objectives", [])
        chapters_data = outline.get("chapters", [])

        # 4. Insert Course, Chapters, Topics & Detailed Lessons
        course = Course(
            user_id=user_id,
            document_id=doc.id,
            title=final_title,
            description=final_description,
            difficulty_level=req.difficulty_level or "intermediate",
            estimated_duration_hours=max(3, len(chapters_data) * 2),
            learning_objectives=final_objectives,
        )
        db.add(course)
        await db.commit()
        await db.refresh(course)

        for c_idx, chap_data in enumerate(chapters_data):
            chap_title = chap_data.get("title", f"Chapter {c_idx + 1}")
            chap_desc = chap_data.get("description", f"Exploration of key principles in {chap_title}.")
            ch_page_start = chap_data.get("page_start")
            ch_page_end = chap_data.get("page_end")

            chapter = Chapter(
                course_id=course.id,
                title=chap_title,
                description=chap_desc,
                order_index=c_idx,
            )
            db.add(chapter)
            await db.commit()
            await db.refresh(chapter)

            topics_list = chap_data.get("topics", [])
            for t_idx, topic_entry in enumerate(topics_list):
                if isinstance(topic_entry, dict):
                    t_title = topic_entry.get("title", f"Topic {t_idx + 1}")
                    t_page_start = topic_entry.get("page_start", ch_page_start)
                    t_page_end = topic_entry.get("page_end", ch_page_end)
                else:
                    t_title = str(topic_entry)
                    t_page_start = ch_page_start
                    t_page_end = ch_page_end

                t_title = EducationalSanitizer.clean_title(t_title, fallback_prefix=f"Topic {t_idx + 1}")

                topic = Topic(
                    chapter_id=chapter.id,
                    title=t_title,
                    order_index=t_idx,
                )
                db.add(topic)
                await db.commit()
                await db.refresh(topic)

                # Retrieve topic-specific context using page range if available, else query search
                if t_page_start is not None and t_page_end is not None:
                    t_passages = RAGRetriever.get_chunks_for_pages(
                        document_id=doc.id,
                        user_id=user_id,
                        page_start=t_page_start,
                        page_end=t_page_end,
                        max_chunks=12,
                    )
                else:
                    t_passages = RAGRetriever.retrieve(
                        query=f"{t_title} {chap_title}",
                        user_id=user_id,
                        document_id=doc.id,
                        top_k=6,
                    )

                source_pages = sorted(list(set(p.get("page_number", 1) for p in t_passages))) if t_passages else (
                    list(range(t_page_start, t_page_end + 1)) if t_page_start and t_page_end else [1]
                )

                # Generate lesson via LessonAgent
                lesson_payload = await LessonAgent.generate_lesson(
                    topic_title=t_title,
                    chapter_title=chap_title,
                    course_title=final_title,
                    passages=t_passages,
                    source_pages=source_pages,
                    doc_blueprint=doc_blueprint,
                    difficulty=req.difficulty_level or "intermediate",
                    page_start=t_page_start,
                    page_end=t_page_end,
                )

                content = lesson_payload.get("content", "")
                gen_status = lesson_payload.get("generation_status", "ready")
                gen_error = lesson_payload.get("generation_error")
                quality_score = 1.0

                # Quality gate check
                if content and gen_status == "ready":
                    source_text = "\n\n".join(p.get("text", "") for p in t_passages) if t_passages else ""
                    passed, reasons = LessonQualityGate.check(content, source_text)
                    if not passed:
                        logger.warning(f"Quality gate check failed for '{t_title}': {reasons}. Retrying...")
                        retry_payload = await LessonAgent.generate_lesson(
                            topic_title=t_title,
                            chapter_title=chap_title,
                            course_title=final_title,
                            passages=t_passages,
                            source_pages=source_pages,
                            doc_blueprint=doc_blueprint,
                            difficulty=req.difficulty_level or "intermediate",
                            page_start=t_page_start,
                            page_end=t_page_end,
                        )
                        retry_content = retry_payload.get("content", "")
                        if retry_content:
                            retry_passed, retry_reasons = LessonQualityGate.check(retry_content, source_text)
                            if retry_passed:
                                lesson_payload = retry_payload
                                content = retry_content
                                quality_score = 1.0
                            else:
                                quality_score = max(0.2, 1.0 - (len(retry_reasons) * 0.15))
                        else:
                            gen_status = "failed"
                            gen_error = "; ".join(reasons)

                lesson = Lesson(
                    topic_id=topic.id,
                    title=t_title,
                    content=content,
                    summary=lesson_payload.get("summary", ""),
                    key_takeaways=lesson_payload.get("key_takeaways", []),
                    source_pages=source_pages,
                    is_completed=False,
                    page_start=t_page_start,
                    page_end=t_page_end,
                    generation_status=gen_status,
                    quality_score=quality_score,
                    generation_error=gen_error,
                )
                db.add(lesson)

        await db.commit()
        return await CourseService.get_course_detail(db, user_id, course.id)

    @staticmethod
    async def list_user_courses(db: AsyncSession, user_id: int) -> List[CourseResponse]:
        query = select(Course).where(Course.user_id == user_id).order_by(Course.id.desc())
        res = await db.execute(query)
        courses = res.scalars().all()
        return [CourseResponse.model_validate(c) for c in courses]

    @staticmethod
    async def get_course_detail(db: AsyncSession, user_id: int, course_id: int) -> CourseDetailResponse:
        query = (
            select(Course)
            .where(Course.id == course_id)
            .options(
                selectinload(Course.chapters)
                .selectinload(Chapter.topics)
                .selectinload(Topic.lesson)
            )
        )
        res = await db.execute(query)
        course = res.scalars().first()

        if not course:
            raise NotFoundException("Course not found")
        if course.user_id != user_id:
            raise ForbiddenException("Unauthorized course access")

        return CourseDetailResponse.model_validate(course)

    @staticmethod
    async def delete_course(db: AsyncSession, user_id: int, course_id: int) -> dict:
        course_res = await db.execute(select(Course).where(Course.id == course_id))
        course = course_res.scalars().first()
        if not course:
            raise NotFoundException("Course not found")
        if course.user_id != user_id:
            raise ForbiddenException("Unauthorized course deletion")

        await db.delete(course)
        await db.commit()
        return {"message": "Course deleted successfully", "course_id": course_id}

    @staticmethod
    async def get_lesson(db: AsyncSession, user_id: int, lesson_id: int) -> LessonResponse:
        query = (
            select(Lesson)
            .where(Lesson.id == lesson_id)
            .options(
                selectinload(Lesson.topic)
                .selectinload(Topic.chapter)
                .selectinload(Chapter.course)
            )
        )
        res = await db.execute(query)
        lesson = res.scalars().first()

        if not lesson:
            raise NotFoundException("Lesson not found")
        if lesson.topic.chapter.course.user_id != user_id:
            raise ForbiddenException("Unauthorized lesson access")

        return LessonResponse.model_validate(lesson)

    @staticmethod
    async def toggle_lesson_completion(db: AsyncSession, user_id: int, lesson_id: int) -> LessonResponse:
        lesson_res = await db.execute(
            select(Lesson)
            .where(Lesson.id == lesson_id)
            .options(selectinload(Lesson.topic).selectinload(Topic.chapter).selectinload(Chapter.course))
        )
        lesson = lesson_res.scalars().first()
        if not lesson:
            raise NotFoundException("Lesson not found")
        if lesson.topic.chapter.course.user_id != user_id:
            raise ForbiddenException("Unauthorized lesson access")

        lesson.is_completed = not lesson.is_completed
        await db.commit()
        await db.refresh(lesson)
        return LessonResponse.model_validate(lesson)

    @staticmethod
    async def regenerate_lesson(db: AsyncSession, user_id: int, lesson_id: int) -> LessonResponse:
        query = (
            select(Lesson)
            .where(Lesson.id == lesson_id)
            .options(
                selectinload(Lesson.topic)
                .selectinload(Topic.chapter)
                .selectinload(Chapter.course)
                .selectinload(Course.document)
            )
        )
        res = await db.execute(query)
        lesson = res.scalars().first()
        if not lesson:
            raise NotFoundException("Lesson not found")
        course = lesson.topic.chapter.course
        if course.user_id != user_id:
            raise ForbiddenException("Unauthorized lesson access")

        lesson.generation_status = "generating"
        lesson.generation_error = None
        await db.commit()
        await db.refresh(lesson)

        doc = course.document
        t_title = lesson.title
        chap_title = lesson.topic.chapter.title
        course_title = course.title
        page_start = lesson.page_start
        page_end = lesson.page_end

        t_passages = []
        if doc:
            if page_start is not None and page_end is not None:
                t_passages = RAGRetriever.get_chunks_for_pages(
                    document_id=doc.id,
                    user_id=user_id,
                    page_start=page_start,
                    page_end=page_end,
                    max_chunks=12,
                )
            else:
                t_passages = RAGRetriever.retrieve(
                    query=f"{t_title} {chap_title}",
                    user_id=user_id,
                    document_id=doc.id,
                    top_k=6,
                )

        source_pages = sorted(list(set(p.get("page_number", 1) for p in t_passages))) if t_passages else (
            lesson.source_pages or [1]
        )
        doc_blueprint = {"clean_title": course_title, "subject_domain": "general"}

        lesson_payload = await LessonAgent.generate_lesson(
            topic_title=t_title,
            chapter_title=chap_title,
            course_title=course_title,
            passages=t_passages,
            source_pages=source_pages,
            doc_blueprint=doc_blueprint,
            difficulty=course.difficulty_level,
            page_start=page_start,
            page_end=page_end,
        )

        content = lesson_payload.get("content", "")
        gen_status = lesson_payload.get("generation_status", "ready")
        gen_error = lesson_payload.get("generation_error")
        quality_score = 1.0

        if content and gen_status == "ready":
            source_text = "\n\n".join(p.get("text", "") for p in t_passages) if t_passages else ""
            passed, reasons = LessonQualityGate.check(content, source_text)
            if not passed:
                quality_score = max(0.2, 1.0 - (len(reasons) * 0.15))

        lesson.content = content
        lesson.summary = lesson_payload.get("summary", lesson.summary)
        lesson.key_takeaways = lesson_payload.get("key_takeaways", lesson.key_takeaways)
        lesson.source_pages = source_pages
        lesson.generation_status = gen_status
        lesson.quality_score = quality_score
        lesson.generation_error = gen_error

        await db.commit()
        await db.refresh(lesson)
        return LessonResponse.model_validate(lesson)
