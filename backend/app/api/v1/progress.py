from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models.user import User
from app.api.dependencies.auth import get_current_user
from app.schemas.learning_tools import ProgressResponse
from app.services.progress_service import ProgressService

router = APIRouter()

@router.get("/stats", response_model=ProgressResponse, status_code=status.HTTP_200_OK)
async def get_progress_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve personalized learning analytics, completion rates, and weak topics."""
    return await ProgressService.get_user_progress(db, current_user.id)
