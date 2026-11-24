from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime

class LessonCreate(BaseModel):
    title: str
    content: str
    summary: Optional[str] = None
    key_takeaways: Optional[List[str]] = Field(default_factory=list)
    source_pages: Optional[List[int]] = Field(default_factory=list)

class LessonResponse(BaseModel):
    id: int
    topic_id: int
    title: str
    content: str
    summary: Optional[str] = None
    key_takeaways: Optional[List[str]] = Field(default_factory=list)
    source_pages: Optional[List[int]] = Field(default_factory=list)
    is_completed: bool
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    generation_status: str = "ready"
    generation_error: Optional[str] = None
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
    topics: List[TopicResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

class CourseBase(BaseModel):
    title: str
    description: str
    difficulty_level: str = "intermediate"
    estimated_duration_hours: int = 5
    learning_objectives: Optional[List[str]] = Field(default_factory=list)

class CourseGenerateRequest(BaseModel):
    document_id: int
    difficulty_level: Optional[str] = "intermediate"
    target_chapters_count: Optional[int] = 3

class CourseResponse(CourseBase):
    id: int
    user_id: int
    document_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CourseDetailResponse(CourseResponse):
    chapters: List[ChapterResponse] = Field(default_factory=list)
