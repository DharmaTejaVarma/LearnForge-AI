import asyncio
import sys
from typing import List, Optional, Dict, Any, Set
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ForbiddenException, BadRequestException
from app.core.logging import logger
from app.core.sanitizer import EducationalSanitizer
from app.db.database import AsyncSessionLocal
from app.db.models.course import (
    Course,
    Chapter,
    Topic,
    Lesson,
    LessonExercise,
    ExerciseSubmission,
    CourseAssessment,
    CourseAssessmentAttempt,
    LessonNote,
    GenerationJob,
)
from app.db.models.document import UploadedDocument
from app.schemas.course import (
    CourseGenerateRequest,
    CourseResponse,
    CourseDetailResponse,
    LessonResponse,
    LessonExerciseResponse,
    ExerciseSubmitRequest,
    ExerciseSubmitResponse,
    CodeRunResponse,
    LessonNoteRequest,
    LessonNoteResponse,
    CourseAssessmentResponse,
    AssessmentQuestionItem,
    AssessmentSubmitRequest,
    AssessmentResultResponse,
    GenerationJobResponse,
)
from app.ai.models.model_router import model_router
from app.ai.rag.retriever import RAGRetriever
from app.ai.rag.document_loader import DocumentLoader
from app.ai.rag.text_cleaner import TextCleaner
from app.ai.agents.document_agent import DocumentAgent
from app.ai.agents.content_agent import ContentAgent
from app.ai.agents.lesson_agent import LessonAgent
from app.ai.agents.exercise_agent import ExerciseAgent
from app.services.lesson_quality import LessonQualityGate
from app.services.code_sandbox import execute_python_sandbox

_lesson_gen_locks: Dict[int, asyncio.Lock] = {}
_background_tasks: Set[asyncio.Task] = set()
_active_lesson_ids: Set[int] = set()


def _get_lesson_lock(lesson_id: int) -> asyncio.Lock:
    lock = _lesson_gen_locks.get(lesson_id)
    if lock is None:
        lock = asyncio.Lock()
        _lesson_gen_locks[lesson_id] = lock
    return lock


class CourseService:
    @staticmethod
    def _retrieve_topic_passages(
        document_id: Optional[int],
        user_id: int,
        t_title: str,
        chap_title: str,
        t_page_start: Optional[int],
        t_page_end: Optional[int],
        file_path: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> tuple[List[Dict[str, Any]], List[int]]:
        t_passages: List[Dict[str, Any]] = []
        if document_id is not None:
            if t_page_start is not None and t_page_end is not None:
                t_passages = RAGRetriever.get_chunks_for_pages(
                    document_id=document_id,
                    user_id=user_id,
                    page_start=t_page_start,
                    page_end=t_page_end,
                    max_chunks=12,
                )
            else:
                t_passages = RAGRetriever.retrieve(
                    query=f"{t_title} {chap_title}",
                    user_id=user_id,
                    document_id=document_id,
                    top_k=6,
                )

        # Fallback/enrich from exact source file pages when chunks are sparse or lack printed_page metadata
        if file_path and t_page_start is not None:
            raw_pages = DocumentLoader.extract_page_texts_range(
                file_path, mime_type, t_page_start, t_page_end or t_page_start
            )
            label_map = {p["page_number"]: p.get("printed_page", str(p["page_number"])) for p in raw_pages}
            total_chunk_chars = sum(len(p.get("text", "")) for p in t_passages)
            if total_chunk_chars < 1400 and raw_pages:
                t_passages = [
                    {
                        "text": p["text"],
                        "page_number": p["page_number"],
                        "printed_page": p.get("printed_page", str(p["page_number"])),
                    }
                    for p in raw_pages
                    if p.get("text", "").strip()
                ]
            else:
                for p in t_passages:
                    pn = p.get("page_number")
                    if pn in label_map:
                        p["printed_page"] = label_map[pn]
        elif file_path and t_passages:
            label_map = DocumentLoader.get_page_labels_map(file_path)
            if label_map:
                for p in t_passages:
                    pn = p.get("page_number")
                    if pn in label_map:
                        p["printed_page"] = label_map[pn]

        source_pages = (
            sorted(list(set(p.get("page_number", 1) for p in t_passages)))
            if t_passages
            else (list(range(t_page_start, t_page_end + 1)) if t_page_start and t_page_end else [1])
        )
        return t_passages, source_pages

    @staticmethod
    async def _synthesize_lesson_with_quality_gate(
        t_title: str,
        chap_title: str,
        course_title: str,
        t_passages: List[Dict[str, Any]],
        source_pages: List[int],
        doc_blueprint: Dict[str, Any],
        difficulty: str,
        t_page_start: Optional[int],
        t_page_end: Optional[int],
        subtopics: Optional[List[str]] = None,
        chapter_order: int = 0,
        doc_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        lesson_payload = await LessonAgent.generate_lesson(
            topic_title=t_title,
            chapter_title=chap_title,
            course_title=course_title,
            passages=t_passages,
            source_pages=source_pages,
            doc_blueprint=doc_blueprint,
            difficulty=difficulty,
            page_start=t_page_start,
            page_end=t_page_end,
            subtopics=subtopics,
            chapter_order=chapter_order,
            doc_hash=doc_hash,
        )

        content = lesson_payload.get("content", "")
        gen_status = lesson_payload.get("generation_status", "ready")
        gen_error = lesson_payload.get("generation_error")
        quality_score = 1.0

        if content and gen_status == "ready":
            source_text = "\n\n".join(p.get("text", "") for p in t_passages) if t_passages else ""
            passed, reasons = LessonQualityGate.check(content, source_text, subtopics=subtopics)
            if not passed:
                if not model_router.is_local_only():
                    logger.warning(f"Quality gate check failed for '{t_title}': {reasons}. Retrying...")
                    retry_payload = await LessonAgent.generate_lesson(
                        topic_title=t_title,
                        chapter_title=chap_title,
                        course_title=course_title,
                        passages=t_passages,
                        source_pages=source_pages,
                        doc_blueprint=doc_blueprint,
                        difficulty=difficulty,
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
                else:
                    quality_score = max(0.2, 1.0 - (len(reasons) * 0.15))

        return {
            "content": content,
            "summary": lesson_payload.get("summary", ""),
            "key_takeaways": lesson_payload.get("key_takeaways", []),
            "learning_objectives": lesson_payload.get("learning_objectives", []),
            "prerequisites": lesson_payload.get("prerequisites", []),
            "estimated_minutes": lesson_payload.get("estimated_minutes", 10),
            "structured_sections": lesson_payload.get("structured_sections", {}),
            "printed_pages": lesson_payload.get("printed_pages", [str(p) for p in source_pages]),
            "source_pages": source_pages,
            "generation_status": gen_status,
            "quality_score": quality_score,
            "generation_error": gen_error,
        }

    @staticmethod
    async def _ensure_lesson_exercises(
        db: AsyncSession,
        lesson: Lesson,
        chap_title: str,
        source_text: str = "",
        domain: str = "computer_science",
        content_type: str = "programming",
        difficulty: str = "intermediate",
    ) -> List[LessonExercise]:
        """Ensure interactive exercises exist for a ready lesson; generate once and persist."""
        existing_res = await db.execute(
            select(LessonExercise)
            .where(LessonExercise.lesson_id == lesson.id)
            .order_by(LessonExercise.order_index.asc())
        )
        existing = list(existing_res.scalars().all())
        if existing:
            return existing
        if not lesson.content or lesson.generation_status != "ready":
            return []

        printed = lesson.printed_pages or []
        p_label = (
            f"Book p. {printed[0]}–{printed[-1]}" if len(printed) > 1
            else (f"Book p. {printed[0]}" if printed else "")
        )
        source_ref = f"{chap_title}, {p_label}" if p_label else chap_title

        generated = await ExerciseAgent.generate_lesson_exercises(
            topic_title=lesson.title,
            chapter_title=chap_title,
            lesson_content=lesson.content,
            source_text=source_text,
            domain=domain,
            content_type=content_type,
            difficulty=difficulty,
            key_takeaways=lesson.key_takeaways or [],
            source_reference=source_ref,
        )
        created: List[LessonExercise] = []
        for idx, ex in enumerate(generated):
            row = LessonExercise(
                lesson_id=lesson.id,
                order_index=ex.get("order_index", idx),
                exercise_type=ex.get("exercise_type", "mcq"),
                title=ex.get("title", f"Exercise {idx + 1}"),
                prompt=ex.get("prompt", ""),
                starter_code=ex.get("starter_code"),
                buggy_code=ex.get("buggy_code"),
                options=ex.get("options") or [],
                option_explanations=ex.get("option_explanations") or [],
                correct_answer=ex.get("correct_answer"),
                expected_output=ex.get("expected_output"),
                test_cases=ex.get("test_cases") or [],
                hints=ex.get("hints") or [],
                explanation=ex.get("explanation"),
                difficulty=ex.get("difficulty", difficulty),
            )
            db.add(row)
            created.append(row)
        await db.flush()
        return created

    @staticmethod
    async def _find_cached_lesson(
        db: AsyncSession,
        cache_key: str,
    ) -> Optional[Lesson]:
        """Return a previously synthesized ready lesson with matching cache_key."""
        res = await db.execute(
            select(Lesson)
            .where(
                Lesson.cache_key == cache_key,
                Lesson.generation_status == "ready",
                Lesson.content != "",
            )
            .options(selectinload(Lesson.exercises))
            .limit(1)
        )
        return res.scalars().first()

    @staticmethod
    async def _generate_remaining_lessons_bg(
        lesson_ids: List[int],
        user_id: int,
        doc_blueprint: Dict[str, Any],
        job_id: Optional[int] = None,
    ) -> None:
        """Synthesize queued lessons in parallel (up to MAX_PARALLEL_LESSONS at once)."""
        # Local CPU Ollama runs faster sequentially (avoids CPU thrashing); Groq free-tier 8k TPM runs cleanest at 2
        from app.core.config import settings
        MAX_PARALLEL_LESSONS = 1 if model_router.is_local_only() else (2 if settings.GROQ_API_KEY else 3)
        semaphore = asyncio.Semaphore(MAX_PARALLEL_LESSONS)
        completed_count = 0
        total = len(lesson_ids)

        async def _process_one_lesson(lid: int) -> None:
            nonlocal completed_count
            lock = _get_lesson_lock(lid)
            async with semaphore:
                try:
                    async with lock:
                        # --- Load lesson metadata ---
                        async with AsyncSessionLocal() as session:
                            res = await session.execute(
                                select(Lesson)
                                .where(Lesson.id == lid)
                                .options(
                                    selectinload(Lesson.topic)
                                    .selectinload(Topic.chapter)
                                    .selectinload(Chapter.course)
                                    .selectinload(Course.document)
                                )
                            )
                            lesson = res.scalars().first()
                            if not lesson or (lesson.content and lesson.generation_status == "ready"):
                                completed_count += 1
                                return

                            course = lesson.topic.chapter.course
                            doc_obj = course.document
                            t_title = lesson.title
                            chap_title = lesson.topic.chapter.title
                            chap_order = lesson.topic.chapter.order_index
                            course_title = course.title
                            doc_id = course.document_id
                            difficulty = course.difficulty_level
                            p_start = lesson.page_start
                            p_end = lesson.page_end
                            cache_key = lesson.cache_key
                            subtopics = (lesson.structured_sections or {}).get("subtopics") or []
                            doc_file_path = doc_obj.file_path if doc_obj else None
                            doc_mime = doc_obj.mime_type if doc_obj else None
                            doc_hash = course.document_hash or (doc_obj.file_hash if doc_obj else None)

                            if job_id:
                                job_row = await session.get(GenerationJob, job_id)
                                if job_row:
                                    job_row.current_stage = f"Retrieving source for '{t_title[:50]}'"
                            lesson.generation_status = "generating"
                            await session.commit()

                        # --- Cache check ---
                        synthesized: Optional[Dict[str, Any]] = None
                        t_passages: List[Dict[str, Any]] = []
                        if cache_key:
                            async with AsyncSessionLocal() as cache_sess:
                                cached = await CourseService._find_cached_lesson(cache_sess, cache_key)
                                if cached:
                                    synthesized = {
                                        "content": cached.content,
                                        "summary": cached.summary,
                                        "key_takeaways": cached.key_takeaways or [],
                                        "learning_objectives": cached.learning_objectives or [],
                                        "prerequisites": cached.prerequisites or [],
                                        "estimated_minutes": cached.estimated_minutes or 10,
                                        "structured_sections": cached.structured_sections or {},
                                        "printed_pages": cached.printed_pages or [],
                                        "source_pages": cached.source_pages or [],
                                        "generation_status": "ready",
                                        "quality_score": cached.quality_score or 1.0,
                                        "generation_error": None,
                                    }

                        # --- Generate if not cached ---
                        if synthesized is None:
                            t_passages, source_pages = CourseService._retrieve_topic_passages(
                                document_id=doc_id,
                                user_id=user_id,
                                t_title=t_title,
                                chap_title=chap_title,
                                t_page_start=p_start,
                                t_page_end=p_end,
                                file_path=doc_file_path,
                                mime_type=doc_mime,
                            )
                            synthesized = await CourseService._synthesize_lesson_with_quality_gate(
                                t_title=t_title,
                                chap_title=chap_title,
                                course_title=course_title,
                                t_passages=t_passages,
                                source_pages=source_pages,
                                doc_blueprint=doc_blueprint,
                                difficulty=difficulty,
                                t_page_start=p_start,
                                t_page_end=p_end,
                                subtopics=subtopics,
                                chapter_order=chap_order,
                                doc_hash=doc_hash,
                            )

                        # --- Persist result ---
                        source_text = "\n\n".join(p.get("text", "") for p in t_passages)
                        async with AsyncSessionLocal() as session:
                            res = await session.execute(select(Lesson).where(Lesson.id == lid))
                            lesson = res.scalars().first()
                            if not lesson:
                                return
                            lesson.content = synthesized["content"]
                            lesson.summary = synthesized["summary"] or lesson.summary
                            lesson.key_takeaways = synthesized["key_takeaways"]
                            lesson.learning_objectives = synthesized["learning_objectives"]
                            lesson.prerequisites = synthesized["prerequisites"]
                            lesson.estimated_minutes = synthesized["estimated_minutes"]
                            lesson.structured_sections = synthesized["structured_sections"]
                            lesson.printed_pages = synthesized["printed_pages"]
                            lesson.source_pages = synthesized["source_pages"]
                            lesson.generation_status = synthesized["generation_status"]
                            lesson.quality_score = synthesized["quality_score"]
                            lesson.generation_error = synthesized["generation_error"]

                            if synthesized["generation_status"] == "ready":
                                await CourseService._ensure_lesson_exercises(
                                    session,
                                    lesson,
                                    chap_title=chap_title,
                                    source_text=source_text,
                                    domain=doc_blueprint.get("subject_domain", "general"),
                                    content_type=doc_blueprint.get("content_type", "theoretical"),
                                    difficulty=difficulty,
                                )

                            completed_count += 1
                            if job_id:
                                job_row = await session.get(GenerationJob, job_id)
                                if job_row:
                                    job_row.completed_items = min(job_row.total_items, completed_count + 1)
                                    job_row.current_stage = f"Completed {completed_count}/{total} lessons"
                            await session.commit()
                            logger.info(f"Background lesson synthesis finished for lesson id={lid} ({t_title})")
                except Exception as e:
                    logger.warning(f"Background lesson synthesis failed for lesson id={lid}: {e}")
                    # Mark as failed so UI can show error state rather than spinning forever
                    try:
                        async with AsyncSessionLocal() as session:
                            res = await session.execute(select(Lesson).where(Lesson.id == lid))
                            lesson = res.scalars().first()
                            if lesson and lesson.generation_status not in ("ready",):
                                lesson.generation_status = "queued"  # Reset to retry later
                                lesson.generation_error = str(e)[:255]
                                await session.commit()
                    except Exception:
                        pass
                    completed_count += 1

        try:
            # Run all lessons concurrently (up to MAX_PARALLEL_LESSONS at a time)
            tasks = [asyncio.create_task(_process_one_lesson(lid)) for lid in lesson_ids]
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            if job_id:
                try:
                    async with AsyncSessionLocal() as session:
                        job_row = await session.get(GenerationJob, job_id)
                        if job_row:
                            from sqlalchemy import func as sa_func
                            tot_res = await session.execute(
                                select(sa_func.count(Lesson.id))
                                .join(Topic, Lesson.topic_id == Topic.id)
                                .join(Chapter, Topic.chapter_id == Chapter.id)
                                .where(Chapter.course_id == job_row.course_id)
                            )
                            rdy_res = await session.execute(
                                select(sa_func.count(Lesson.id))
                                .join(Topic, Lesson.topic_id == Topic.id)
                                .join(Chapter, Topic.chapter_id == Chapter.id)
                                .where(Chapter.course_id == job_row.course_id, Lesson.generation_status == "ready")
                            )
                            total_cnt = int(tot_res.scalar() or 0)
                            ready_cnt = int(rdy_res.scalar() or 0)
                            job_row.status = "completed"
                            job_row.completed_items = ready_cnt
                            job_row.total_items = total_cnt or job_row.total_items
                            job_row.current_stage = (
                                f"All {total_cnt} lessons ready"
                                if total_cnt > 0 and ready_cnt >= total_cnt
                                else f"Prefetch complete ({ready_cnt}/{total_cnt} ready · remaining generate on demand)"
                            )
                            await session.commit()
                except Exception as exc:
                    logger.debug(f"Could not finalize generation job {job_id}: {exc}")

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
        if doc.processing_status == "failed":
            raise BadRequestException("Document processing failed; please reprocess or re-upload.")

        if getattr(req, "prevent_duplicate", False):
            req_diff = (req.difficulty_level or "intermediate").lower()
            dup_res = await db.execute(
                select(Course).where(
                    Course.user_id == user_id,
                    Course.document_id == req.document_id,
                    Course.difficulty_level == req_diff,
                )
            )
            existing_course = dup_res.scalars().first()
            if existing_course:
                from app.core.exceptions import ConflictException
                raise ConflictException(
                    f"Course '{existing_course.title}' already exists for this document and '{req_diff}' difficulty."
                )
        if doc.processing_status == "uploaded" and "pytest" not in sys.modules:
            for _ in range(30):
                await asyncio.sleep(1.0)
                await db.refresh(doc)
                if doc.processing_status in ("processed", "indexed"):
                    break
                if doc.processing_status == "failed":
                    raise BadRequestException("Document indexing failed; please reprocess.")
            if doc.processing_status not in ("processed", "indexed"):
                raise BadRequestException("Document is still extracting text. Please wait a few seconds and try again.")

        # 2. Reuse cached extracted pages & structure when available (avoids re-parsing 491p/280p PDFs)
        from app.services.document_service import DocumentService
        cleaned_pages = DocumentService.get_cached_pages(doc.file_hash)
        if cleaned_pages is None:
            pages = DocumentLoader.load_document(doc.file_path, doc.mime_type)
            cleaned_pages = TextCleaner.clean_document_pages(pages)
        doc_blueprint = DocumentAgent.analyze_document(cleaned_pages, doc.original_filename)

        # 2b. Reuse persisted document structure if already extracted
        extracted_sections = doc.structure if isinstance(doc.structure, list) and doc.structure else DocumentLoader.extract_structure(doc.file_path, doc.mime_type)
        if extracted_sections and not doc.structure:
            doc.structure = extracted_sections

        # 3. Synthesize structured syllabus via ContentAgent
        outline = await ContentAgent.synthesize_course_outline(
            doc_blueprint=doc_blueprint,
            target_chapters_count=req.target_chapters_count or 18,
            difficulty=req.difficulty_level or "intermediate",
            sections=extracted_sections,
        )

        final_title = outline.get("title", doc_blueprint.get("clean_title", "Course Study Guide"))
        final_description = outline.get("description", f"Comprehensive study course for {final_title}.")
        final_objectives = outline.get("learning_objectives", [])
        chapters_data = outline.get("chapters", [])
        difficulty = req.difficulty_level or "intermediate"

        # 4. Build Course, Chapters, Topics & Lessons atomically before commit
        course = Course(
            user_id=user_id,
            document_id=doc.id,
            title=final_title,
            description=final_description,
            category=outline.get("category") or doc_blueprint.get("subject_domain", "general").replace("_", " ").title(),
            difficulty_level=difficulty,
            estimated_duration_hours=outline.get("estimated_duration_hours") or max(2, len(chapters_data)),
            learning_objectives=final_objectives,
            prerequisites=outline.get("prerequisites", []),
            document_hash=doc.file_hash,
        )
        db.add(course)
        await db.flush()

        # When running with local-only CPU LLM (outside pytest), synthesize first lesson/cache hits immediately
        # and queue remaining lessons cleanly.
        first_lesson_generated = ("pytest" not in sys.modules) and model_router.is_local_only()
        pending_lessons: List[Lesson] = []
        total_topics = sum(len(ch.get("topics", [])) for ch in chapters_data)

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
                page_start=ch_page_start,
                page_end=ch_page_end,
                printed_page_start=chap_data.get("printed_page_start"),
                printed_page_end=chap_data.get("printed_page_end"),
                learning_outcomes=[f"Explain and apply core patterns in {chap_title}"],
            )
            db.add(chapter)
            await db.flush()

            topics_list = chap_data.get("topics", [])
            for t_idx, topic_entry in enumerate(topics_list):
                if isinstance(topic_entry, dict):
                    t_title = topic_entry.get("title", f"Topic {t_idx + 1}")
                    t_page_start = topic_entry.get("page_start", ch_page_start)
                    t_page_end = topic_entry.get("page_end", ch_page_end)
                    t_printed_start = topic_entry.get("printed_page_start")
                    t_printed_end = topic_entry.get("printed_page_end")
                    t_subtopics = topic_entry.get("subtopics") or []
                else:
                    t_title = str(topic_entry)
                    t_page_start = ch_page_start
                    t_page_end = ch_page_end
                    t_printed_start = None
                    t_printed_end = None
                    t_subtopics = []

                t_title = EducationalSanitizer.clean_title(t_title, fallback_prefix=f"Topic {t_idx + 1}")

                topic = Topic(
                    chapter_id=chapter.id,
                    title=t_title,
                    order_index=t_idx,
                )
                db.add(topic)
                await db.flush()

                source_pages = (
                    list(range(int(t_page_start), int(t_page_end or t_page_start) + 1))
                    if t_page_start is not None
                    else ([int(ch_page_start)] if ch_page_start is not None else [1])
                )
                t_passages: List[Dict[str, Any]] = []

                cache_key = LessonAgent.compute_cache_key(
                    doc_hash=doc.file_hash,
                    page_start=t_page_start,
                    page_end=t_page_end,
                    topic_title=t_title,
                    difficulty=difficulty,
                )
                cached = await CourseService._find_cached_lesson(db, cache_key)

                if cached is not None:
                    lesson = Lesson(
                        topic_id=topic.id,
                        title=t_title,
                        content=cached.content,
                        summary=cached.summary,
                        key_takeaways=cached.key_takeaways or [],
                        learning_objectives=cached.learning_objectives or [],
                        prerequisites=cached.prerequisites or [],
                        estimated_minutes=cached.estimated_minutes or 10,
                        structured_sections=cached.structured_sections or {},
                        printed_pages=cached.printed_pages or [],
                        source_pages=cached.source_pages or source_pages,
                        cache_key=cache_key,
                        is_completed=False,
                        page_start=t_page_start,
                        page_end=t_page_end,
                        generation_status="ready",
                        quality_score=cached.quality_score or 1.0,
                        generation_error=None,
                    )
                    db.add(lesson)
                    await db.flush()
                    if cached.exercises:
                        for idx, cex in enumerate(cached.exercises):
                            db.add(
                                LessonExercise(
                                    lesson_id=lesson.id,
                                    order_index=cex.order_index if cex.order_index is not None else idx,
                                    exercise_type=cex.exercise_type,
                                    title=cex.title,
                                    prompt=cex.prompt,
                                    starter_code=cex.starter_code,
                                    buggy_code=cex.buggy_code,
                                    options=cex.options or [],
                                    option_explanations=cex.option_explanations or [],
                                    correct_answer=cex.correct_answer,
                                    expected_output=cex.expected_output,
                                    test_cases=cex.test_cases or [],
                                    hints=cex.hints or [],
                                    explanation=cex.explanation,
                                    difficulty=cex.difficulty,
                                )
                            )
                        await db.flush()
                    else:
                        source_text = "\n\n".join(p.get("text", "") for p in t_passages)
                        await CourseService._ensure_lesson_exercises(
                            db,
                            lesson,
                            chap_title=chap_title,
                            source_text=source_text,
                            domain=doc_blueprint.get("subject_domain", "general"),
                            content_type=doc_blueprint.get("content_type", "theoretical"),
                            difficulty=difficulty,
                        )
                elif False:  # Never block course creation on synchronous LLM synthesis (30s target)
                    synthesized = await CourseService._synthesize_lesson_with_quality_gate(
                        t_title=t_title,
                        chap_title=chap_title,
                        course_title=final_title,
                        t_passages=t_passages,
                        source_pages=source_pages,
                        doc_blueprint=doc_blueprint,
                        difficulty=difficulty,
                        t_page_start=t_page_start,
                        t_page_end=t_page_end,
                        subtopics=t_subtopics,
                        chapter_order=c_idx,
                        doc_hash=doc.file_hash,
                    )
                    lesson = Lesson(
                        topic_id=topic.id,
                        title=t_title,
                        content=synthesized["content"],
                        summary=synthesized["summary"],
                        key_takeaways=synthesized["key_takeaways"],
                        learning_objectives=synthesized["learning_objectives"],
                        prerequisites=synthesized["prerequisites"],
                        estimated_minutes=synthesized["estimated_minutes"],
                        structured_sections=synthesized["structured_sections"],
                        printed_pages=synthesized["printed_pages"],
                        source_pages=synthesized["source_pages"],
                        cache_key=cache_key,
                        is_completed=False,
                        page_start=t_page_start,
                        page_end=t_page_end,
                        generation_status=synthesized["generation_status"],
                        quality_score=synthesized["quality_score"],
                        generation_error=synthesized["generation_error"],
                    )
                    db.add(lesson)
                    await db.flush()
                    if synthesized["generation_status"] == "ready":
                        source_text = "\n\n".join(p.get("text", "") for p in t_passages)
                        await CourseService._ensure_lesson_exercises(
                            db,
                            lesson,
                            chap_title=chap_title,
                            source_text=source_text,
                            domain=doc_blueprint.get("subject_domain", "general"),
                            content_type=doc_blueprint.get("content_type", "theoretical"),
                            difficulty=difficulty,
                        )
                    first_lesson_generated = True
                else:
                    printed_from_passages = LessonAgent._extract_printed_pages(t_passages, source_pages)
                    default_printed = (
                        printed_from_passages
                        if printed_from_passages
                        else (
                            [t_printed_start, t_printed_end]
                            if t_printed_start and t_printed_end and t_printed_start != t_printed_end
                            else ([t_printed_start] if t_printed_start else [str(p) for p in source_pages])
                        )
                    )
                    lesson = Lesson(
                        topic_id=topic.id,
                        title=t_title,
                        content="",
                        summary=f"Lesson on {t_title} — queued for synthesis from source pages.",
                        key_takeaways=[],
                        source_pages=source_pages,
                        printed_pages=default_printed,
                        estimated_minutes=10,
                        prerequisites=[f"Section overview for {chap_title}"],
                        learning_objectives=[f"Apply core concepts of {t_title}"],
                        structured_sections={"subtopics": t_subtopics},
                        cache_key=cache_key,
                        is_completed=False,
                        page_start=t_page_start,
                        page_end=t_page_end,
                        generation_status="queued",
                        quality_score=None,
                        generation_error=None,
                    )
                    db.add(lesson)
                    pending_lessons.append(lesson)

        prefetch_count = min(2, len(pending_lessons))
        job = GenerationJob(
            course_id=course.id,
            user_id=user_id,
            job_type="course_lessons",
            status="running" if prefetch_count else "completed",
            total_items=total_topics,
            completed_items=max(0, total_topics - len(pending_lessons)),
            current_stage=f"Prefetching next {prefetch_count} lesson(s)" if prefetch_count else "Course structure ready",
        )
        db.add(job)
        await db.commit()

        if pending_lessons and "pytest" not in sys.modules:
            # Prefetch ONLY 1 next lesson in local mode (2 in cloud) so on-demand clicks aren't blocked
            prefetch_slice = 1 if model_router.is_local_only() else 2
            pending_ids = [l.id for l in pending_lessons[:prefetch_slice]]
            task = asyncio.create_task(
                CourseService._generate_remaining_lessons_bg(pending_ids, user_id, doc_blueprint, job_id=job.id)
            )
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)

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
                .selectinload(Lesson.exercises),
                selectinload(Course.generation_jobs),
            )
        )
        res = await db.execute(query)
        course = res.scalars().first()

        if not course:
            raise NotFoundException("Course not found")
        if course.user_id != user_id:
            raise ForbiddenException("Unauthorized course access")

        detail = CourseDetailResponse.model_validate(course)
        if course.generation_jobs:
            latest_job = sorted(course.generation_jobs, key=lambda j: j.id, reverse=True)[0]
            detail.active_job = GenerationJobResponse.model_validate(latest_job)
        return detail

    @staticmethod
    async def get_generation_job(db: AsyncSession, user_id: int, course_id: int) -> Optional[GenerationJobResponse]:
        res = await db.execute(
            select(GenerationJob)
            .where(GenerationJob.course_id == course_id, GenerationJob.user_id == user_id)
            .order_by(GenerationJob.id.desc())
            .limit(1)
        )
        job = res.scalars().first()
        if not job:
            return None
        return GenerationJobResponse.model_validate(job)

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
    async def _populate_lesson_record(
        db: AsyncSession,
        lesson: Lesson,
        user_id: int,
        stage_cb: Optional[Any] = None,
    ) -> Lesson:
        """Synthesize content and exercises for a Lesson ORM object and persist it."""
        import time as _time
        stage_timings: Dict[str, float] = {}

        async def _emit(st_code: str, st_label: str) -> None:
            if stage_cb is not None:
                await stage_cb(st_code, st_label)

        course = lesson.topic.chapter.course
        doc = course.document
        t_title = lesson.title
        chap_title = lesson.topic.chapter.title
        course_title = course.title
        page_start = lesson.page_start
        page_end = lesson.page_end

        chap_order = lesson.topic.chapter.order_index
        subtopics = (lesson.structured_sections or {}).get("subtopics") or []

        # 1. Check cache first if cache_key exists
        await _emit("CHECKING_CACHE", "Checking lesson cache")
        t0 = _time.perf_counter()
        if lesson.cache_key:
            cached = await CourseService._find_cached_lesson(db, lesson.cache_key)
            if cached and cached.id != lesson.id:
                lesson.content = cached.content
                lesson.summary = cached.summary or lesson.summary
                lesson.key_takeaways = cached.key_takeaways or lesson.key_takeaways
                lesson.learning_objectives = cached.learning_objectives or []
                lesson.prerequisites = cached.prerequisites or []
                lesson.estimated_minutes = cached.estimated_minutes or 10
                lesson.structured_sections = cached.structured_sections or {}
                lesson.printed_pages = cached.printed_pages or lesson.printed_pages
                lesson.source_pages = cached.source_pages or lesson.source_pages
                lesson.generation_status = "ready"
                lesson.quality_score = cached.quality_score or 1.0
                lesson.generation_error = None
                await CourseService._ensure_lesson_exercises(
                    db, lesson, chap_title=chap_title, source_text="", difficulty=course.difficulty_level
                )
                await db.commit()
                await db.refresh(lesson)
                return lesson
        stage_timings["cache_check_ms"] = round((_time.perf_counter() - t0) * 1000, 1)

        # 2. Ensure document indexing is complete before retrieving from ChromaDB
        await _emit("CHECKING_DOCUMENT", "Checking document readiness")
        t_doc = _time.perf_counter()
        if doc is not None:
            if doc.processing_status == "failed":
                raise BadRequestException("Source document processing failed; please reprocess or re-upload.")
            if doc.processing_status in ("uploaded", "processed") and "pytest" not in sys.modules:
                for _ in range(30):
                    await asyncio.sleep(1.0)
                    await db.refresh(doc)
                    if doc.processing_status == "indexed":
                        break
                    if doc.processing_status == "failed":
                        raise BadRequestException("Source document indexing failed.")
                if doc.processing_status != "indexed":
                    raise BadRequestException("Document is still indexing vectors. Please wait a few seconds and retry.")
        stage_timings["doc_readiness_ms"] = round((_time.perf_counter() - t_doc) * 1000, 1)

        # 3. Non-blocking source retrieval with 30s timeout so jobs never hang in RETRIEVING_SOURCE
        await _emit("RETRIEVING_SOURCE", "Retrieving relevant source passages")
        t_ret = _time.perf_counter()
        t_passages, source_pages = await asyncio.wait_for(
            asyncio.to_thread(
                CourseService._retrieve_topic_passages,
                document_id=doc.id if doc else course.document_id,
                user_id=user_id,
                t_title=t_title,
                chap_title=chap_title,
                t_page_start=page_start,
                t_page_end=page_end,
                file_path=doc.file_path if doc else None,
                mime_type=doc.mime_type if doc else None,
            ),
            timeout=30.0,
        )
        if not t_passages and lesson.source_pages:
            source_pages = lesson.source_pages
        stage_timings["retrieval_ms"] = round((_time.perf_counter() - t_ret) * 1000, 1)

        await _emit("PREPARING_CONTEXT", "Preparing grounded context")
        domain_guess = (course.category or "general").lower().replace(" ", "_")
        doc_blueprint = {
            "clean_title": course_title,
            "subject_domain": domain_guess,
            "content_type": "programming" if domain_guess == "computer_science" else "theoretical",
        }
        await _emit("GENERATING", "Generating lesson content")
        synthesized = await CourseService._synthesize_lesson_with_quality_gate(
            t_title=t_title,
            chap_title=chap_title,
            course_title=course_title,
            t_passages=t_passages,
            source_pages=source_pages,
            doc_blueprint=doc_blueprint,
            difficulty=course.difficulty_level,
            t_page_start=page_start,
            t_page_end=page_end,
            subtopics=subtopics,
            chapter_order=chap_order,
            doc_hash=course.document_hash or (doc.file_hash if doc else None),
        )

        await _emit("VALIDATING", "Validating technical content & code")
        perf_meta = dict((synthesized.get("structured_sections") or {}).get("performance_metrics") or {})
        perf_meta.update(stage_timings)
        if isinstance(synthesized.get("structured_sections"), dict):
            synthesized["structured_sections"]["performance_metrics"] = perf_meta

        lesson.content = synthesized["content"]
        lesson.summary = synthesized["summary"] or lesson.summary
        lesson.key_takeaways = synthesized["key_takeaways"] or lesson.key_takeaways
        lesson.learning_objectives = synthesized["learning_objectives"]
        lesson.prerequisites = synthesized["prerequisites"]
        lesson.estimated_minutes = synthesized["estimated_minutes"]
        lesson.structured_sections = synthesized["structured_sections"]
        lesson.printed_pages = synthesized["printed_pages"]
        lesson.source_pages = synthesized["source_pages"]
        lesson.generation_status = synthesized["generation_status"]
        lesson.quality_score = synthesized["quality_score"]
        lesson.generation_error = synthesized["generation_error"]

        if synthesized["generation_status"] == "ready":
            await _emit("PREPARING_EXERCISES", "Preparing interactive exercises")
            t_ex = _time.perf_counter()
            source_text = "\n\n".join(p.get("text", "") for p in t_passages)
            await CourseService._ensure_lesson_exercises(
                db,
                lesson,
                chap_title=chap_title,
                source_text=source_text,
                domain=domain_guess,
                content_type=doc_blueprint["content_type"],
                difficulty=course.difficulty_level,
            )
            perf_meta["exercise_gen_ms"] = round((_time.perf_counter() - t_ex) * 1000, 1)

        t_db = _time.perf_counter()
        await db.commit()
        await db.refresh(lesson)
        perf_meta["db_persist_ms"] = round((_time.perf_counter() - t_db) * 1000, 1)
        await _emit("SAVING", "Saving validated lesson")
        return lesson

    @staticmethod
    async def _build_lesson_response(
        db: AsyncSession,
        lesson: Lesson,
        user_id: int,
    ) -> LessonResponse:
        """Assemble full LessonResponse with user's exercises progress & personal note."""
        exercises = await CourseService._ensure_lesson_exercises(
            db,
            lesson,
            chap_title=lesson.topic.chapter.title if lesson.topic and lesson.topic.chapter else "Module",
            domain=(
                (lesson.topic.chapter.course.category or "general").lower().replace(" ", "_")
                if lesson.topic and lesson.topic.chapter and lesson.topic.chapter.course
                else "general"
            ),
            difficulty=(
                lesson.topic.chapter.course.difficulty_level
                if lesson.topic and lesson.topic.chapter and lesson.topic.chapter.course
                else "intermediate"
            ),
        )
        await db.commit()

        ex_ids = [e.id for e in exercises]
        subs_by_ex: Dict[int, List[ExerciseSubmission]] = {}
        if ex_ids:
            sub_res = await db.execute(
                select(ExerciseSubmission)
                .where(
                    ExerciseSubmission.exercise_id.in_(ex_ids),
                    ExerciseSubmission.user_id == user_id,
                )
                .order_by(ExerciseSubmission.id.desc())
            )
            for s in sub_res.scalars().all():
                subs_by_ex.setdefault(s.exercise_id, []).append(s)

        ex_responses: List[LessonExerciseResponse] = []
        for ex in exercises:
            ex_model = LessonExerciseResponse.model_validate(ex)
            subs = subs_by_ex.get(ex.id, [])
            if subs:
                ex_model.latest_is_correct = subs[0].is_correct
                ex_model.latest_score = subs[0].score
                ex_model.attempts_count = len(subs)
            ex_responses.append(ex_model)

        note_res = await db.execute(
            select(LessonNote).where(LessonNote.lesson_id == lesson.id, LessonNote.user_id == user_id)
        )
        note_row = note_res.scalars().first()
        note_schema = (
            LessonNoteResponse(
                lesson_id=lesson.id,
                content=note_row.content,
                is_bookmarked=note_row.is_bookmarked,
                updated_at=note_row.updated_at,
            )
            if note_row
            else LessonNoteResponse(lesson_id=lesson.id, content="", is_bookmarked=False)
        )

        resp = LessonResponse.model_validate(lesson)
        resp.exercises = ex_responses
        resp.note = note_schema
        return resp

    @staticmethod
    async def get_lesson(db: AsyncSession, user_id: int, lesson_id: int) -> LessonResponse:
        query = (
            select(Lesson)
            .where(Lesson.id == lesson_id)
            .options(
                selectinload(Lesson.topic)
                .selectinload(Topic.chapter)
                .selectinload(Chapter.course)
                .selectinload(Course.document),
                selectinload(Lesson.exercises),
            )
        )
        res = await db.execute(query)
        lesson = res.scalars().first()

        if not lesson:
            raise NotFoundException("Lesson not found")
        if lesson.topic.chapter.course.user_id != user_id:
            raise ForbiddenException("Unauthorized lesson access")

        if lesson.generation_status in ("queued", "generating", "pending") and not lesson.content:
            if "pytest" in sys.modules:
                async with _get_lesson_lock(lesson_id):
                    await db.refresh(lesson)
                    if lesson.generation_status in ("queued", "generating", "pending") and not lesson.content:
                        lesson.generation_status = "generating"
                        await db.commit()
                        lesson = await CourseService._populate_lesson_record(db, lesson, user_id)
            else:
                # Non-blocking on-demand synthesis via SQLite-backed LessonJobService
                from app.services.job_queue import LessonJobService
                if lesson.generation_status in ("queued", "pending"):
                    lesson.generation_status = "generating"
                    await db.commit()
                    res = await db.execute(query)
                    lesson = res.scalars().first()
                await LessonJobService.enqueue_lesson_job(
                    course_id=lesson.topic.chapter.course_id,
                    lesson_id=lesson_id,
                    user_id=user_id,
                    job_type="on_demand",
                )

        # Prefetch next lesson ONLY after current lesson is ready so we don't block the active lesson
        if "pytest" not in sys.modules and lesson.generation_status == "ready" and lesson.topic and lesson.topic.chapter:
            from app.core.config import settings
            from app.services.job_queue import LessonJobService
            if not LessonJobService.is_prefetch_paused(lesson.topic.chapter.course_id):
                CourseService._schedule_next_lessons_prefetch(
                    course_id=lesson.topic.chapter.course_id,
                    current_lesson_id=lesson.id,
                    user_id=user_id,
                    limit=1 if model_router.is_local_only() else (3 if settings.GROQ_API_KEY else 2),
                )

        return await CourseService._build_lesson_response(db, lesson, user_id)

    @staticmethod
    def _spawn_on_demand_lesson(lesson_id: int, user_id: int) -> None:
        """Synthesize a single user-requested lesson in the background without blocking HTTP."""
        if lesson_id in _active_lesson_ids:
            return
        _active_lesson_ids.add(lesson_id)

        async def _run() -> None:
            try:
                lock = _get_lesson_lock(lesson_id)
                async with lock:
                    async with AsyncSessionLocal() as session:
                        res = await session.execute(
                            select(Lesson)
                            .where(Lesson.id == lesson_id)
                            .options(
                                selectinload(Lesson.topic)
                                .selectinload(Topic.chapter)
                                .selectinload(Chapter.course)
                                .selectinload(Course.document),
                                selectinload(Lesson.exercises),
                            )
                        )
                        lesson_obj = res.scalars().first()
                        if not lesson_obj or (lesson_obj.content and lesson_obj.generation_status == "ready"):
                            return
                        await CourseService._populate_lesson_record(session, lesson_obj, user_id)
            except Exception as exc:
                logger.warning(f"On-demand lesson synthesis failed for id={lesson_id}: {exc}")
                try:
                    async with AsyncSessionLocal() as session:
                        row = await session.get(Lesson, lesson_id)
                        if row and row.generation_status != "ready":
                            row.generation_status = "failed"
                            row.generation_error = str(exc)[:255]
                            await session.commit()
                except Exception:
                    pass
            finally:
                _active_lesson_ids.discard(lesson_id)

        task = asyncio.create_task(_run())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    @staticmethod
    def _schedule_next_lessons_prefetch(
        course_id: int,
        current_lesson_id: int,
        user_id: int,
        limit: int = 2,
    ) -> None:
        """Schedule background prefetch for up to `limit` upcoming queued lessons after `current_lesson_id`."""
        async def _run_prefetch() -> None:
            try:
                async with AsyncSessionLocal() as session:
                    res = await session.execute(
                        select(Course)
                        .where(Course.id == course_id)
                        .options(
                            selectinload(Course.chapters)
                            .selectinload(Chapter.topics)
                            .selectinload(Topic.lesson),
                            selectinload(Course.document),
                        )
                    )
                    course = res.scalars().first()
                    if not course:
                        return
                    ordered_lessons: List[Lesson] = []
                    for ch in sorted(course.chapters, key=lambda c: c.order_index):
                        for t in sorted(ch.topics, key=lambda tp: tp.order_index):
                            if t.lesson:
                                ordered_lessons.append(t.lesson)
                    idx = next((i for i, l in enumerate(ordered_lessons) if l.id == current_lesson_id), -1)
                    if idx < 0:
                        return
                    upcoming = [
                        l.id
                        for l in ordered_lessons[idx + 1 :]
                        if l.generation_status == "queued" and not l.content
                    ][:limit]
                    if not upcoming:
                        return
                    doc_blueprint = {
                        "clean_title": course.title,
                        "subject_domain": (course.category or "general").lower().replace(" ", "_"),
                        "content_type": "programming" if (course.category or "").lower() == "computer science" else "theoretical",
                    }
                await CourseService._generate_remaining_lessons_bg(upcoming, user_id, doc_blueprint)
            except Exception as exc:
                logger.debug(f"Prefetch skipped for course {course_id}: {exc}")

        task = asyncio.create_task(_run_prefetch())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    @staticmethod
    async def toggle_lesson_completion(db: AsyncSession, user_id: int, lesson_id: int) -> LessonResponse:
        lesson_res = await db.execute(
            select(Lesson)
            .where(Lesson.id == lesson_id)
            .options(
                selectinload(Lesson.topic).selectinload(Topic.chapter).selectinload(Chapter.course),
                selectinload(Lesson.exercises),
            )
        )
        lesson = lesson_res.scalars().first()
        if not lesson:
            raise NotFoundException("Lesson not found")
        if lesson.topic.chapter.course.user_id != user_id:
            raise ForbiddenException("Unauthorized lesson access")

        lesson.is_completed = not lesson.is_completed
        await db.commit()
        await db.refresh(lesson)
        return await CourseService._build_lesson_response(db, lesson, user_id)

    @staticmethod
    async def regenerate_lesson(db: AsyncSession, user_id: int, lesson_id: int) -> LessonResponse:
        query = (
            select(Lesson)
            .where(Lesson.id == lesson_id)
            .options(
                selectinload(Lesson.topic)
                .selectinload(Topic.chapter)
                .selectinload(Chapter.course)
                .selectinload(Course.document),
                selectinload(Lesson.exercises),
            )
        )
        res = await db.execute(query)
        lesson = res.scalars().first()
        if not lesson:
            raise NotFoundException("Lesson not found")
        course = lesson.topic.chapter.course
        if course.user_id != user_id:
            raise ForbiddenException("Unauthorized lesson access")

        async with _get_lesson_lock(lesson_id):
            # Preserve student completion status, notes, and exercise submission history
            prev_sections = dict(lesson.structured_sections or {})
            prev_ver = int(prev_sections.get("content_version") or 1)
            prev_sections["content_version"] = prev_ver + 1
            lesson.structured_sections = prev_sections
            lesson.generation_status = "generating"
            lesson.generation_error = None
            lesson.content = ""
            lesson.cache_key = f"{lesson.cache_key}:v{prev_ver + 1}" if lesson.cache_key else None
            # Only delete unattempted exercises so student ExerciseSubmission history remains intact
            for old_ex in list(lesson.exercises):
                sub_chk = await db.execute(
                    select(ExerciseSubmission.id).where(ExerciseSubmission.exercise_id == old_ex.id).limit(1)
                )
                if sub_chk.scalar() is None:
                    await db.delete(old_ex)
            await db.commit()
            res = await db.execute(query)
            lesson = res.scalars().first()

        if "pytest" in sys.modules:
            lesson = await CourseService._populate_lesson_record(db, lesson, user_id)
        else:
            from app.services.job_queue import LessonJobService
            await LessonJobService.enqueue_lesson_job(
                course_id=course.id,
                lesson_id=lesson_id,
                user_id=user_id,
                job_type="on_demand",
            )

        return await CourseService._build_lesson_response(db, lesson, user_id)

    @staticmethod
    async def validate_lesson(db: AsyncSession, user_id: int, lesson_id: int) -> Dict[str, Any]:
        """Validate an existing lesson's source coverage, technical accuracy, and exercise alignment without modifying progress."""
        from app.services.code_validator import CodeValidationPipeline
        from app.services.lesson_evaluator import LessonEvaluator

        res = await db.execute(
            select(Lesson)
            .where(Lesson.id == lesson_id)
            .options(
                selectinload(Lesson.topic).selectinload(Topic.chapter).selectinload(Chapter.course),
                selectinload(Lesson.exercises),
            )
        )
        lesson = res.scalars().first()
        if not lesson:
            raise NotFoundException("Lesson not found")
        course = lesson.topic.chapter.course
        if course.user_id != user_id:
            raise ForbiddenException("Unauthorized lesson access")

        domain = (course.category or "general").lower().replace(" ", "_")
        subtopics = (lesson.structured_sections or {}).get("subtopics") or []
        tech_val = CodeValidationPipeline.validate_technical_claims(lesson.content or "", domain=domain)
        ex_dicts = [
            {"title": e.title, "prompt": e.prompt, "exercise_type": e.exercise_type}
            for e in (lesson.exercises or [])
        ]
        eval_report = LessonEvaluator.evaluate(
            topic_title=lesson.title,
            lesson_content=lesson.content or "",
            subtopics=subtopics,
            exercises=ex_dicts,
            learning_objectives=lesson.learning_objectives or [],
            technical_validation=tech_val,
        )
        return {
            "lesson_id": lesson.id,
            "title": lesson.title,
            "evaluation": eval_report,
            "technical_validation": tech_val,
        }

    @staticmethod
    async def run_exercise_code(
        db: AsyncSession,
        user_id: int,
        lesson_id: int,
        exercise_id: int,
        code: str,
    ) -> CodeRunResponse:
        ex_res = await db.execute(
            select(LessonExercise)
            .where(LessonExercise.id == exercise_id, LessonExercise.lesson_id == lesson_id)
            .options(
                selectinload(LessonExercise.lesson)
                .selectinload(Lesson.topic)
                .selectinload(Topic.chapter)
                .selectinload(Chapter.course)
            )
        )
        ex = ex_res.scalars().first()
        if not ex:
            raise NotFoundException("Exercise not found")
        if ex.lesson.topic.chapter.course.user_id != user_id:
            raise ForbiddenException("Unauthorized exercise access")

        sandbox_res = await asyncio.to_thread(
            execute_python_sandbox,
            code,
            ex.test_cases or [],
        )
        return CodeRunResponse(**sandbox_res)

    @staticmethod
    async def submit_exercise(
        db: AsyncSession,
        user_id: int,
        lesson_id: int,
        exercise_id: int,
        req: ExerciseSubmitRequest,
    ) -> ExerciseSubmitResponse:
        ex_res = await db.execute(
            select(LessonExercise)
            .where(LessonExercise.id == exercise_id, LessonExercise.lesson_id == lesson_id)
            .options(
                selectinload(LessonExercise.lesson)
                .selectinload(Lesson.topic)
                .selectinload(Topic.chapter)
                .selectinload(Chapter.course)
            )
        )
        ex = ex_res.scalars().first()
        if not ex:
            raise NotFoundException("Exercise not found")
        if ex.lesson.topic.chapter.course.user_id != user_id:
            raise ForbiddenException("Unauthorized exercise access")

        prev_res = await db.execute(
            select(ExerciseSubmission).where(
                ExerciseSubmission.exercise_id == exercise_id,
                ExerciseSubmission.user_id == user_id,
            )
        )
        attempt_number = len(prev_res.scalars().all()) + 1

        is_correct = False
        score = 0.0
        feedback = ""
        option_feedback = None
        stdout = None
        stderr = None
        test_results: List[Dict[str, Any]] = []

        if ex.exercise_type in ("coding", "debugging"):
            code = req.code or req.answer or ""
            run_out = await asyncio.to_thread(execute_python_sandbox, code, ex.test_cases or [])
            stdout = run_out["stdout"]
            stderr = run_out["stderr"]
            test_results = run_out["results"]
            total_t = run_out["total_tests"]
            passed_t = run_out["passed_tests"]
            is_correct = bool(run_out["passed"])
            score = round((passed_t / total_t) * 100.0, 1) if total_t > 0 else (100.0 if is_correct else 0.0)
            feedback = (
                f"All {passed_t}/{total_t} tests passed cleanly!"
                if is_correct
                else (stderr or f"Passed {passed_t}/{total_t} test cases. Review failing cases and try again.")
            )
        elif ex.exercise_type == "mcq":
            ans = (req.answer or "").strip()
            options = ex.options or []
            option_exps = ex.option_explanations or []
            expected = (ex.correct_answer or "").strip()
            is_correct = ans.lower() == expected.lower()
            score = 100.0 if is_correct else 0.0
            if ans in options:
                idx = options.index(ans)
                if idx < len(option_exps):
                    option_feedback = option_exps[idx]
            feedback = option_feedback or (
                "Correct! Great understanding."
                if is_correct
                else "Not quite right. Use the hint or review the lesson section and try again."
            )
        elif ex.exercise_type == "fill_blank":
            ans = (req.answer or "").strip().lower()
            expected = (ex.correct_answer or "").strip().lower()
            is_correct = bool(ans) and (ans == expected or expected in ans)
            score = 100.0 if is_correct else 0.0
            feedback = "Exact match!" if is_correct else "Check your terminology and spelling, or reveal a hint."
        else:  # mini_task / reflective response
            ans = (req.answer or "").strip()
            words = len(ans.split())
            expected_kw = (ex.correct_answer or "").strip().lower()
            has_kw = not expected_kw or expected_kw in ans.lower()
            is_correct = words >= 8
            score = 100.0 if (words >= 12 and has_kw) else (75.0 if is_correct else 30.0)
            feedback = (
                "Thoughtful explanation recorded."
                if is_correct
                else "Write at least a complete 1–2 sentence explanation connecting the core concept."
            )

        sub = ExerciseSubmission(
            exercise_id=exercise_id,
            user_id=user_id,
            submitted_answer=req.answer,
            submitted_code=req.code,
            is_correct=is_correct,
            score=score,
            attempt_number=attempt_number,
            execution_stdout=stdout,
            execution_stderr=stderr,
            feedback=feedback,
        )
        db.add(sub)
        await db.commit()

        return ExerciseSubmitResponse(
            exercise_id=exercise_id,
            is_correct=is_correct,
            score=score,
            attempt_number=attempt_number,
            feedback=feedback,
            explanation=ex.explanation if is_correct or attempt_number >= 2 else None,
            option_feedback=option_feedback,
            stdout=stdout,
            stderr=stderr,
            test_results=test_results,
        )

    @staticmethod
    async def get_lesson_note(db: AsyncSession, user_id: int, lesson_id: int) -> LessonNoteResponse:
        lesson_res = await db.execute(
            select(Lesson)
            .where(Lesson.id == lesson_id)
            .options(selectinload(Lesson.topic).selectinload(Topic.chapter).selectinload(Chapter.course))
        )
        lesson = lesson_res.scalars().first()
        if not lesson:
            raise NotFoundException("Lesson not found")
        if lesson.topic.chapter.course.user_id != user_id:
            raise ForbiddenException("Unauthorized access")

        res = await db.execute(
            select(LessonNote).where(LessonNote.lesson_id == lesson_id, LessonNote.user_id == user_id)
        )
        note = res.scalars().first()
        if not note:
            return LessonNoteResponse(lesson_id=lesson_id, content="", is_bookmarked=False)
        return LessonNoteResponse(
            lesson_id=lesson_id,
            content=note.content,
            is_bookmarked=note.is_bookmarked,
            updated_at=note.updated_at,
        )

    @staticmethod
    async def upsert_lesson_note(
        db: AsyncSession,
        user_id: int,
        lesson_id: int,
        req: LessonNoteRequest,
    ) -> LessonNoteResponse:
        lesson_res = await db.execute(
            select(Lesson)
            .where(Lesson.id == lesson_id)
            .options(selectinload(Lesson.topic).selectinload(Topic.chapter).selectinload(Chapter.course))
        )
        lesson = lesson_res.scalars().first()
        if not lesson:
            raise NotFoundException("Lesson not found")
        if lesson.topic.chapter.course.user_id != user_id:
            raise ForbiddenException("Unauthorized access")

        res = await db.execute(
            select(LessonNote).where(LessonNote.lesson_id == lesson_id, LessonNote.user_id == user_id)
        )
        note = res.scalars().first()
        if not note:
            note = LessonNote(
                lesson_id=lesson_id,
                user_id=user_id,
                content=req.content if req.content is not None else "",
                is_bookmarked=bool(req.is_bookmarked) if req.is_bookmarked is not None else False,
            )
            db.add(note)
        else:
            if req.content is not None:
                note.content = req.content
            if req.is_bookmarked is not None:
                note.is_bookmarked = req.is_bookmarked

        await db.commit()
        await db.refresh(note)
        return LessonNoteResponse(
            lesson_id=lesson_id,
            content=note.content,
            is_bookmarked=note.is_bookmarked,
            updated_at=note.updated_at,
        )

    @staticmethod
    async def get_module_assessment(
        db: AsyncSession,
        user_id: int,
        course_id: int,
        chapter_id: int,
    ) -> CourseAssessmentResponse:
        chap_res = await db.execute(
            select(Chapter)
            .where(Chapter.id == chapter_id, Chapter.course_id == course_id)
            .options(
                selectinload(Chapter.course),
                selectinload(Chapter.topics).selectinload(Topic.lesson).selectinload(Lesson.exercises),
            )
        )
        chapter = chap_res.scalars().first()
        if not chapter:
            raise NotFoundException("Module not found")
        if chapter.course.user_id != user_id:
            raise ForbiddenException("Unauthorized access")

        existing_res = await db.execute(
            select(CourseAssessment)
            .where(
                CourseAssessment.course_id == course_id,
                CourseAssessment.chapter_id == chapter_id,
                CourseAssessment.assessment_type == "module",
            )
            .options(selectinload(CourseAssessment.attempts))
        )
        assessment = existing_res.scalars().first()
        if not assessment:
            lessons = [t.lesson for t in chapter.topics if t.lesson]
            data = ExerciseAgent.build_module_assessment(course_id, chapter_id, chapter.title, lessons)
            assessment = CourseAssessment(**data)
            db.add(assessment)
            await db.commit()
            await db.refresh(assessment, ["attempts"])

        return CourseService._format_assessment_response(assessment, user_id)

    @staticmethod
    async def get_final_assessment(
        db: AsyncSession,
        user_id: int,
        course_id: int,
    ) -> CourseAssessmentResponse:
        course_res = await db.execute(
            select(Course)
            .where(Course.id == course_id)
            .options(
                selectinload(Course.chapters)
                .selectinload(Chapter.topics)
                .selectinload(Topic.lesson)
                .selectinload(Lesson.exercises)
            )
        )
        course = course_res.scalars().first()
        if not course:
            raise NotFoundException("Course not found")
        if course.user_id != user_id:
            raise ForbiddenException("Unauthorized access")

        existing_res = await db.execute(
            select(CourseAssessment)
            .where(
                CourseAssessment.course_id == course_id,
                CourseAssessment.assessment_type == "final",
            )
            .options(selectinload(CourseAssessment.attempts))
        )
        assessment = existing_res.scalars().first()
        if not assessment:
            data = ExerciseAgent.build_final_assessment(course_id, course.title, course.chapters)
            assessment = CourseAssessment(**data)
            db.add(assessment)
            await db.commit()
            await db.refresh(assessment, ["attempts"])

        return CourseService._format_assessment_response(assessment, user_id)

    @staticmethod
    def _format_assessment_response(assessment: CourseAssessment, user_id: int) -> CourseAssessmentResponse:
        user_attempts = [a for a in (assessment.attempts or []) if a.user_id == user_id]
        best_score = max((a.score for a in user_attempts), default=None)
        passed = any(a.passed for a in user_attempts)
        safe_questions = [
            AssessmentQuestionItem(
                id=str(q.get("id")),
                question_type=str(q.get("question_type", "mcq")),
                prompt=str(q.get("prompt", "")),
                options=q.get("options") or [],
                topic_id=q.get("topic_id"),
                topic_title=q.get("topic_title"),
                lesson_id=q.get("lesson_id"),
            )
            for q in (assessment.questions or [])
        ]
        return CourseAssessmentResponse(
            id=assessment.id,
            course_id=assessment.course_id,
            chapter_id=assessment.chapter_id,
            assessment_type=assessment.assessment_type,
            title=assessment.title,
            description=assessment.description,
            passing_score=assessment.passing_score,
            questions=safe_questions,
            best_score=best_score,
            passed=passed,
        )

    @staticmethod
    async def submit_assessment(
        db: AsyncSession,
        user_id: int,
        course_id: int,
        assessment_id: int,
        req: AssessmentSubmitRequest,
    ) -> AssessmentResultResponse:
        res = await db.execute(
            select(CourseAssessment)
            .where(CourseAssessment.id == assessment_id, CourseAssessment.course_id == course_id)
            .options(selectinload(CourseAssessment.course))
        )
        assessment = res.scalars().first()
        if not assessment:
            raise NotFoundException("Assessment not found")
        if assessment.course.user_id != user_id:
            raise ForbiddenException("Unauthorized access")

        questions = assessment.questions or []
        correct_count = 0
        topic_stats: Dict[str, Dict[str, Any]] = {}
        feedback_items: List[Dict[str, Any]] = []

        for q in questions:
            qid = str(q.get("id"))
            selected = str(req.answers.get(qid, "")).strip()
            expected = str(q.get("correct_answer", "")).strip()
            ok = bool(selected) and selected.lower() == expected.lower()
            if ok:
                correct_count += 1

            t_title = str(q.get("topic_title") or "General")
            l_id = q.get("lesson_id")
            stat = topic_stats.setdefault(t_title, {"topic_title": t_title, "lesson_id": l_id, "correct": 0, "total": 0})
            stat["total"] += 1
            if ok:
                stat["correct"] += 1

            feedback_items.append({
                "id": qid,
                "is_correct": ok,
                "selected_answer": selected,
                "correct_answer": expected,
                "explanation": q.get("explanation", ""),
                "topic_title": t_title,
                "lesson_id": l_id,
            })

        total_q = len(questions)
        score = round((correct_count / total_q) * 100.0, 1) if total_q > 0 else 100.0
        passed = score >= assessment.passing_score

        breakdown = []
        rec_lessons: List[int] = []
        for stat in topic_stats.values():
            pct = round((stat["correct"] / stat["total"]) * 100.0, 1) if stat["total"] else 0.0
            breakdown.append({**stat, "percentage": pct})
            if pct < 70.0 and stat["lesson_id"] and stat["lesson_id"] not in rec_lessons:
                rec_lessons.append(stat["lesson_id"])

        attempt = CourseAssessmentAttempt(
            assessment_id=assessment.id,
            user_id=user_id,
            answers=req.answers,
            score=score,
            passed=passed,
            topic_breakdown=breakdown,
            recommended_lesson_ids=rec_lessons,
        )
        db.add(attempt)
        await db.commit()

        return AssessmentResultResponse(
            assessment_id=assessment.id,
            score=score,
            passed=passed,
            correct_count=correct_count,
            total_questions=total_q,
            topic_breakdown=breakdown,
            recommended_lesson_ids=rec_lessons,
            question_feedback=feedback_items,
        )
