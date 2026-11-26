from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# Flashcard Schemas
class FlashcardCreate(BaseModel):
    course_id: Optional[int] = None
    document_id: Optional[int] = None
    count: Optional[int] = 5
    difficulty: Optional[str] = "medium"

class FlashcardResponse(BaseModel):
    id: int
    user_id: int
    course_id: Optional[int] = None
    document_id: Optional[int] = None
    front_prompt: str
    back_answer: str
    difficulty: str = "medium"
    review_count: int
    mastery_level: str
    ease_factor: float = 2.5
    interval_days: int = 0
    next_review_at: Optional[datetime] = None
    last_reviewed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class FlashcardReviewUpdate(BaseModel):
    mastered: bool

# Question & Quiz Schemas
class QuestionResponse(BaseModel):
    id: int
    user_id: int
    course_id: Optional[int] = None
    document_id: Optional[int] = None
    question_text: str
    question_type: str
    options: Optional[List[str]] = Field(default_factory=list)
    correct_answer: str
    explanation: Optional[str] = None
    difficulty: str

    model_config = ConfigDict(from_attributes=True)

class QuizGenerateRequest(BaseModel):
    course_id: Optional[int] = None
    document_id: Optional[int] = None
    question_count: Optional[int] = 5
    difficulty: Optional[str] = "medium"
    question_type: Optional[str] = "mcq"  # mcq, true_false, short_answer, mixed

class QuizListItem(BaseModel):
    id: int
    user_id: int
    course_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    question_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class QuizResponse(BaseModel):
    id: int
    user_id: int
    course_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    questions: List[QuestionResponse] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class QuizSubmitRequest(BaseModel):
    answers: Dict[int, str] # question_id -> selected_option

class QuizAttemptResponse(BaseModel):
    id: int
    quiz_id: int
    score_percentage: float
    total_questions: int
    correct_answers_count: int
    feedback: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QuestionResult(BaseModel):
    question_id: int
    question_text: str
    question_type: str = "mcq"
    options: List[str] = Field(default_factory=list)
    correct_answer: str
    selected_answer: str
    is_correct: bool
    explanation: str = ""


class QuizAttemptDetailResponse(BaseModel):
    id: int
    quiz_id: int
    score_percentage: float
    total_questions: int
    correct_answers_count: int
    feedback: Optional[str] = None
    created_at: datetime
    question_results: List[QuestionResult] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

# Tutor Schemas
class TutorChatRequest(BaseModel):
    question: str
    document_id: Optional[int] = None
    course_id: Optional[int] = None
    lesson_id: Optional[int] = None
    exercise_id: Optional[int] = None
    tutor_mode: Optional[str] = None  # explain_simple | explain_code | hint_only | practice_question
    conversation_id: Optional[str] = None

class Citation(BaseModel):
    document_id: int
    filename: Optional[str] = None
    page_number: int
    similarity_score: float

class TutorResource(BaseModel):
    title: str
    source_type: str
    page_number: Optional[int] = None
    document_id: Optional[int] = None
    description: Optional[str] = None

class TutorChatResponse(BaseModel):
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    resources: List[TutorResource] = Field(default_factory=list)
    provider_used: str
    latency_ms: float
    conversation_id: Optional[str] = None
    intent: Optional[str] = None

class TutorConversationItem(BaseModel):
    id: int
    conversation_id: Optional[str] = None
    question: str
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    intent: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TutorSuggestionResponse(BaseModel):
    suggestions: List[str] = Field(default_factory=list)

# Progress Schemas
class WeeklyActivityItem(BaseModel):
    date: str
    label: str
    actions: int

class CourseProgressItem(BaseModel):
    course_id: int
    title: str
    completed_lessons: int
    total_lessons: int
    completion_percentage: float

class RecommendedLessonItem(BaseModel):
    lesson_id: int
    lesson_title: str
    course_id: int
    course_title: str

class ProgressResponse(BaseModel):
    user_id: int
    total_courses: int
    total_documents: int
    completed_lessons: int
    total_lessons: int
    flashcards_mastered: int
    total_flashcards: int
    flashcards_reviewed: int = 0
    flashcards_due: int = 0
    quizzes_taken: int
    average_quiz_score: float
    overall_mastery_percentage: float
    weak_topics: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    course_progress: List[CourseProgressItem] = Field(default_factory=list)
    recommended_next_lessons: List[RecommendedLessonItem] = Field(default_factory=list)
    weekly_activity: List[WeeklyActivityItem] = Field(default_factory=list)
