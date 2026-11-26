from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.course import Course, Chapter, Topic, Lesson
from app.db.models.document import UploadedDocument
from app.db.models.learning_tools import Flashcard, QuizAttempt, TutorConversation, LearningProgress


class AnalyticsAgent:
    """
    Analyzes database learning history across courses, lessons, flashcards, quizzes,
    and tutor conversations to compute weak topics, weekly study activity, and next steps.
    """

    @staticmethod
    async def analyze_user_learning(db: AsyncSession, user_id: int) -> Dict[str, Any]:
        # 1. Courses & lesson completion breakdown
        course_rows_res = await db.execute(
            select(
                Course.id,
                Course.title,
                func.count(Lesson.id).label("total_lessons"),
                func.coalesce(func.sum(case((Lesson.is_completed.is_(True), 1), else_=0)), 0).label("completed_lessons"),
            )
            .outerjoin(Chapter, Chapter.course_id == Course.id)
            .outerjoin(Topic, Topic.chapter_id == Chapter.id)
            .outerjoin(Lesson, Lesson.topic_id == Topic.id)
            .where(Course.user_id == user_id)
            .group_by(Course.id, Course.title)
            .order_by(Course.id.desc())
        )
        course_rows = course_rows_res.all()

        total_courses = len(course_rows)
        total_lessons = sum(int(r.total_lessons or 0) for r in course_rows)
        completed_lessons = sum(int(r.completed_lessons or 0) for r in course_rows)

        # 2. Documents count
        docs_res = await db.execute(
            select(func.count(UploadedDocument.id)).where(UploadedDocument.user_id == user_id)
        )
        total_docs = int(docs_res.scalar() or 0)

        # 3. Flashcards aggregate + due for SM-2 review
        now_utc = datetime.utcnow()
        fc_res = await db.execute(
            select(
                func.count(Flashcard.id),
                func.coalesce(func.sum(case((Flashcard.mastery_level == "mastered", 1), else_=0)), 0),
                func.coalesce(func.sum(Flashcard.review_count), 0),
                func.coalesce(
                    func.sum(
                        case(
                            ((Flashcard.next_review_at.is_(None)) | (Flashcard.next_review_at <= now_utc), 1),
                            else_=0,
                        )
                    ),
                    0,
                ),
            ).where(Flashcard.user_id == user_id)
        )
        total_fc, mastered_fc, total_fc_reviews, due_fc = fc_res.one()
        total_flashcards = int(total_fc or 0)
        mastered_flashcards = int(mastered_fc or 0)
        flashcards_reviewed = int(total_fc_reviews or 0)
        flashcards_due = int(due_fc or 0)

        # 4. Quiz attempts aggregate & weak concepts from recent attempts
        qa_res = await db.execute(
            select(QuizAttempt)
            .where(QuizAttempt.user_id == user_id)
            .order_by(QuizAttempt.id.desc())
            .limit(30)
        )
        recent_attempts = qa_res.scalars().all()
        quizzes_taken = len(recent_attempts)
        if quizzes_taken > 0:
            # Query exact total count & avg across all user attempts if > 30
            qa_agg_res = await db.execute(
                select(func.count(QuizAttempt.id), func.coalesce(func.avg(QuizAttempt.score_percentage), 0.0)).where(
                    QuizAttempt.user_id == user_id
                )
            )
            q_cnt, q_avg = qa_agg_res.one()
            quizzes_taken = int(q_cnt or 0)
            avg_score = round(float(q_avg or 0.0), 2)
        else:
            avg_score = 0.0

        # Extract real weak topics from quiz weak_concepts and low-scoring unmastered flashcards
        weak_topic_counts: Dict[str, int] = {}
        for att in recent_attempts:
            if att.score_percentage < 85.0 and att.weak_concepts:
                for wc in att.weak_concepts:
                    label = str(wc).strip()
                    if label:
                        weak_topic_counts[label[:120]] = weak_topic_counts.get(label[:120], 0) + 1

        # Include unmastered flashcard prompts if no quiz weak concepts yet
        if not weak_topic_counts and total_flashcards > mastered_flashcards:
            fc_weak_res = await db.execute(
                select(Flashcard.front_prompt)
                .where(Flashcard.user_id == user_id, Flashcard.mastery_level != "mastered")
                .order_by(Flashcard.review_count.asc())
                .limit(3)
            )
            for (prompt,) in fc_weak_res.all():
                short_p = str(prompt).strip()[:90]
                if short_p:
                    weak_topic_counts[short_p] = 1

        weak_topics = [
            k for k, _ in sorted(weak_topic_counts.items(), key=lambda kv: kv[1], reverse=True)
        ][:5]

        # 5. Course progress & recommended next lessons (real incomplete lessons)
        course_progress: List[Dict[str, Any]] = []
        for row in course_rows:
            t_les = int(row.total_lessons or 0)
            c_les = int(row.completed_lessons or 0)
            pct = round((c_les / t_les * 100), 1) if t_les > 0 else 0.0
            course_progress.append({
                "course_id": row.id,
                "title": row.title,
                "completed_lessons": c_les,
                "total_lessons": t_les,
                "completion_percentage": pct,
            })

            # Sync LearningProgress table
            lp_res = await db.execute(
                select(LearningProgress).where(
                    LearningProgress.user_id == user_id, LearningProgress.course_id == row.id
                )
            )
            lp = lp_res.scalars().first()
            if lp:
                lp.completed_lessons = c_les
                lp.total_lessons = t_les
                lp.mastery_percentage = pct
                lp.weak_topics = weak_topics
            else:
                db.add(LearningProgress(
                    user_id=user_id,
                    course_id=row.id,
                    completed_lessons=c_les,
                    total_lessons=t_les,
                    mastery_percentage=pct,
                    weak_topics=weak_topics,
                ))
        await db.commit()

        next_lessons_res = await db.execute(
            select(Lesson.id, Lesson.title, Course.id.label("course_id"), Course.title.label("course_title"))
            .join(Topic, Lesson.topic_id == Topic.id)
            .join(Chapter, Topic.chapter_id == Chapter.id)
            .join(Course, Chapter.course_id == Course.id)
            .where(Course.user_id == user_id, Lesson.is_completed.is_(False))
            .order_by(Course.id.desc(), Chapter.order_index.asc(), Topic.order_index.asc())
            .limit(4)
        )
        recommended_next_lessons = [
            {
                "lesson_id": r.id,
                "lesson_title": r.title,
                "course_id": r.course_id,
                "course_title": r.course_title,
            }
            for r in next_lessons_res.all()
        ]

        # 6. 7-day weekly study activity computed from real DB timestamps
        since_date = now_utc - timedelta(days=6)
        day_buckets: Dict[str, int] = {}
        for offset in range(6, -1, -1):
            d_str = (now_utc - timedelta(days=offset)).strftime("%Y-%m-%d")
            day_buckets[d_str] = 0

        for model_col in (QuizAttempt.created_at, TutorConversation.created_at):
            model_cls = model_col.class_
            rows = await db.execute(
                select(model_col).where(model_cls.user_id == user_id, model_col >= since_date)
            )
            for (ts,) in rows.all():
                if ts:
                    key = ts.strftime("%Y-%m-%d")
                    if key in day_buckets:
                        day_buckets[key] += 1

        fc_activity_rows = await db.execute(
            select(Flashcard.last_reviewed_at).where(
                Flashcard.user_id == user_id,
                Flashcard.last_reviewed_at.is_not(None),
                Flashcard.last_reviewed_at >= since_date,
            )
        )
        for (ts,) in fc_activity_rows.all():
            if ts:
                key = ts.strftime("%Y-%m-%d")
                if key in day_buckets:
                    day_buckets[key] += 1

        lesson_activity_rows = await db.execute(
            select(Lesson.updated_at)
            .join(Topic, Lesson.topic_id == Topic.id)
            .join(Chapter, Topic.chapter_id == Chapter.id)
            .join(Course, Chapter.course_id == Course.id)
            .where(Course.user_id == user_id, Lesson.is_completed.is_(True), Lesson.updated_at >= since_date)
        )
        for (ts,) in lesson_activity_rows.all():
            if ts:
                key = ts.strftime("%Y-%m-%d")
                if key in day_buckets:
                    day_buckets[key] += 1

        weekly_activity = [
            {
                "date": d_key,
                "label": datetime.strptime(d_key, "%Y-%m-%d").strftime("%a"),
                "actions": count_val,
            }
            for d_key, count_val in day_buckets.items()
        ]

        # 7. Overall mastery & personalized recommendations
        lesson_pct = (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0.0
        fc_pct = (mastered_flashcards / total_flashcards * 100) if total_flashcards > 0 else 0.0
        quiz_pct = avg_score

        components = [c for c in [lesson_pct, fc_pct, quiz_pct] if c > 0]
        overall_mastery = round(sum(components) / len(components), 1) if components else 0.0

        recommendations: List[str] = []
        if flashcards_due > 0:
            recommendations.append(f"Review {flashcards_due} spaced-repetition flashcard(s) currently due.")
        if recommended_next_lessons:
            nxt = recommended_next_lessons[0]
            recommendations.append(f"Continue '{nxt['course_title']}' with lesson '{nxt['lesson_title']}'.")
        if quizzes_taken == 0 and total_docs > 0:
            recommendations.append("Take an adaptive quiz to establish a baseline accuracy score.")
        elif quizzes_taken > 0 and avg_score < 75.0:
            recommendations.append("Revisit missed quiz concepts in the AI Tutor before your next assessment.")

        return {
            "user_id": user_id,
            "total_courses": total_courses,
            "total_documents": total_docs,
            "completed_lessons": completed_lessons,
            "total_lessons": total_lessons,
            "flashcards_mastered": mastered_flashcards,
            "total_flashcards": total_flashcards,
            "flashcards_reviewed": flashcards_reviewed,
            "flashcards_due": flashcards_due,
            "quizzes_taken": quizzes_taken,
            "average_quiz_score": avg_score,
            "overall_mastery_percentage": overall_mastery,
            "weak_topics": weak_topics,
            "recommendations": recommendations,
            "course_progress": course_progress,
            "recommended_next_lessons": recommended_next_lessons,
            "weekly_activity": weekly_activity,
        }
