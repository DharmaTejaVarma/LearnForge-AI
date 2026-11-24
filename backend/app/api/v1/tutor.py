from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models.user import User
from app.api.dependencies.auth import get_current_user
from app.schemas.learning_tools import (
    TutorChatRequest,
    TutorChatResponse,
    TutorConversationItem,
    TutorSuggestionResponse,
)
from app.services.tutor_service import TutorService

router = APIRouter()

@router.post("/chat", response_model=TutorChatResponse, status_code=status.HTTP_200_OK)
async def tutor_chat(
    req: TutorChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Interact with the Socratic AI Tutor with intelligent intent routing, RAG citations, and conversation memory."""
    return await TutorService.chat(db, current_user.id, req)

@router.get("/history", response_model=List[TutorConversationItem], status_code=status.HTTP_200_OK)
async def get_tutor_history(
    conversation_id: Optional[str] = Query(None),
    document_id: Optional[int] = Query(None),
    course_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves conversation history for the student, optionally filtered by conversation_id, course_id, or document_id."""
    return await TutorService.get_history(
        db=db,
        user_id=current_user.id,
        conversation_id=conversation_id,
        course_id=course_id,
        document_id=document_id,
    )

@router.delete("/history", status_code=status.HTTP_200_OK)
async def clear_tutor_history(
    conversation_id: Optional[str] = Query(None),
    document_id: Optional[int] = Query(None),
    course_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Clears conversation history for the student."""
    return await TutorService.clear_history(
        db=db,
        user_id=current_user.id,
        conversation_id=conversation_id,
        course_id=course_id,
        document_id=document_id,
    )

@router.get("/suggestions", response_model=TutorSuggestionResponse, status_code=status.HTTP_200_OK)
async def get_tutor_suggestions(
    course_id: Optional[int] = Query(None),
    lesson_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns dynamic suggested questions tailored to the active course or lesson."""
    suggestions = await TutorService.get_suggested_questions(
        db=db,
        user_id=current_user.id,
        course_id=course_id,
        lesson_id=lesson_id,
    )
    return TutorSuggestionResponse(suggestions=suggestions)
