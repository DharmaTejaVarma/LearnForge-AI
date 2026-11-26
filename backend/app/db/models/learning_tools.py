from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import String, Integer, Float, ForeignKey, Text, Boolean, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

class AgentExecutionLog(Base, TimestampMixin):
    __tablename__ = "agent_execution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="success", nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    input_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

class Flashcard(Base, TimestampMixin):
    __tablename__ = "flashcards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=True, index=True)
    document_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("uploaded_documents.id", ondelete="SET NULL"), nullable=True)

    front_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    back_answer: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mastery_level: Mapped[str] = mapped_column(String(32), default="new", nullable=False) # new, reviewing, mastered
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5, nullable=False)
    interval_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_review_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

class Question(Base, TimestampMixin):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=True, index=True)
    document_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("uploaded_documents.id", ondelete="SET NULL"), nullable=True)

    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(32), default="mcq", nullable=False) # mcq, short_answer
    options: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list) # List of 4 choices for MCQ
    correct_answer: Mapped[str] = mapped_column(String(255), nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)

class Quiz(Base, TimestampMixin):
    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=True, index=True)
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    question_ids: Mapped[List[int]] = mapped_column(JSON, default=list, nullable=False)

class QuizAttempt(Base, TimestampMixin):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    quiz_id: Mapped[int] = mapped_column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)

    score_percentage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_answers_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    weak_concepts: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)

class TutorConversation(Base, TimestampMixin):
    __tablename__ = "tutor_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("uploaded_documents.id", ondelete="SET NULL"), nullable=True)
    course_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    conversation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    intent: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, default=list)

class LearningProgress(Base, TimestampMixin):
    __tablename__ = "learning_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)

    completed_lessons: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_lessons: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mastery_percentage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    weak_topics: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)
