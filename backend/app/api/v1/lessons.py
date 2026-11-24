from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models.user import User
from app.api.dependencies.auth import get_current_user
from app.schemas.course import LessonResponse
from app.services.course_service import CourseService

router = APIRouter()

@router.get("/{lesson_id}", response_model=LessonResponse, status_code=status.HTTP_200_OK)
async def get_lesson(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full lesson content with rich Markdown text and source page citations."""
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
    """Regenerate a failed or outdated lesson."""
    return await CourseService.regenerate_lesson(db, current_user.id, lesson_id)
