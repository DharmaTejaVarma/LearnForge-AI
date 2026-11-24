import os
import uuid
import hashlib
from pathlib import Path
from typing import List, Optional
from fastapi import UploadFile
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.exceptions import BadRequestException, NotFoundException, ForbiddenException
from app.core.logging import logger
from app.db.models.document import UploadedDocument
from app.schemas.document import DocumentResponse, DocumentDetailResponse
from app.ai.rag.document_loader import DocumentLoader
from app.ai.rag.text_cleaner import TextCleaner
from app.ai.rag.chunking import ChunkingService
from app.ai.embeddings.embedding_service import EmbeddingService
from app.ai.rag.vector_store import VectorStoreManager

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".pptx", ".md", ".markdown"}

class DocumentService:
    @staticmethod
    async def upload_document(
        db: AsyncSession,
        user_id: int,
        file: UploadFile,
    ) -> DocumentResponse:
        original_name = file.filename or "unknown_document"
        file_ext = Path(original_name).suffix.lower()

        if file_ext not in ALLOWED_EXTENSIONS:
            raise BadRequestException(
                f"Unsupported file format: '{file_ext}'. Allowed formats are: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        content = await file.read()
        file_size = len(content)

        if file_size > MAX_FILE_SIZE:
            raise BadRequestException(
                f"File size exceeds maximum allowed limit of {MAX_FILE_SIZE // (1024 * 1024)}MB"
            )

        if file_size == 0:
            raise BadRequestException("Uploaded file is empty (0 bytes).")

        file_hash = hashlib.sha256(content).hexdigest()

        # Generate unique local stored filename
        unique_id = uuid.uuid4().hex
        clean_stem = "".join(c for c in Path(original_name).stem if c.isalnum() or c in ("-", "_"))[:30]
        stored_filename = f"{unique_id}_{clean_stem}{file_ext}"

        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / stored_filename

        # Write to local filesystem
        file_path.write_bytes(content)
        logger.info(f"Stored uploaded file locally: {file_path}")

        # Insert metadata in database
        doc = UploadedDocument(
            user_id=user_id,
            original_filename=original_name,
            stored_filename=stored_filename,
            file_path=str(file_path.resolve()),
            file_size=file_size,
            mime_type=file.content_type or f"application/{file_ext[1:]}",
            file_hash=file_hash,
            processing_status="uploaded",
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        # Extract text via Universal DocumentLoader
        try:
            extracted_pages = DocumentLoader.load_document(str(file_path), doc.mime_type)
            cleaned_pages = TextCleaner.clean_document_pages(extracted_pages)
            total_chars = sum(p["char_count"] for p in cleaned_pages)
            page_count = len(cleaned_pages)

            doc.page_count = page_count
            doc.character_count = total_chars
            doc.processing_status = "processed"
            await db.commit()
            await db.refresh(doc)

            # RAG Pipeline: Chunking & Local Vector Indexing
            chunker = ChunkingService(chunk_size=800, chunk_overlap=150)
            chunks = chunker.chunk_pages(
                pages=cleaned_pages,
                document_id=doc.id,
                user_id=user_id,
                filename=original_name,
            )

            if chunks:
                texts = [c["text"] for c in chunks]
                embeddings = EmbeddingService.embed_texts(texts)
                VectorStoreManager.index_document_chunks(
                    user_id=user_id,
                    document_id=doc.id,
                    chunks=chunks,
                    embeddings=embeddings,
                )
                doc.processing_status = "indexed"
                await db.commit()
                await db.refresh(doc)

            logger.info(f"Successfully processed & indexed document id={doc.id}: {page_count} pages, {len(chunks)} chunks")
        except Exception as e:
            logger.warning(f"RAG processing failed for document id={doc.id}: {e}")
            doc.processing_status = "failed"
            doc.error_message = str(e)
            await db.commit()
            await db.refresh(doc)
            raise

        return DocumentResponse.model_validate(doc)

    @staticmethod
    async def list_user_documents(db: AsyncSession, user_id: int) -> List[DocumentResponse]:
        query = select(UploadedDocument).where(UploadedDocument.user_id == user_id).order_by(UploadedDocument.id.desc())
        result = await db.execute(query)
        docs = result.scalars().all()
        return [DocumentResponse.model_validate(d) for d in docs]

    @staticmethod
    async def get_user_document(db: AsyncSession, user_id: int, doc_id: int) -> UploadedDocument:
        query = select(UploadedDocument).where(UploadedDocument.id == doc_id)
        result = await db.execute(query)
        doc = result.scalars().first()

        if not doc:
            raise NotFoundException("Document not found")
        if doc.user_id != user_id:
            raise ForbiddenException("You do not have permission to access this document")

        return doc

    @staticmethod
    async def delete_document(db: AsyncSession, user_id: int, doc_id: int) -> dict:
        doc = await DocumentService.get_user_document(db, user_id, doc_id)

        # 1. Remove vector records from ChromaDB
        VectorStoreManager.delete_document_vectors(user_id=user_id, document_id=doc_id)

        # 2. Remove local file from disk
        local_file = Path(doc.file_path)
        if local_file.exists():
            try:
                local_file.unlink()
                logger.info(f"Deleted local file from disk: {local_file}")
            except Exception as e:
                logger.warning(f"Could not remove local file {local_file}: {e}")

        # 3. Delete SQLite record
        await db.delete(doc)
        await db.commit()
        logger.info(f"Deleted document id={doc_id} from SQLite database")

        return {"message": "Document deleted successfully", "document_id": doc_id}
