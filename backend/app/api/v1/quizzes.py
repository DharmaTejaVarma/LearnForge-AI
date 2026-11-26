from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models.user import User
from app.db.models.course import Course, Chapter, Topic, Lesson
from app.db.models.learning_tools import Question, Quiz, QuizAttempt, AgentExecutionLog
from app.api.dependencies.auth import get_current_user
from app.schemas.learning_tools import (
    QuizGenerateRequest,
    QuizResponse,
    QuizListItem,
    QuizSubmitRequest,
    QuizAttemptResponse,
    QuestionResponse,
    QuizAttemptDetailResponse,
)
from app.ai.agents.assessment_agent import AssessmentAgent
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


@router.get("", response_model=List[QuizListItem], status_code=status.HTTP_200_OK)
@router.get("/", response_model=List[QuizListItem], status_code=status.HTTP_200_OK)
async def list_quizzes(
    course_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's generated quizzes ordered by most recent."""
    query = select(Quiz).where(Quiz.user_id == current_user.id)
    if course_id:
        query = query.where(Quiz.course_id == course_id)
    query = query.order_by(Quiz.id.desc()).offset(skip).limit(limit)
    res = await db.execute(query)
    quizzes = res.scalars().all()
    return [
        QuizListItem(
            id=q.id,
            user_id=q.user_id,
            course_id=q.course_id,
            title=q.title,
            description=q.description,
            question_count=len(q.question_ids or []),
            created_at=q.created_at,
        )
        for q in quizzes
    ]


@router.post("/generate", response_model=QuizResponse, status_code=status.HTTP_201_CREATED)
async def generate_quiz(
    req: QuizGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate dynamic assessment quiz (MCQ, True/False, Short Answer) via LangGraph workflow."""
    single_doc_id, multi_doc_ids = await _resolve_document_ids(
        db, current_user.id, req.document_id, req.course_id
    )

    graph_state = await LearningGraph.run_workflow(
        {
            "workflow_type": "quiz_generation",
            "user_id": current_user.id,
            "document_id": single_doc_id,
            "document_ids": multi_doc_ids,
            "course_id": req.course_id,
            "count": req.question_count or 5,
            "difficulty": req.difficulty or "medium",
            "question_type": req.question_type or "mcq",
        }
    )
    q_data_list = (graph_state.get("generated_output") or {}).get("questions", [])
    if not q_data_list:
        raise BadRequestException(
            "Insufficient indexed source material found in the selected document or course to generate quiz questions."
        )

    created_questions = []
    for q_data in q_data_list:
        q = Question(
            user_id=current_user.id,
            course_id=req.course_id,
            document_id=req.document_id or single_doc_id,
            question_text=q_data["question_text"],
            question_type=q_data.get("question_type", "mcq"),
            options=q_data.get("options", []),
            correct_answer=q_data["correct_answer"],
            explanation=q_data.get("explanation"),
            difficulty=req.difficulty or "medium",
        )
        db.add(q)
        created_questions.append(q)

    await db.commit()
    for q in created_questions:
        await db.refresh(q)

    # Build a meaningful quiz title from context
    difficulty_label = (req.difficulty or "medium").title()
    quiz_title = f"{difficulty_label} Assessment Quiz"
    if req.course_id:
        course_res = await db.execute(select(Course).where(Course.id == req.course_id, Course.user_id == current_user.id))
        course = course_res.scalars().first()
        if course:
            quiz_title = f"{course.title} — {difficulty_label} Quiz"

    quiz = Quiz(
        user_id=current_user.id,
        course_id=req.course_id,
        title=quiz_title,
        description=f"AI-generated {difficulty_label.lower()} assessment with {len(created_questions)} questions",
        question_ids=[q.id for q in created_questions],
    )
    db.add(quiz)
    db.add(
        AgentExecutionLog(
            user_id=current_user.id,
            agent_name="LearningGraph:Question",
            task_type="quiz_generation",
            status="success",
            latency_ms=0.0,
            output_summary=f"questions={len(created_questions)}, type={req.question_type or 'mcq'}",
        )
    )
    await db.commit()
    await db.refresh(quiz)

    return QuizResponse(
        id=quiz.id,
        user_id=quiz.user_id,
        course_id=quiz.course_id,
        title=quiz.title,
        description=quiz.description,
        questions=[QuestionResponse.model_validate(q) for q in created_questions],
        created_at=quiz.created_at,
    )


@router.get("/{quiz_id}", response_model=QuizResponse, status_code=status.HTTP_200_OK)
async def get_quiz(
    quiz_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve quiz questions and details."""
    quiz_res = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = quiz_res.scalars().first()
    if not quiz:
        raise NotFoundException("Quiz not found")
    if quiz.user_id != current_user.id:
        raise ForbiddenException("Unauthorized quiz access")

    questions = []
    if quiz.question_ids:
        q_res = await db.execute(select(Question).where(Question.id.in_(quiz.question_ids)))
        questions = q_res.scalars().all()

    return QuizResponse(
        id=quiz.id,
        user_id=quiz.user_id,
        course_id=quiz.course_id,
        title=quiz.title,
        description=quiz.description,
        questions=[QuestionResponse.model_validate(q) for q in questions],
        created_at=quiz.created_at,
    )


@router.post("/{quiz_id}/submit", response_model=QuizAttemptDetailResponse, status_code=status.HTTP_200_OK)
async def submit_quiz(
    quiz_id: int,
    submission: QuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit quiz answers, compute score, and generate explanatory feedback with per-question results."""
    quiz_res = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = quiz_res.scalars().first()
    if not quiz:
        raise NotFoundException("Quiz not found")
    if quiz.user_id != current_user.id:
        raise ForbiddenException("Unauthorized quiz access")

    questions = []
    if quiz.question_ids:
        q_res = await db.execute(select(Question).where(Question.id.in_(quiz.question_ids)))
        questions = q_res.scalars().all()
    q_dict_list = [
        {
            "id": q.id,
            "correct_answer": q.correct_answer,
            "question_text": q.question_text,
            "question_type": q.question_type,
            "explanation": q.explanation or "",
            "options": q.options or [],
        }
        for q in questions
    ]

    graph_state = await LearningGraph.run_workflow(
        {
            "workflow_type": "assessment_review",
            "user_id": current_user.id,
            "quiz_questions": q_dict_list,
            "student_answers": submission.answers,
        }
    )
    eval_result = graph_state.get("generated_output") or AssessmentAgent.evaluate_quiz(q_dict_list, submission.answers)

    attempt = QuizAttempt(
        user_id=current_user.id,
        quiz_id=quiz.id,
        score_percentage=eval_result["score_percentage"],
        total_questions=eval_result["total"],
        correct_answers_count=eval_result["correct_count"],
        feedback=eval_result["feedback"],
        weak_concepts=eval_result.get("weak_concepts", []),
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)

    # Build per-question result details for the frontend
    question_results = []
    for q in questions:
        selected = submission.answers.get(q.id, "")
        is_correct = AssessmentAgent.is_correct(q.correct_answer, selected, question_type=q.question_type)
        question_results.append({
            "question_id": q.id,
            "question_text": q.question_text,
            "question_type": q.question_type,
            "options": q.options or [],
            "correct_answer": q.correct_answer,
            "selected_answer": selected,
            "is_correct": is_correct,
            "explanation": q.explanation or "",
        })

    return QuizAttemptDetailResponse(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        score_percentage=attempt.score_percentage,
        total_questions=attempt.total_questions,
        correct_answers_count=attempt.correct_answers_count,
        feedback=attempt.feedback,
        created_at=attempt.created_at,
        question_results=question_results,
    )


@router.get("/{quiz_id}/attempts", response_model=List[QuizAttemptResponse], status_code=status.HTTP_200_OK)
async def get_quiz_attempts(
    quiz_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all attempts for a given quiz."""
    quiz_res = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = quiz_res.scalars().first()
    if not quiz:
        raise NotFoundException("Quiz not found")
    if quiz.user_id != current_user.id:
        raise ForbiddenException("Unauthorized quiz access")

    attempts_res = await db.execute(
        select(QuizAttempt)
        .where(QuizAttempt.quiz_id == quiz_id, QuizAttempt.user_id == current_user.id)
        .order_by(QuizAttempt.id.desc())
    )
    attempts = attempts_res.scalars().all()
    return [QuizAttemptResponse.model_validate(a) for a in attempts]


@router.delete("/{quiz_id}", status_code=status.HTTP_200_OK)
async def delete_quiz(
    quiz_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a quiz and its associated questions."""
    quiz_res = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = quiz_res.scalars().first()
    if not quiz:
        raise NotFoundException("Quiz not found")
    if quiz.user_id != current_user.id:
        raise ForbiddenException("Unauthorized quiz access")

    # Delete associated questions
    questions = []
    if quiz.question_ids:
        q_res = await db.execute(select(Question).where(Question.id.in_(quiz.question_ids)))
        questions = q_res.scalars().all()
    for q in questions:
        await db.delete(q)

    await db.delete(quiz)
    await db.commit()
    return {"message": "Quiz deleted", "id": quiz_id}
