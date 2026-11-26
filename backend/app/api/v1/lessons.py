import asyncio
import json
from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db, AsyncSessionLocal
from app.db.models.user import User
from app.api.dependencies.auth import get_current_user
from app.schemas.course import (
    LessonResponse,
    ExerciseSubmitRequest,
    ExerciseSubmitResponse,
    CodeRunRequest,
    CodeRunResponse,
    LessonNoteRequest,
    LessonNoteResponse,
)
from app.services.course_service import CourseService
from app.services.job_queue import LessonJobService

router = APIRouter()


@router.get("/{lesson_id}", response_model=LessonResponse, status_code=status.HTTP_200_OK)
async def get_lesson(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full lesson content with structured metadata, exercises, notes, and source page citations."""
    return await CourseService.get_lesson(db, current_user.id, lesson_id)


@router.post("/{lesson_id}/toggle-complete", response_model=LessonResponse, status_code=status.HTTP_200_OK)
async def toggle_lesson_completion(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle completion status for a lesson."""
    return await CourseService.toggle_lesson_completion(db, current_user.id, lesson_id)


@router.post("/{lesson_id}/regenerate", response_model=LessonResponse, status_code=status.HTTP_200_OK)
async def regenerate_lesson(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Regenerate a failed or outdated lesson and its exercises."""
    return await CourseService.regenerate_lesson(db, current_user.id, lesson_id)


@router.get("/{lesson_id}/status", status_code=status.HTTP_200_OK)
async def get_lesson_job_status(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return real-time generation job stage, elapsed time, retry count, and metrics."""
    return await LessonJobService.get_job_status_payload(db, current_user.id, lesson_id)


@router.post("/{lesson_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_lesson_generation(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an active on-demand lesson generation job."""
    return await LessonJobService.cancel_lesson_job(db, current_user.id, lesson_id)


@router.get("/{lesson_id}/events")
async def stream_lesson_events(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
):
    """Server-Sent Events stream reporting real-time lesson generation stage transitions."""
    async def _event_stream():
        for _ in range(180):
            async with AsyncSessionLocal() as session:
                payload = await LessonJobService.get_job_status_payload(session, current_user.id, lesson_id)
            yield f"data: {json.dumps(payload)}\n\n"
            if payload.get("status") in ("COMPLETED", "FAILED", "CANCELLED"):
                break
            await asyncio.sleep(1.5)

    return StreamingResponse(_event_stream(), media_type="text/event-stream")


@router.post("/{lesson_id}/exercises/{exercise_id}/run", response_model=CodeRunResponse, status_code=status.HTTP_200_OK)
async def run_exercise_code(
    lesson_id: int,
    exercise_id: int,
    req: CodeRunRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute Python code in an isolated subprocess sandbox against the exercise test cases."""
    from app.services.code_sandbox import check_sandbox_rate_limit
    check_sandbox_rate_limit(current_user.id)
    return await CourseService.run_exercise_code(db, current_user.id, lesson_id, exercise_id, req.code)


@router.post("/{lesson_id}/exercises/{exercise_id}/submit", response_model=ExerciseSubmitResponse, status_code=status.HTTP_200_OK)
async def submit_exercise(
    lesson_id: int,
    exercise_id: int,
    req: ExerciseSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Evaluate and persist an interactive exercise submission."""
    return await CourseService.submit_exercise(db, current_user.id, lesson_id, exercise_id, req)


@router.get("/{lesson_id}/notes", response_model=LessonNoteResponse, status_code=status.HTTP_200_OK)
async def get_lesson_note(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch user's personal notes and bookmark state for a lesson."""
    return await CourseService.get_lesson_note(db, current_user.id, lesson_id)


@router.put("/{lesson_id}/notes", response_model=LessonNoteResponse, status_code=status.HTTP_200_OK)
async def save_lesson_note(
    lesson_id: int,
    req: LessonNoteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save or update personal notes and bookmark state for a lesson."""
    return await CourseService.upsert_lesson_note(db, current_user.id, lesson_id, req)
