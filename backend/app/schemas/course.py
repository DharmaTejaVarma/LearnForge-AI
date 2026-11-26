from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class LessonCreate(BaseModel):
    title: str
    content: str
    summary: Optional[str] = None
    key_takeaways: Optional[List[str]] = Field(default_factory=list)
    source_pages: Optional[List[int]] = Field(default_factory=list)


class LessonExerciseResponse(BaseModel):
    id: int
    lesson_id: int
    order_index: int = 0
    exercise_type: str
    title: str
    prompt: str
    starter_code: Optional[str] = None
    buggy_code: Optional[str] = None
    options: Optional[List[str]] = Field(default_factory=list)
    option_explanations: Optional[List[str]] = Field(default_factory=list)
    expected_output: Optional[str] = None
    test_cases: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    hints: Optional[List[str]] = Field(default_factory=list)
    difficulty: str = "intermediate"
    # Latest user attempt status (populated per-user in service)
    latest_is_correct: Optional[bool] = None
    latest_score: Optional[float] = None
    attempts_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ExerciseSubmitRequest(BaseModel):
    answer: Optional[str] = None
    code: Optional[str] = None


class ExerciseSubmitResponse(BaseModel):
    exercise_id: int
    is_correct: bool
    score: float
    attempt_number: int
    feedback: str
    explanation: Optional[str] = None
    option_feedback: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    test_results: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class CodeRunRequest(BaseModel):
    code: str


class CodeRunResponse(BaseModel):
    passed: bool
    passed_tests: int
    total_tests: int
    stdout: str = ""
    stderr: str = ""
    results: List[Dict[str, Any]] = Field(default_factory=list)
    timed_out: bool = False


class LessonNoteRequest(BaseModel):
    content: Optional[str] = None
    is_bookmarked: Optional[bool] = None


class LessonNoteResponse(BaseModel):
    lesson_id: int
    content: str = ""
    is_bookmarked: bool = False
    updated_at: Optional[datetime] = None


class LessonResponse(BaseModel):
    id: int
    topic_id: int
    title: str
    content: str
    summary: Optional[str] = None
    key_takeaways: Optional[List[str]] = Field(default_factory=list)
    source_pages: Optional[List[int]] = Field(default_factory=list)
    printed_pages: Optional[List[str]] = Field(default_factory=list)
    estimated_minutes: int = 10
    prerequisites: Optional[List[str]] = Field(default_factory=list)
    learning_objectives: Optional[List[str]] = Field(default_factory=list)
    structured_sections: Optional[Dict[str, Any]] = Field(default_factory=dict)
    is_completed: bool
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    generation_status: str = "ready"
    generation_error: Optional[str] = None
    exercises: List[LessonExerciseResponse] = Field(default_factory=list)
    note: Optional[LessonNoteResponse] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TopicResponse(BaseModel):
    id: int
    chapter_id: int
    title: str
    order_index: int
    lesson: Optional[LessonResponse] = None

    model_config = ConfigDict(from_attributes=True)

class ChapterResponse(BaseModel):
    id: int
    course_id: int
    title: str
    description: Optional[str] = None
    order_index: int
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    printed_page_start: Optional[str] = None
    printed_page_end: Optional[str] = None
    learning_outcomes: Optional[List[str]] = Field(default_factory=list)
    topics: List[TopicResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class GenerationJobResponse(BaseModel):
    id: int
    course_id: int
    job_type: str
    status: str
    total_items: int
    completed_items: int
    current_stage: str
    error_message: Optional[str] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CourseBase(BaseModel):
    title: str
    description: str
    category: Optional[str] = None
    difficulty_level: str = "intermediate"
    estimated_duration_hours: int = 5
    learning_objectives: Optional[List[str]] = Field(default_factory=list)
    prerequisites: Optional[List[str]] = Field(default_factory=list)

class CourseGenerateRequest(BaseModel):
    document_id: int
    difficulty_level: Optional[str] = "intermediate"
    target_chapters_count: Optional[int] = Field(default=18, ge=1, le=24)

class CourseResponse(CourseBase):
    id: int
    user_id: int
    document_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CourseDetailResponse(CourseResponse):
    chapters: List[ChapterResponse] = Field(default_factory=list)
    active_job: Optional[GenerationJobResponse] = None


class AssessmentQuestionItem(BaseModel):
    id: str
    question_type: str = "mcq"
    prompt: str
    options: List[str] = Field(default_factory=list)
    topic_id: Optional[int] = None
    topic_title: Optional[str] = None
    lesson_id: Optional[int] = None


class CourseAssessmentResponse(BaseModel):
    id: int
    course_id: int
    chapter_id: Optional[int] = None
    assessment_type: str
    title: str
    description: Optional[str] = None
    passing_score: float = 70.0
    questions: List[AssessmentQuestionItem] = Field(default_factory=list)
    best_score: Optional[float] = None
    passed: bool = False

    model_config = ConfigDict(from_attributes=True)


class AssessmentSubmitRequest(BaseModel):
    answers: Dict[str, str]


class AssessmentResultResponse(BaseModel):
    assessment_id: int
    score: float
    passed: bool
    correct_count: int
    total_questions: int
    topic_breakdown: List[Dict[str, Any]] = Field(default_factory=list)
    recommended_lesson_ids: List[int] = Field(default_factory=list)
    question_feedback: List[Dict[str, Any]] = Field(default_factory=list)
