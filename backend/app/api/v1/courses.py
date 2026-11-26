import asyncio
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models.user import User
from app.api.dependencies.auth import get_current_user
from app.schemas.course import (
    CourseGenerateRequest,
    CourseResponse,
    CourseDetailResponse,
    CourseAssessmentResponse,
    AssessmentSubmitRequest,
    AssessmentResultResponse,
    GenerationJobResponse,
)
from app.services.code_sandbox import execute_python_sandbox, check_sandbox_rate_limit
from app.services.course_service import CourseService
from app.services.job_queue import LessonJobService

router = APIRouter()


@router.post("/generate", response_model=CourseDetailResponse, status_code=status.HTTP_201_CREATED)
async def generate_course(
    req: CourseGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Synthesize a complete modular course with chapters, topics, and lessons from an uploaded document."""
    return await CourseService.generate_course(db, current_user.id, req)


@router.get("", response_model=List[CourseResponse], status_code=status.HTTP_200_OK)
@router.get("/", response_model=List[CourseResponse], status_code=status.HTTP_200_OK)
async def list_courses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all courses created by or generated for the current user."""
    return await CourseService.list_user_courses(db, current_user.id)


@router.get("/{course_id}", response_model=CourseDetailResponse, status_code=status.HTTP_200_OK)
async def get_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full course outline including chapters, topics, and lesson IDs."""
    return await CourseService.get_course_detail(db, current_user.id, course_id)


@router.get("/{course_id}/generation-status", response_model=Optional[GenerationJobResponse], status_code=status.HTTP_200_OK)
async def get_course_generation_status(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return latest background lesson generation job status for real-time progress tracking."""
    return await CourseService.get_generation_job(db, current_user.id, course_id)


@router.get("/{course_id}/generation-progress", status_code=status.HTTP_200_OK)
async def get_course_generation_progress(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return real-time curriculum & content readiness breakdown for the course."""
    return await LessonJobService.get_course_generation_progress(db, current_user.id, course_id)


@router.get("/{course_id}/lessons", status_code=status.HTTP_200_OK)
async def list_course_lessons_status(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return lightweight status summaries for all lessons in a course."""
    return await LessonJobService.list_course_lessons_status(db, current_user.id, course_id)


@router.post("/{course_id}/prefetch/pause", status_code=status.HTTP_200_OK)
async def pause_course_prefetch(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pause background lesson prefetching for this course."""
    await CourseService.get_course_detail(db, current_user.id, course_id)
    LessonJobService.pause_prefetch(course_id)
    return {"course_id": course_id, "prefetch_paused": True}


@router.post("/{course_id}/prefetch/resume", status_code=status.HTTP_200_OK)
async def resume_course_prefetch(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resume background lesson prefetching for this course."""
    await CourseService.get_course_detail(db, current_user.id, course_id)
    LessonJobService.resume_prefetch(course_id)
    return {"course_id": course_id, "prefetch_paused": False}


@router.post("/{course_id}/retry-failed", status_code=status.HTTP_200_OK)
async def retry_failed_course_lessons(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-enqueue failed lessons in this course."""
    return await LessonJobService.retry_failed_lessons(db, current_user.id, course_id)


@router.get("/{course_id}/modules/{chapter_id}/assessment", response_model=CourseAssessmentResponse, status_code=status.HTTP_200_OK)
async def get_module_assessment(
    course_id: int,
    chapter_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get or build a graded module mastery assessment."""
    return await CourseService.get_module_assessment(db, current_user.id, course_id, chapter_id)


@router.get("/{course_id}/final-assessment", response_model=CourseAssessmentResponse, status_code=status.HTTP_200_OK)
async def get_final_assessment(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get or build the comprehensive final course assessment."""
    return await CourseService.get_final_assessment(db, current_user.id, course_id)


@router.post("/{course_id}/assessments/{assessment_id}/submit", response_model=AssessmentResultResponse, status_code=status.HTTP_200_OK)
async def submit_course_assessment(
    course_id: int,
    assessment_id: int,
    req: AssessmentSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Evaluate a module or final course assessment submission with topic-level breakdown."""
    return await CourseService.submit_assessment(db, current_user.id, course_id, assessment_id, req)


@router.delete("/{course_id}", status_code=status.HTTP_200_OK)
async def delete_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a course and all associated chapters, topics, and lessons."""
    return await CourseService.delete_course(db, current_user.id, course_id)


class SandboxRunRequest(BaseModel):
    code: str
    test_cases: Optional[List[Dict[str, Any]]] = None


@router.post("/sandbox/run", status_code=status.HTTP_200_OK)
async def run_sandbox_code(
    req: SandboxRunRequest,
    current_user: User = Depends(get_current_user),
):
    """Execute Python code in the isolated subprocess sandbox (used by Project Milestones)."""
    check_sandbox_rate_limit(current_user.id)
    return await asyncio.to_thread(execute_python_sandbox, req.code, req.test_cases or [])
