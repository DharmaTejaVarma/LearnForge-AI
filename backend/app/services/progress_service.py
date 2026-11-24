from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.course import Course, Chapter, Topic, Lesson
from app.db.models.document import UploadedDocument
from app.db.models.learning_tools import Flashcard, QuizAttempt
from app.schemas.learning_tools import ProgressResponse

class ProgressService:
    @staticmethod
    async def get_user_progress(db: AsyncSession, user_id: int) -> ProgressResponse:
        # Courses count
        courses_res = await db.execute(
            select(func.count(Course.id)).where(Course.user_id == user_id)
        )
        total_courses = courses_res.scalar() or 0

        # Documents count
        docs_res = await db.execute(
            select(func.count(UploadedDocument.id)).where(UploadedDocument.user_id == user_id)
        )
        total_docs = docs_res.scalar() or 0

        # Lessons count via joins
        lessons_res = await db.execute(
            select(Lesson)
            .join(Topic, Lesson.topic_id == Topic.id)
            .join(Chapter, Topic.chapter_id == Chapter.id)
            .join(Course, Chapter.course_id == Course.id)
            .where(Course.user_id == user_id)
        )
        user_lessons = lessons_res.scalars().all()
        total_lessons = len(user_lessons)
        completed_lessons = sum(1 for l in user_lessons if l.is_completed)

        # Flashcards
        fc_res = await db.execute(
            select(Flashcard).where(Flashcard.user_id == user_id)
        )
        all_flashcards = fc_res.scalars().all()
        total_flashcards = len(all_flashcards)
        mastered_flashcards = sum(1 for fc in all_flashcards if fc.mastery_level == "mastered")

        # Quizzes
        qa_res = await db.execute(
            select(QuizAttempt).where(QuizAttempt.user_id == user_id)
        )
        attempts = qa_res.scalars().all()
        quizzes_taken = len(attempts)
        avg_score = round(sum(a.score_percentage for a in attempts) / quizzes_taken, 2) if quizzes_taken > 0 else 0.0

        # Overall Mastery
        lesson_pct = (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0.0
        fc_pct = (mastered_flashcards / total_flashcards * 100) if total_flashcards > 0 else 0.0
        quiz_pct = avg_score

        components = [c for c in [lesson_pct, fc_pct, quiz_pct] if c > 0]
        overall_mastery = round(sum(components) / len(components), 1) if components else 0.0

        return ProgressResponse(
            user_id=user_id,
            total_courses=total_courses,
            total_documents=total_docs,
            completed_lessons=completed_lessons,
            total_lessons=total_lessons,
            flashcards_mastered=mastered_flashcards,
            total_flashcards=total_flashcards,
            quizzes_taken=quizzes_taken,
            average_quiz_score=avg_score,
            overall_mastery_percentage=overall_mastery,
            weak_topics=["Review foundational definitions", "Practice active recall flashcards"] if overall_mastery < 60 else []
        )
