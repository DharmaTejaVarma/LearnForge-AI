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
    review_count: int
    mastery_level: str
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
    conversation_id: Optional[str] = None

class Citation(BaseModel):
    document_id: int
    filename: Optional[str] = None
    page_number: int
    similarity_score: float

class TutorChatResponse(BaseModel):
    answer: str
    citations: List[Citation] = Field(default_factory=list)
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
class ProgressResponse(BaseModel):
    user_id: int
    total_courses: int
    total_documents: int
    completed_lessons: int
    total_lessons: int
    flashcards_mastered: int
    total_flashcards: int
    quizzes_taken: int
    average_quiz_score: float
    overall_mastery_percentage: float
    weak_topics: List[str] = Field(default_factory=list)
