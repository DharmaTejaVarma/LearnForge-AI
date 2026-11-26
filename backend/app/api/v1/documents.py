from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models.user import User
from app.api.dependencies.auth import get_current_user
from app.schemas.document import DocumentResponse, DocumentDetailResponse
from app.services.document_service import DocumentService

router = APIRouter()

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload and process an educational document (PDF, DOCX, TXT, PPTX, Markdown)."""
    return await DocumentService.upload_document(db, current_user.id, file)

@router.get("", response_model=List[DocumentResponse], status_code=status.HTTP_200_OK)
@router.get("/", response_model=List[DocumentResponse], status_code=status.HTTP_200_OK)
async def list_documents(
    search: Optional[str] = Query(None, description="Filter documents by filename"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by processing status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List educational documents uploaded by the authenticated user with optional search & pagination."""
    return await DocumentService.list_user_documents(
        db, current_user.id, search=search, status_filter=status_filter, skip=skip, limit=limit
    )

@router.get("/{document_id}", response_model=DocumentDetailResponse, status_code=status.HTTP_200_OK)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details of a specific uploaded document."""
    doc = await DocumentService.get_user_document(db, current_user.id, document_id)
    return DocumentDetailResponse.model_validate(doc)

@router.post("/{document_id}/reprocess", response_model=DocumentResponse, status_code=status.HTTP_200_OK)
async def reprocess_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-extract text, rebuild chunks, and re-index vectors for an existing document."""
    return await DocumentService.reprocess_document(db, current_user.id, document_id)

@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an uploaded document and its physical file from disk."""
    return await DocumentService.delete_document(db, current_user.id, document_id)
