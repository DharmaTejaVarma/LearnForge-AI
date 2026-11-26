from typing import List, Optional, Dict, Any
from sqlalchemy import String, Integer, Float, ForeignKey, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

class Course(Base, TimestampMixin):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("uploaded_documents.id", ondelete="SET NULL"), nullable=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    difficulty_level: Mapped[str] = mapped_column(String(32), default="intermediate", nullable=False)
    estimated_duration_hours: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    learning_objectives: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)
    prerequisites: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)
    document_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    user = relationship("User", backref="courses")
    document = relationship("UploadedDocument", backref="courses")
    chapters = relationship("Chapter", back_populates="course", cascade="all, delete-orphan", order_by="Chapter.order_index")
    assessments = relationship("CourseAssessment", back_populates="course", cascade="all, delete-orphan")
    generation_jobs = relationship("GenerationJob", back_populates="course", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Course id={self.id} title={self.title}>"

class Chapter(Base, TimestampMixin):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    page_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    printed_page_start: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    printed_page_end: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    learning_outcomes: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)

    course = relationship("Course", back_populates="chapters")
    topics = relationship("Topic", back_populates="chapter", cascade="all, delete-orphan", order_by="Topic.order_index")

class Topic(Base, TimestampMixin):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    chapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    chapter = relationship("Chapter", back_populates="topics")
    lesson = relationship("Lesson", back_populates="topic", uselist=False, cascade="all, delete-orphan")

class Lesson(Base, TimestampMixin):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    topic_id: Mapped[int] = mapped_column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False) # Rich Markdown
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_takeaways: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)
    source_pages: Mapped[Optional[List[int]]] = mapped_column(JSON, default=list)
    printed_pages: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=10, server_default="10", nullable=False)
    prerequisites: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)
    learning_objectives: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)
    structured_sections: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
    cache_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Phase 5: page-range tracking and generation status
    page_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    generation_status: Mapped[str] = mapped_column(String(32), default="ready", nullable=False)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    generation_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    topic = relationship("Topic", back_populates="lesson")
    exercises = relationship("LessonExercise", back_populates="lesson", cascade="all, delete-orphan", order_by="LessonExercise.order_index")
    notes = relationship("LessonNote", back_populates="lesson", cascade="all, delete-orphan")


class LessonExercise(Base, TimestampMixin):
    __tablename__ = "lesson_exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    lesson_id: Mapped[int] = mapped_column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    exercise_type: Mapped[str] = mapped_column(String(32), nullable=False)  # mcq, coding, debugging, fill_blank, mini_task
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    starter_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    buggy_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    options: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)
    option_explanations: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)
    correct_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    test_cases: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, default=list)
    hints: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str] = mapped_column(String(32), default="intermediate", server_default="intermediate", nullable=False)

    lesson = relationship("Lesson", back_populates="exercises")
    submissions = relationship("ExerciseSubmission", back_populates="exercise", cascade="all, delete-orphan")


class ExerciseSubmission(Base, TimestampMixin):
    __tablename__ = "exercise_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    exercise_id: Mapped[int] = mapped_column(Integer, ForeignKey("lesson_exercises.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    submitted_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, server_default="0", nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    execution_stdout: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_stderr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    exercise = relationship("LessonExercise", back_populates="submissions")


class CourseAssessment(Base, TimestampMixin):
    __tablename__ = "course_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True, index=True)
    assessment_type: Mapped[str] = mapped_column(String(32), default="module", server_default="module", nullable=False)  # module | final
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    passing_score: Mapped[float] = mapped_column(Float, default=70.0, server_default="70", nullable=False)
    questions: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, default=list)

    course = relationship("Course", back_populates="assessments")
    attempts = relationship("CourseAssessmentAttempt", back_populates="assessment", cascade="all, delete-orphan")


class CourseAssessmentAttempt(Base, TimestampMixin):
    __tablename__ = "course_assessment_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    assessment_id: Mapped[int] = mapped_column(Integer, ForeignKey("course_assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    answers: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
    score: Mapped[float] = mapped_column(Float, default=0.0, server_default="0", nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    topic_breakdown: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, default=list)
    recommended_lesson_ids: Mapped[Optional[List[int]]] = mapped_column(JSON, default=list)

    assessment = relationship("CourseAssessment", back_populates="attempts")


class LessonNote(Base, TimestampMixin):
    __tablename__ = "lesson_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    lesson_id: Mapped[int] = mapped_column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    is_bookmarked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)

    lesson = relationship("Lesson", back_populates="notes")


class GenerationJob(Base, TimestampMixin):
    __tablename__ = "generation_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(64), default="course_lessons", server_default="course_lessons", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="running", server_default="running", nullable=False)
    total_items: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    completed_items: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    current_stage: Mapped[str] = mapped_column(String(128), default="Initializing", server_default="Initializing", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    course = relationship("Course", back_populates="generation_jobs")


class LessonGenerationJob(Base, TimestampMixin):
    __tablename__ = "lesson_generation_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    lesson_id: Mapped[int] = mapped_column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(32), default="on_demand", server_default="on_demand", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", server_default="QUEUED", nullable=False, index=True)
    current_stage: Mapped[str] = mapped_column(String(128), default="Preparing source material", server_default="Preparing source material", nullable=False)
    started_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    completed_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
