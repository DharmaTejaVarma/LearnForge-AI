from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models.user import User
from app.db.models.course import Course, Chapter, Topic, Lesson
from app.db.models.document import UploadedDocument
from app.db.models.learning_tools import Flashcard, AgentExecutionLog
from app.api.dependencies.auth import get_current_user
from app.schemas.learning_tools import FlashcardCreate, FlashcardResponse, FlashcardReviewUpdate
from app.ai.graphs.learning_graph import LearningGraph
from app.core.exceptions import NotFoundException, ForbiddenException, BadRequestException

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
    """Generate deduplicated active-recall flashcard deck via LangGraph workflow."""
    single_doc_id, multi_doc_ids = await _resolve_document_ids(
        db, current_user.id, req.document_id, req.course_id
    )

    existing_res = await db.execute(
        select(Flashcard.front_prompt).where(Flashcard.user_id == current_user.id)
    )
    existing_fronts = [row[0] for row in existing_res.all() if row[0]]

    graph_state = await LearningGraph.run_workflow(
        {
            "workflow_type": "flashcard_generation",
            "user_id": current_user.id,
            "document_id": single_doc_id,
            "document_ids": multi_doc_ids,
            "course_id": req.course_id,
            "count": req.count or 5,
            "difficulty": req.difficulty or "medium",
            "existing_fronts": existing_fronts,
        }
    )
    cards_data = (graph_state.get("generated_output") or {}).get("cards", [])
    if not cards_data:
        raise BadRequestException(
            "Not enough indexed source material found in the selected document or course to generate unique flashcards."
        )

    created_cards = []
    now_utc = datetime.utcnow()
    for c in cards_data:
        fc = Flashcard(
            user_id=current_user.id,
            course_id=req.course_id,
            document_id=req.document_id or single_doc_id,
            front_prompt=c.get("front", "Question"),
            back_answer=c.get("back", "Answer"),
            difficulty=c.get("difficulty", req.difficulty or "medium"),
            review_count=0,
            mastery_level="new",
            ease_factor=2.5,
            interval_days=0,
            next_review_at=now_utc,
        )
        db.add(fc)
        created_cards.append(fc)

    db.add(
        AgentExecutionLog(
            user_id=current_user.id,
            agent_name="LearningGraph:Flashcard",
            task_type="flashcard_generation",
            status="success",
            latency_ms=0.0,
            output_summary=f"created={len(created_cards)}",
        )
    )
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
    due_only: bool = Query(False, description="Only return cards currently due for SM-2 review"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List flashcards belonging to the current user, with optional filters and pagination."""
    query = select(Flashcard).where(Flashcard.user_id == current_user.id)
    if course_id:
        query = query.where(Flashcard.course_id == course_id)
    if document_id:
        query = query.where(Flashcard.document_id == document_id)
    if mastery_level:
        query = query.where(Flashcard.mastery_level == mastery_level)
    if due_only:
        now_utc = datetime.utcnow()
        query = query.where((Flashcard.next_review_at.is_(None)) | (Flashcard.next_review_at <= now_utc))
    query = query.order_by(Flashcard.id.desc()).offset(skip).limit(limit)
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
    """Record flashcard review result and update SM-2 spaced repetition schedule & mastery."""
    res = await db.execute(select(Flashcard).where(Flashcard.id == flashcard_id))
    fc = res.scalars().first()
    if not fc:
        raise NotFoundException("Flashcard not found")
    if fc.user_id != current_user.id:
        raise ForbiddenException("Unauthorized flashcard access")

    now_utc = datetime.utcnow()
    fc.review_count += 1
    fc.last_reviewed_at = now_utc

    if review_in.mastered:
        # SM-2 progression on recall success
        quality = 4
        fc.ease_factor = max(1.3, round(fc.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)), 2))
        if fc.interval_days == 0:
            fc.interval_days = 1
        elif fc.interval_days == 1:
            fc.interval_days = 6
        else:
            fc.interval_days = max(1, int(round(fc.interval_days * fc.ease_factor)))
        fc.mastery_level = "mastered"
        fc.next_review_at = now_utc + timedelta(days=fc.interval_days)
    else:
        # Reset interval on recall miss
        fc.ease_factor = max(1.3, round(fc.ease_factor - 0.2, 2))
        fc.interval_days = 0
        fc.mastery_level = "reviewing"
        fc.next_review_at = now_utc + timedelta(minutes=10)

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
