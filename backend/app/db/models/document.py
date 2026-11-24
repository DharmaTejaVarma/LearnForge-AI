from typing import Any, Optional
from sqlalchemy import JSON, String, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

class UploadedDocument(Base, TimestampMixin):
    __tablename__ = "uploaded_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    character_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processing_status: Mapped[str] = mapped_column(String(32), default="uploaded", nullable=False) # uploaded, processed, indexed, failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    structure: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)  # Phase 5: extracted TOC/heading structure

    user = relationship("User", backref="documents")

    def __repr__(self) -> str:
        return f"<UploadedDocument id={self.id} name={self.original_filename} status={self.processing_status}>"
