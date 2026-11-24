from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class DocumentResponse(BaseModel):
    id: int
    user_id: int
    original_filename: str
    file_size: int
    mime_type: str
    page_count: Optional[int] = 0
    character_count: int
    processing_status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DocumentDetailResponse(DocumentResponse):
    stored_filename: str
