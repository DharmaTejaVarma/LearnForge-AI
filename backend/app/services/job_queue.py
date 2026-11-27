"""SQLite-backed lesson generation job queue with heartbeat, stale detection, 10-stage tracking, and course progress."""
from __future__ import annotations

import asyncio
import datetime
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ForbiddenException, NotFoundException
from app.core.logging import logger
from app.db.database import AsyncSessionLocal
from app.db.models.course import Chapter, Course, Lesson, LessonGenerationJob, Topic

ACTIVE_JOB_STATES = (
    "PENDING",
    "QUEUED",
    "WAITING_FOR_WORKER",
    "WAITING_FOR_MODEL",
    "CHECKING_CACHE",
    "CHECKING_DOCUMENT",
    "RETRIEVING_SOURCE",
    "PREPARING_CONTEXT",
    "GENERATING",
    "VALIDATING",
    "REPAIRING_CODE",
    "PREPARING_EXERCISES",
    "SAVING",
)

STAGE_ORDER = [
    "CHECKING_CACHE",
    "CHECKING_DOCUMENT",
    "RETRIEVING_SOURCE",
    "PREPARING_CONTEXT",
    "GENERATING",
    "VALIDATING",
    "REPAIRING_CODE",
    "PREPARING_EXERCISES",
    "SAVING",
    "COMPLETED",
]

STALE_HEARTBEAT_SECONDS = 180.0


def _utcnow_iso() -> str:
    return datetime.datetime.utcnow().isoformat()


def _format_actionable_error(exc: Exception) -> Tuple[str, str]:
    """Classify exception into (error_code, actionable_message)."""
    msg = str(exc) or type(exc).__name__
    low = msg.lower()
    if "not found" in low and "model" in low:
        return (
            "MODEL_MISSING",
            "Configured Ollama model is not installed. Run 'ollama pull qwen2.5:3b' and retry.",
        )
    if "connect" in low or "11434" in low or "refused" in low or "unavailable" in low:
        return (
            "OLLAMA_UNAVAILABLE",
            "Local AI model is unavailable. Check that Ollama is running.",
        )
    if "chroma" in low or "collection" in low or "vector" in low:
        return (
            "CHROMA_FAILED",
            "Source retrieval failed in ChromaDB. Check vector store health or reprocess the document.",
        )
    if "indexing" in low or "incomplete" in low or "processing failed" in low:
        return (
            "DOC_INCOMPLETE",
            "Document indexing is incomplete. Wait for document processing to finish or reprocess it.",
        )
    if "timeout" in low or "timed out" in low or "readtimeout" in low:
        return (
            "LLM_TIMEOUT",
            "Local AI model timed out while generating this lesson. Click Retry to resume.",
        )
    if "validation" in low:
        return ("VALIDATION_FAILED", msg[:450])
    if "database is locked" in low:
        return (
            "DB_LOCKED",
            "Database was briefly busy saving another lesson. Click Retry to resume.",
        )
    return ("GENERATION_ERROR", msg[:450])


class LessonJobService:
    """Manages SQLite-persisted lesson generation jobs with heartbeat, priority, & stale recovery."""

    _running_tasks: Dict[int, asyncio.Task] = {}
    _worker_sem: Optional[asyncio.Semaphore] = None
    _active_lesson_ids: Set[int] = set()
    _on_demand_waiting: int = 0
    _paused_courses: Set[int] = set()
    _heartbeats: Dict[int, str] = {}

    @classmethod
    def _get_worker_sem(cls) -> asyncio.Semaphore:
        if cls._worker_sem is None:
            from app.ai.models.model_router import model_router
            cls._worker_sem = asyncio.Semaphore(1 if model_router.is_local_only() else 2)
        return cls._worker_sem

    @classmethod
    def pause_prefetch(cls, course_id: int) -> None:
        cls._paused_courses.add(course_id)

    @classmethod
    def resume_prefetch(cls, course_id: int) -> None:
        cls._paused_courses.discard(course_id)

    @classmethod
    def is_prefetch_paused(cls, course_id: int) -> bool:
        return course_id in cls._paused_courses

    @classmethod
    async def get_latest_job_for_lesson(
        cls, db: AsyncSession, user_id: int, lesson_id: int
    ) -> Optional[LessonGenerationJob]:
        res = await db.execute(
            select(LessonGenerationJob)
            .where(LessonGenerationJob.lesson_id == lesson_id, LessonGenerationJob.user_id == user_id)
            .order_by(LessonGenerationJob.id.desc())
            .limit(1)
        )
        return res.scalars().first()

    @classmethod
    async def _check_and_recover_stale_job(
        cls, db: AsyncSession, job: LessonGenerationJob, lesson: Optional[Lesson]
    ) -> None:
        """Detect stale jobs whose worker stopped heartbeating and fail them safely for retry."""
        if job.status not in ACTIVE_JOB_STATES:
            return
        if job.lesson_id in cls._active_lesson_ids:
            return
        metrics = dict(job.metrics or {})
        hb_str = cls._heartbeats.get(job.id) or metrics.get("heartbeat_at") or job.started_at
        if not hb_str:
            return
        try:
            age = (datetime.datetime.utcnow() - datetime.datetime.fromisoformat(hb_str)).total_seconds()
        except Exception:
            age = 0.0

        # Active in-flight stage with no live worker in memory after 25s, or any queued job > STALE_HEARTBEAT_SECONDS
        stale = (job.status != "QUEUED" and age > 25.0) or (age > STALE_HEARTBEAT_SECONDS)
        if not stale:
            return

        metrics["error_code"] = "STALE_JOB_TIMEOUT"
        job.status = "FAILED"
        job.current_stage = "Stale job recovered"
        job.error_message = "Generation stalled (worker heartbeat timeout). Click Retry to resume."
        job.completed_at = _utcnow_iso()
        job.metrics = metrics
        if lesson and lesson.generation_status != "ready":
            lesson.generation_status = "failed"
            lesson.generation_error = job.error_message[:255]
        await db.commit()

    @classmethod
    async def get_job_status_payload(
        cls, db: AsyncSession, user_id: int, lesson_id: int
    ) -> Dict[str, Any]:
        l_res = await db.execute(
            select(Lesson)
            .where(Lesson.id == lesson_id)
            .options(selectinload(Lesson.topic).selectinload(Topic.chapter).selectinload(Chapter.course))
        )
        lesson = l_res.scalars().first()
        if not lesson:
            raise NotFoundException("Lesson not found")
        if lesson.topic.chapter.course.user_id != user_id:
            raise ForbiddenException("Unauthorized lesson access")

        job = await cls.get_latest_job_for_lesson(db, user_id, lesson_id)
        if job:
            await cls._check_and_recover_stale_job(db, job, lesson)
            await db.refresh(job)
            await db.refresh(lesson)

        if not job:
            is_ready = bool(lesson.generation_status == "ready")
            is_failed = bool(lesson.generation_status == "failed")
            return {
                "lesson_id": lesson_id,
                "status": "COMPLETED" if is_ready else ("FAILED" if is_failed else "QUEUED"),
                "current_stage": "Completed" if is_ready else ("Generation failed" if is_failed else "Queued for synthesis"),
                "stage_started_at": None,
                "elapsed_seconds": 0.0,
                "stage_duration_ms": None,
                "completed_stages": len(STAGE_ORDER) if is_ready else 0,
                "total_stages": len(STAGE_ORDER),
                "progress_percentage": 100.0 if is_ready else 0.0,
                "generated_tokens": None,
                "target_tokens": None,
                "error_code": "GENERATION_ERROR" if is_failed else None,
                "error_message": lesson.generation_error,
                "retry_count": 0,
                "heartbeat_at": None,
                "updated_at": _utcnow_iso(),
                "metrics": (lesson.structured_sections or {}).get("performance_metrics") or {},
            }

        metrics = dict(job.metrics or {})
        elapsed = 0.0
        if job.started_at:
            try:
                t_start = datetime.datetime.fromisoformat(job.started_at)
                t_end = datetime.datetime.fromisoformat(job.completed_at) if job.completed_at else datetime.datetime.utcnow()
                elapsed = round(max(0.0, (t_end - t_start).total_seconds()), 1)
            except Exception:
                pass

        stage_started_at = metrics.get("stage_started_at")
        stage_duration_ms = None
        if stage_started_at and job.status in ACTIVE_JOB_STATES:
            try:
                st_dt = datetime.datetime.fromisoformat(stage_started_at)
                stage_duration_ms = round(max(0.0, (datetime.datetime.utcnow() - st_dt).total_seconds() * 1000), 1)
            except Exception:
                pass

        completed_stages = STAGE_ORDER.index(job.status) if job.status in STAGE_ORDER else 0
        if job.status == "COMPLETED":
            completed_stages = len(STAGE_ORDER)
            progress_pct: Optional[float] = 100.0
        elif job.status in ("GENERATING", "WAITING_FOR_MODEL"):
            # Indeterminate during LLM token generation unless token metrics exist
            gen_tok = metrics.get("output_tokens")
            tgt_tok = metrics.get("target_tokens")
            progress_pct = round(min(95.0, (gen_tok / tgt_tok) * 100.0), 1) if (gen_tok and tgt_tok) else None
        elif job.status in ("FAILED", "CANCELLED"):
            progress_pct = None
        else:
            progress_pct = round((completed_stages / len(STAGE_ORDER)) * 100.0, 1)

        return {
            "job_id": job.id,
            "lesson_id": lesson_id,
            "course_id": job.course_id,
            "status": job.status,
            "current_stage": job.current_stage,
            "stage_started_at": stage_started_at,
            "elapsed_seconds": elapsed,
            "stage_duration_ms": stage_duration_ms,
            "completed_stages": completed_stages,
            "total_stages": len(STAGE_ORDER),
            "progress_percentage": progress_pct,
            "generated_tokens": metrics.get("output_tokens"),
            "target_tokens": metrics.get("target_tokens"),
            "error_code": metrics.get("error_code"),
            "error_message": job.error_message,
            "retry_count": job.retry_count,
            "heartbeat_at": metrics.get("heartbeat_at"),
            "updated_at": job.updated_at.isoformat() if job.updated_at else _utcnow_iso(),
            "metrics": metrics,
        }

    @classmethod
    async def get_course_generation_progress(
        cls, db: AsyncSession, user_id: int, course_id: int
    ) -> Dict[str, Any]:
        c_res = await db.execute(select(Course).where(Course.id == course_id))
        course = c_res.scalars().first()
        if not course:
            raise NotFoundException("Course not found")
        if course.user_id != user_id:
            raise ForbiddenException("Unauthorized course access")

        l_rows = await db.execute(
            select(Lesson.id, Lesson.title, Lesson.generation_status)
            .join(Topic, Lesson.topic_id == Topic.id)
            .join(Chapter, Topic.chapter_id == Chapter.id)
            .where(Chapter.course_id == course_id)
        )
        lessons = l_rows.all()
        total = len(lessons)
        ready = sum(1 for _, _, st in lessons if st == "ready")
        generating = sum(1 for _, _, st in lessons if st == "generating")
        failed = sum(1 for _, _, st in lessons if st == "failed")
        cancelled = sum(1 for _, _, st in lessons if st == "cancelled")
        queued = max(0, total - ready - generating - failed - cancelled)

        readiness_pct = round((ready / total) * 100.0, 2) if total > 0 else 0.0

        job_res = await db.execute(
            select(LessonGenerationJob)
            .where(
                LessonGenerationJob.course_id == course_id,
                LessonGenerationJob.user_id == user_id,
                LessonGenerationJob.status.in_(ACTIVE_JOB_STATES),
            )
            .order_by(LessonGenerationJob.id.desc())
            .limit(1)
        )
        active_job = job_res.scalars().first()
        active_title = None
        active_elapsed = 0.0
        if active_job:
            await cls._check_and_recover_stale_job(db, active_job, None)
            if active_job.status in ACTIVE_JOB_STATES:
                active_title = next((t for lid, t, _ in lessons if lid == active_job.lesson_id), None)
                if active_job.started_at:
                    try:
                        active_elapsed = round(
                            max(0.0, (datetime.datetime.utcnow() - datetime.datetime.fromisoformat(active_job.started_at)).total_seconds()),
                            1,
                        )
                    except Exception:
                        pass
            else:
                active_job = None

        course_gen_status = (
            "COMPLETED"
            if total > 0 and ready == total
            else ("GENERATING" if (active_job or generating > 0) else ("FAILED" if failed > 0 and ready == 0 else "ON_DEMAND_READY"))
        )

        from app.db.models.document import UploadedDocument
        from app.services.document_service import DocumentService
        doc_res = await db.execute(
            select(UploadedDocument)
            .where(UploadedDocument.user_id == user_id)
            .order_by(UploadedDocument.id.desc())
            .limit(4)
        )
        docs_progress = [DocumentService.get_document_progress(d) for d in doc_res.scalars().all()]

        return {
            "course_id": course_id,
            "total_lessons": total,
            "ready_lessons": ready,
            "queued_lessons": queued,
            "generating_lessons": generating,
            "failed_lessons": failed,
            "cancelled_lessons": cancelled,
            "curriculum_status": "READY" if total > 0 else "EMPTY",
            "curriculum_percentage": 100.0 if total > 0 else 0.0,
            "content_readiness_percentage": readiness_pct,
            "course_generation_status": course_gen_status,
            "active_job_id": active_job.id if active_job else None,
            "active_lesson_id": active_job.lesson_id if active_job else None,
            "active_lesson_title": active_title,
            "active_stage": active_job.current_stage if active_job else None,
            "active_elapsed_seconds": active_elapsed,
            "prefetch_paused": cls.is_prefetch_paused(course_id),
            "documents_progress": docs_progress,
            "updated_at": _utcnow_iso(),
        }

    @classmethod
    async def list_course_lessons_status(
        cls, db: AsyncSession, user_id: int, course_id: int
    ) -> List[Dict[str, Any]]:
        c_res = await db.execute(select(Course).where(Course.id == course_id))
        course = c_res.scalars().first()
        if not course:
            raise NotFoundException("Course not found")
        if course.user_id != user_id:
            raise ForbiddenException("Unauthorized course access")

        rows = await db.execute(
            select(
                Lesson.id,
                Lesson.title,
                Lesson.generation_status,
                Lesson.is_completed,
                Lesson.quality_score,
                Lesson.generation_error,
                Chapter.order_index,
                Topic.order_index,
            )
            .join(Topic, Lesson.topic_id == Topic.id)
            .join(Chapter, Topic.chapter_id == Chapter.id)
            .where(Chapter.course_id == course_id)
            .order_by(Chapter.order_index, Topic.order_index)
        )
        return [
            {
                "lesson_id": lid,
                "title": title,
                "generation_status": st,
                "is_completed": bool(done),
                "quality_score": q_score,
                "generation_error": err,
                "chapter_index": c_idx,
                "topic_index": t_idx,
            }
            for lid, title, st, done, q_score, err, c_idx, t_idx in rows.all()
        ]

    @classmethod
    async def retry_failed_lessons(
        cls, db: AsyncSession, user_id: int, course_id: int
    ) -> Dict[str, Any]:
        c_res = await db.execute(select(Course).where(Course.id == course_id))
        course = c_res.scalars().first()
        if not course:
            raise NotFoundException("Course not found")
        if course.user_id != user_id:
            raise ForbiddenException("Unauthorized course access")

        rows = await db.execute(
            select(Lesson)
            .join(Topic, Lesson.topic_id == Topic.id)
            .join(Chapter, Topic.chapter_id == Chapter.id)
            .where(Chapter.course_id == course_id, Lesson.generation_status == "failed")
        )
        failed_lessons = rows.scalars().all()
        requeued = 0
        for l in failed_lessons:
            l.generation_status = "queued"
            l.generation_error = None
            requeued += 1
        await db.commit()

        for l in failed_lessons:
            await cls.enqueue_lesson_job(course_id, l.id, user_id, job_type="prefetch")
        return {"course_id": course_id, "requeued_lessons": requeued}

    @classmethod
    async def enqueue_lesson_job(
        cls,
        course_id: int,
        lesson_id: int,
        user_id: int,
        job_type: str = "on_demand",
    ) -> int:
        """Create or reuse an active SQLite job for `lesson_id` (zero duplicate jobs)."""
        async with AsyncSessionLocal() as session:
            existing_res = await session.execute(
                select(LessonGenerationJob)
                .where(
                    LessonGenerationJob.lesson_id == lesson_id,
                    LessonGenerationJob.user_id == user_id,
                    LessonGenerationJob.status.in_(ACTIVE_JOB_STATES),
                )
                .order_by(LessonGenerationJob.id.desc())
                .limit(1)
            )
            existing = existing_res.scalars().first()
            if existing:
                if lesson_id not in cls._active_lesson_ids:
                    cls._spawn_worker(existing.id, lesson_id, user_id, job_type=job_type)
                return existing.id

            now_iso = _utcnow_iso()
            job = LessonGenerationJob(
                course_id=course_id,
                lesson_id=lesson_id,
                user_id=user_id,
                job_type=job_type,
                status="QUEUED",
                current_stage="Waiting for worker",
                started_at=now_iso,
                retry_count=0,
                metrics={"heartbeat_at": now_iso, "stage_started_at": now_iso},
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            job_id = job.id

        cls._spawn_worker(job_id, lesson_id, user_id, job_type=job_type)
        return job_id

    @classmethod
    async def _set_job_stage(
        cls,
        job_id: int,
        status: str,
        stage_label: str,
        error_message: Optional[str] = None,
        error_code: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
        completed: bool = False,
        retry_count: Optional[int] = None,
    ) -> None:
        async with AsyncSessionLocal() as session:
            job = await session.get(LessonGenerationJob, job_id)
            if not job:
                return
            now_iso = _utcnow_iso()
            merged_metrics = dict(job.metrics or {})
            if metrics:
                merged_metrics.update(metrics)
            merged_metrics["heartbeat_at"] = now_iso
            merged_metrics["stage_started_at"] = now_iso
            if error_code is not None:
                merged_metrics["error_code"] = error_code

            job.status = status
            job.current_stage = stage_label
            if error_message is not None:
                job.error_message = error_message[:500]
            job.metrics = merged_metrics
            if retry_count is not None:
                job.retry_count = retry_count
            if completed:
                job.completed_at = now_iso
            await session.commit()

    @classmethod
    def _spawn_worker(cls, job_id: int, lesson_id: int, user_id: int, job_type: str = "on_demand") -> None:
        if lesson_id in cls._active_lesson_ids:
            return
        cls._active_lesson_ids.add(lesson_id)

        async def _heartbeat_loop(stop_evt: asyncio.Event) -> None:
            while not stop_evt.is_set():
                cls._heartbeats[job_id] = _utcnow_iso()
                try:
                    await asyncio.sleep(3.0)
                except asyncio.CancelledError:
                    break

        async def _execute() -> None:
            from app.services.course_service import CourseService, _get_lesson_lock
            max_retries = 2
            is_on_demand = job_type == "on_demand"
            waiting_decremented = False
            if is_on_demand:
                cls._on_demand_waiting += 1
            stop_hb = asyncio.Event()
            hb_task = asyncio.create_task(_heartbeat_loop(stop_hb))
            try:
                if not is_on_demand:
                    while cls._on_demand_waiting > 0:
                        await asyncio.sleep(0.1)
                await cls._set_job_stage(job_id, "WAITING_FOR_WORKER", "Waiting for worker")
                async with cls._get_worker_sem():
                    if is_on_demand and not waiting_decremented and cls._on_demand_waiting > 0:
                        cls._on_demand_waiting -= 1
                        waiting_decremented = True
                    for attempt in range(max_retries + 1):
                        try:
                            async def _stage_cb(st_code: str, st_label: str) -> None:
                                await cls._set_job_stage(job_id, st_code, st_label)

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
                                    if not lesson_obj:
                                        await cls._set_job_stage(
                                            job_id,
                                            "FAILED",
                                            "Lesson not found",
                                            error_message="Lesson not found",
                                            error_code="NOT_FOUND",
                                            completed=True,
                                        )
                                        return
                                    if lesson_obj.content and lesson_obj.generation_status == "ready":
                                        await cls._set_job_stage(job_id, "COMPLETED", "Completed", completed=True)
                                        return

                                    t0 = time.perf_counter()
                                    updated = await CourseService._populate_lesson_record(
                                        session, lesson_obj, user_id, stage_cb=_stage_cb
                                    )
                                    total_ms = round((time.perf_counter() - t0) * 1000, 1)
                                    metrics = dict((updated.structured_sections or {}).get("performance_metrics") or {})
                                    metrics["job_id"] = job_id
                                    metrics["course_id"] = updated.topic.chapter.course_id if updated.topic and updated.topic.chapter else None
                                    metrics["lesson_id"] = lesson_id
                                    metrics["user_id"] = user_id
                                    metrics["total_ms"] = total_ms
                                    logger.info(
                                        f"LessonJob completed: job_id={job_id} lesson_id={lesson_id} "
                                        f"user_id={user_id} status={updated.generation_status} total_ms={total_ms} "
                                        f"stages={metrics}"
                                    )
                                    if updated.generation_status == "ready":
                                        await cls._set_job_stage(job_id, "COMPLETED", "Completed", metrics=metrics, completed=True)
                                    else:
                                        await cls._set_job_stage(
                                            job_id,
                                            "FAILED",
                                            "Generation failed",
                                            error_message=updated.generation_error or "Validation failed",
                                            error_code="VALIDATION_FAILED",
                                            metrics=metrics,
                                            completed=True,
                                        )
                                    return
                        except asyncio.CancelledError:
                            await cls._set_job_stage(job_id, "CANCELLED", "Cancelled by user", completed=True)
                            async with AsyncSessionLocal() as session:
                                row = await session.get(Lesson, lesson_id)
                                if row and row.generation_status != "ready":
                                    row.generation_status = "queued"
                                    await session.commit()
                            return
                        except Exception as exc:
                            err_code, actionable = _format_actionable_error(exc)
                            logger.warning(f"Job {job_id} attempt {attempt + 1} failed for lesson {lesson_id}: [{err_code}] {actionable}")
                            if attempt < max_retries:
                                backoff = 2 ** (attempt + 1)
                                await cls._set_job_stage(
                                    job_id,
                                    "QUEUED",
                                    f"Retrying in {backoff}s (attempt {attempt + 2}/{max_retries + 1})",
                                    error_message=actionable,
                                    error_code=err_code,
                                    retry_count=attempt + 1,
                                )
                                await asyncio.sleep(backoff)
                            else:
                                await cls._set_job_stage(
                                    job_id,
                                    "FAILED",
                                    "Generation failed",
                                    error_message=actionable,
                                    error_code=err_code,
                                    retry_count=attempt,
                                    completed=True,
                                )
                                async with AsyncSessionLocal() as session:
                                    row = await session.get(Lesson, lesson_id)
                                    if row and row.generation_status != "ready":
                                        row.generation_status = "failed"
                                        row.generation_error = actionable[:255]
                                        await session.commit()
            finally:
                stop_hb.set()
                if not hb_task.done():
                    hb_task.cancel()
                cls._heartbeats.pop(job_id, None)
                if is_on_demand and not waiting_decremented and cls._on_demand_waiting > 0:
                    cls._on_demand_waiting -= 1
                    waiting_decremented = True
                cls._active_lesson_ids.discard(lesson_id)
                cls._running_tasks.pop(lesson_id, None)

        task = asyncio.create_task(_execute())
        cls._running_tasks[lesson_id] = task

    @classmethod
    async def cancel_lesson_job(cls, db: AsyncSession, user_id: int, lesson_id: int) -> Dict[str, Any]:
        # Verify lesson ownership before cancelling any task or mutating Lesson state
        own_res = await db.execute(
            select(Lesson)
            .join(Topic, Lesson.topic_id == Topic.id)
            .join(Chapter, Topic.chapter_id == Chapter.id)
            .join(Course, Chapter.course_id == Course.id)
            .where(Lesson.id == lesson_id, Course.user_id == user_id)
        )
        row = own_res.scalars().first()
        if not row:
            raise NotFoundException("Lesson not found")
        task = cls._running_tasks.get(lesson_id)
        if task and not task.done():
            task.cancel()
        await db.execute(
            update(LessonGenerationJob)
            .where(
                LessonGenerationJob.lesson_id == lesson_id,
                LessonGenerationJob.user_id == user_id,
                LessonGenerationJob.status.in_(ACTIVE_JOB_STATES),
            )
            .values(status="CANCELLED", current_stage="Cancelled by user", completed_at=_utcnow_iso())
        )
        if row.generation_status != "ready":
            row.generation_status = "queued"
        await db.commit()
        return {"lesson_id": lesson_id, "status": "CANCELLED"}

    @classmethod
    async def recover_interrupted_jobs(cls) -> None:
        """Reset active jobs interrupted by a server restart back to QUEUED."""
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(LessonGenerationJob)
                .where(LessonGenerationJob.status.in_(ACTIVE_JOB_STATES))
                .values(status="QUEUED", current_stage="Recovered after restart — ready to resume")
            )
            await session.commit()

    @classmethod
    async def shutdown_workers(cls) -> None:
        for task in list(cls._running_tasks.values()):
            if not task.done():
                task.cancel()
        cls._running_tasks.clear()
        cls._active_lesson_ids.clear()
