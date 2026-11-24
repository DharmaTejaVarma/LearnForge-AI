from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models.user import User
from app.db.models.course import Course, Chapter, Topic, Lesson
from app.db.models.document import UploadedDocument
from app.db.models.learning_tools import Flashcard
from app.api.dependencies.auth import get_current_user
from app.schemas.learning_tools import FlashcardCreate, FlashcardResponse, FlashcardReviewUpdate
from app.ai.agents.flashcard_agent import FlashcardAgent
from app.core.exceptions import NotFoundException, ForbiddenException

router = APIRouter()


async def _resolve_document_ids(
    db: AsyncSession,
    user_id: int,
    document_id: Optional[int],
    course_id: Optional[int],
) -> tuple[Optional[int], Optional[List[int]]]:
    """Resolve single or multi-document IDs for RAG scoping based on course or document selection."""
    if course_id:
        course_res = await db.execute(select(Course).where(Course.id == course_id, Course.user_id == user_id))
        course = course_res.scalars().first()
        if not course:
            raise NotFoundException("Course not found")
        if course.document_id:
            return course.document_id, [course.document_id]
        return None, None
    return document_id, [document_id] if document_id else None


@router.post("/generate", response_model=List[FlashcardResponse], status_code=status.HTTP_201_CREATED)
async def generate_flashcards(
    req: FlashcardCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate active-recall flashcard deck using AI and RAG document/course context."""
    single_doc_id, multi_doc_ids = await _resolve_document_ids(
        db, current_user.id, req.document_id, req.course_id
    )

    cards_data = await FlashcardAgent.generate_cards(
        user_id=current_user.id,
        document_id=single_doc_id,
        document_ids=multi_doc_ids,
        count=req.count or 5,
        difficulty=req.difficulty or "medium",
    )

    created_cards = []
    for c in cards_data:
        fc = Flashcard(
            user_id=current_user.id,
            course_id=req.course_id,
            document_id=req.document_id or single_doc_id,
            front_prompt=c.get("front", "Question"),
            back_answer=c.get("back", "Answer"),
            review_count=0,
            mastery_level="new",
        )
        db.add(fc)
        created_cards.append(fc)

    await db.commit()
    for fc in created_cards:
        await db.refresh(fc)

    return [FlashcardResponse.model_validate(c) for c in created_cards]


@router.get("", response_model=List[FlashcardResponse], status_code=status.HTTP_200_OK)
@router.get("/", response_model=List[FlashcardResponse], status_code=status.HTTP_200_OK)
async def list_flashcards(
    course_id: Optional[int] = Query(None, description="Filter by course"),
    document_id: Optional[int] = Query(None, description="Filter by document"),
    mastery_level: Optional[str] = Query(None, description="Filter by mastery: new, reviewing, mastered"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List flashcards belonging to the current user, with optional filters."""
    query = select(Flashcard).where(Flashcard.user_id == current_user.id)
    if course_id:
        query = query.where(Flashcard.course_id == course_id)
    if document_id:
        query = query.where(Flashcard.document_id == document_id)
    if mastery_level:
        query = query.where(Flashcard.mastery_level == mastery_level)
    query = query.order_by(Flashcard.id.desc())
    res = await db.execute(query)
    cards = res.scalars().all()
    return [FlashcardResponse.model_validate(c) for c in cards]


@router.post("/{flashcard_id}/review", response_model=FlashcardResponse, status_code=status.HTTP_200_OK)
async def review_flashcard(
    flashcard_id: int,
    review_in: FlashcardReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record flashcard review result and update mastery level."""
    res = await db.execute(select(Flashcard).where(Flashcard.id == flashcard_id))
    fc = res.scalars().first()
    if not fc:
        raise NotFoundException("Flashcard not found")
    if fc.user_id != current_user.id:
        raise ForbiddenException("Unauthorized flashcard access")

    fc.review_count += 1
    fc.last_reviewed_at = datetime.utcnow()
    fc.mastery_level = "mastered" if review_in.mastered else "reviewing"

    await db.commit()
    await db.refresh(fc)
    return FlashcardResponse.model_validate(fc)


@router.delete("/{flashcard_id}", status_code=status.HTTP_200_OK)
async def delete_flashcard(
    flashcard_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a flashcard."""
    res = await db.execute(select(Flashcard).where(Flashcard.id == flashcard_id))
    fc = res.scalars().first()
    if not fc:
        raise NotFoundException("Flashcard not found")
    if fc.user_id != current_user.id:
        raise ForbiddenException("Unauthorized flashcard access")
    await db.delete(fc)
    await db.commit()
    return {"message": "Flashcard deleted", "id": flashcard_id}


@router.delete("", status_code=status.HTTP_200_OK)
async def clear_flashcards(
    course_id: Optional[int] = Query(None),
    document_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Clear all flashcards for the current user (optionally scoped to course or document)."""
    query = select(Flashcard).where(Flashcard.user_id == current_user.id)
    if course_id:
        query = query.where(Flashcard.course_id == course_id)
    if document_id:
        query = query.where(Flashcard.document_id == document_id)
    res = await db.execute(query)
    cards = res.scalars().all()
    for fc in cards:
        await db.delete(fc)
    await db.commit()
    return {"message": f"Cleared {len(cards)} flashcards"}
