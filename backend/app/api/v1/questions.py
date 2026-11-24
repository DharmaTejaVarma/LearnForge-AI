from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models.user import User
from app.db.models.learning_tools import Question
from app.api.dependencies.auth import get_current_user
from app.schemas.learning_tools import QuestionResponse

router = APIRouter()

@router.get("", response_model=List[QuestionResponse], status_code=status.HTTP_200_OK)
@router.get("/", response_model=List[QuestionResponse], status_code=status.HTTP_200_OK)
async def list_questions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all generated questions belonging to the user."""
    query = select(Question).where(Question.user_id == current_user.id).order_by(Question.id.desc())
    res = await db.execute(query)
    return [QuestionResponse.model_validate(q) for q in res.scalars().all()]
