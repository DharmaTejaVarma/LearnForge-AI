from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models.user import User
from app.api.dependencies.auth import get_current_user
from app.schemas.course import CourseGenerateRequest, CourseResponse, CourseDetailResponse
from app.services.course_service import CourseService

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

@router.delete("/{course_id}", status_code=status.HTTP_200_OK)
async def delete_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a course and all associated chapters, topics, and lessons."""
    return await CourseService.delete_course(db, current_user.id, course_id)
