from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, status
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
    """Upload and process an educational document (PDF or DOCX)."""
    return await DocumentService.upload_document(db, current_user.id, file)

@router.get("", response_model=List[DocumentResponse], status_code=status.HTTP_200_OK)
@router.get("/", response_model=List[DocumentResponse], status_code=status.HTTP_200_OK)
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all educational documents uploaded by the authenticated user."""
    return await DocumentService.list_user_documents(db, current_user.id)

@router.get("/{document_id}", response_model=DocumentDetailResponse, status_code=status.HTTP_200_OK)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details of a specific uploaded document."""
    doc = await DocumentService.get_user_document(db, current_user.id, document_id)
    return DocumentDetailResponse.model_validate(doc)

@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an uploaded document and its physical file from disk."""
    return await DocumentService.delete_document(db, current_user.id, document_id)
