"""SQLite-backed lesson generation job queue with stage tracking, retries, cancellation, and recovery."""
from __future__ import annotations

import asyncio
import datetime
import time
from typing import Any, Dict, Optional, Set

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import logger
from app.db.database import AsyncSessionLocal
from app.db.models.course import Chapter, Course, Lesson, LessonGenerationJob, Topic

ACTIVE_JOB_STATES = ("PENDING", "QUEUED", "RETRIEVING_SOURCE", "GENERATING", "VALIDATING", "SAVING")


def _utcnow_iso() -> str:
    return datetime.datetime.utcnow().isoformat()


def _format_actionable_error(exc: Exception) -> str:
    """Translate raw transport/model exceptions into clear, actionable student/operator messages."""
    msg = str(exc) or type(exc).__name__
    low = msg.lower()
    if "timeout" in low or "timed out" in low or "readtimeout" in low:
        return "Local AI model timed out while generating this lesson. Click Regenerate Lesson to retry."
    if "connect" in low or "11434" in low or "refused" in low:
        return "Local AI engine (Ollama) is unreachable. Verify Ollama is running, then click Regenerate Lesson."
    if "not found" in low and "model" in low:
        return "Configured Ollama model is not installed. Run 'ollama pull qwen2.5:3b' and retry."
    if "database is locked" in low:
        return "Database was briefly busy saving another lesson. Click Regenerate Lesson to retry."
    return msg[:450]


class LessonJobService:
    """Manages SQLite-persisted lesson generation jobs with duplicate prevention & cancellation."""

    _running_tasks: Dict[int, asyncio.Task] = {}
    _worker_sem: Optional[asyncio.Semaphore] = None
    _active_lesson_ids: Set[int] = set()
    _on_demand_waiting: int = 0

    @classmethod
    def _get_worker_sem(cls) -> asyncio.Semaphore:
        if cls._worker_sem is None:
            cls._worker_sem = asyncio.Semaphore(1)
        return cls._worker_sem

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
    async def get_job_status_payload(
        cls, db: AsyncSession, user_id: int, lesson_id: int
    ) -> Dict[str, Any]:
        job = await cls.get_latest_job_for_lesson(db, user_id, lesson_id)
        lesson = await db.get(Lesson, lesson_id)
        if not job:
            return {
                "lesson_id": lesson_id,
                "status": "COMPLETED" if (lesson and lesson.generation_status == "ready") else (
                    "FAILED" if (lesson and lesson.generation_status == "failed") else "QUEUED"
                ),
                "current_stage": "Lesson ready" if (lesson and lesson.generation_status == "ready") else "Preparing source material",
                "elapsed_seconds": 0.0,
                "retry_count": 0,
                "error_message": lesson.generation_error if lesson else None,
                "metrics": (lesson.structured_sections or {}).get("performance_metrics") if lesson else {},
            }

        elapsed = 0.0
        if job.started_at:
            try:
                t_start = datetime.datetime.fromisoformat(job.started_at)
                t_end = datetime.datetime.fromisoformat(job.completed_at) if job.completed_at else datetime.datetime.utcnow()
                elapsed = round(max(0.0, (t_end - t_start).total_seconds()), 1)
            except Exception:
                pass

        return {
            "job_id": job.id,
            "lesson_id": lesson_id,
            "course_id": job.course_id,
            "status": job.status,
            "current_stage": job.current_stage,
            "elapsed_seconds": elapsed,
            "retry_count": job.retry_count,
            "error_message": job.error_message,
            "metrics": job.metrics or {},
        }

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

            job = LessonGenerationJob(
                course_id=course_id,
                lesson_id=lesson_id,
                user_id=user_id,
                job_type=job_type,
                status="QUEUED",
                current_stage="Preparing source material",
                started_at=_utcnow_iso(),
                retry_count=0,
                metrics={},
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
        metrics: Optional[Dict[str, Any]] = None,
        completed: bool = False,
        retry_count: Optional[int] = None,
    ) -> None:
        async with AsyncSessionLocal() as session:
            job = await session.get(LessonGenerationJob, job_id)
            if not job:
                return
            job.status = status
            job.current_stage = stage_label
            if error_message is not None:
                job.error_message = error_message[:500]
            if metrics is not None:
                job.metrics = metrics
            if retry_count is not None:
                job.retry_count = retry_count
            if completed:
                job.completed_at = _utcnow_iso()
            await session.commit()

    @classmethod
    def _spawn_worker(cls, job_id: int, lesson_id: int, user_id: int, job_type: str = "on_demand") -> None:
        if lesson_id in cls._active_lesson_ids:
            return
        cls._active_lesson_ids.add(lesson_id)

        async def _execute() -> None:
            from app.services.course_service import CourseService, _get_lesson_lock
            max_retries = 2
            is_on_demand = job_type == "on_demand"
            if is_on_demand:
                cls._on_demand_waiting += 1
            try:
                if not is_on_demand:
                    while cls._on_demand_waiting > 0:
                        await asyncio.sleep(0.1)
                async with cls._get_worker_sem():
                    if is_on_demand and cls._on_demand_waiting > 0:
                        cls._on_demand_waiting -= 1
                    for attempt in range(max_retries + 1):
                        try:
                            await cls._set_job_stage(job_id, "RETRIEVING_SOURCE", "Retrieving relevant sections")
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
                                        await cls._set_job_stage(job_id, "FAILED", "Lesson not found", error_message="Lesson not found", completed=True)
                                        return
                                    if lesson_obj.content and lesson_obj.generation_status == "ready":
                                        await cls._set_job_stage(job_id, "COMPLETED", "Lesson ready", completed=True)
                                        return

                                    await cls._set_job_stage(job_id, "GENERATING", "Generating lesson content")
                                    t0 = time.perf_counter()
                                    updated = await CourseService._populate_lesson_record(session, lesson_obj, user_id)
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
                                        await cls._set_job_stage(job_id, "COMPLETED", "Lesson ready", metrics=metrics, completed=True)
                                    else:
                                        await cls._set_job_stage(
                                            job_id,
                                            "FAILED",
                                            "Generation failed",
                                            error_message=updated.generation_error or "Validation failed",
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
                            actionable = _format_actionable_error(exc)
                            logger.warning(f"Job {job_id} attempt {attempt + 1} failed for lesson {lesson_id}: {actionable}")
                            if attempt < max_retries:
                                backoff = 2 ** (attempt + 1)
                                await cls._set_job_stage(
                                    job_id,
                                    "QUEUED",
                                    f"Retrying in {backoff}s (attempt {attempt + 2}/{max_retries + 1})",
                                    error_message=actionable,
                                    retry_count=attempt + 1,
                                )
                                await asyncio.sleep(backoff)
                            else:
                                await cls._set_job_stage(
                                    job_id,
                                    "FAILED",
                                    "Generation failed",
                                    error_message=actionable,
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
                if is_on_demand and cls._on_demand_waiting > 0:
                    cls._on_demand_waiting -= 1
                cls._active_lesson_ids.discard(lesson_id)
                cls._running_tasks.pop(lesson_id, None)

        task = asyncio.create_task(_execute())
        cls._running_tasks[lesson_id] = task

    @classmethod
    async def cancel_lesson_job(cls, db: AsyncSession, user_id: int, lesson_id: int) -> Dict[str, Any]:
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
        row = await db.get(Lesson, lesson_id)
        if row and row.generation_status != "ready":
            row.generation_status = "queued"
        await db.commit()
        return {"lesson_id": lesson_id, "status": "CANCELLED"}

    @classmethod
    async def recover_interrupted_jobs(cls) -> None:
        """Reset active jobs interrupted by a server restart back to QUEUED."""
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(LessonGenerationJob)
                .where(LessonGenerationJob.status.in_(("RETRIEVING_SOURCE", "GENERATING", "VALIDATING", "SAVING")))
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
