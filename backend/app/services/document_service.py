import asyncio
import os
import sys
import uuid
import hashlib
from pathlib import Path
from typing import List, Optional, Set
from fastapi import UploadFile
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.exceptions import BadRequestException, NotFoundException, ForbiddenException, ConflictException
from app.core.logging import logger
from app.db.database import AsyncSessionLocal
from app.db.models.document import UploadedDocument
from app.schemas.document import DocumentResponse, DocumentDetailResponse
from app.ai.rag.document_loader import DocumentLoader
from app.ai.rag.text_cleaner import TextCleaner
from app.ai.rag.chunking import ChunkingService
from app.ai.embeddings.embedding_service import EmbeddingService
from app.ai.rag.vector_store import VectorStoreManager

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".pptx", ".md", ".markdown"}
_doc_bg_tasks: Set[asyncio.Task] = set()
_indexing_sem: Optional[asyncio.Semaphore] = None
_EXTRACTED_PAGES_CACHE: dict[str, list[dict]] = {}
_DOC_PROGRESS: dict[int, dict] = {}


def _get_indexing_sem() -> asyncio.Semaphore:
    global _indexing_sem
    if _indexing_sem is None:
        _indexing_sem = asyncio.Semaphore(1)
    return _indexing_sem

class DocumentService:
    @staticmethod
    def get_cached_pages(file_hash: Optional[str]) -> Optional[List[dict]]:
        if not file_hash:
            return None
        return _EXTRACTED_PAGES_CACHE.get(file_hash)

    @staticmethod
    def get_document_progress(doc: UploadedDocument) -> dict:
        prog = _DOC_PROGRESS.get(doc.id)
        if prog:
            return dict(prog)
        st = doc.processing_status
        return {
            "document_id": doc.id,
            "filename": doc.original_filename,
            "extraction_status": "complete" if st in ("processed", "indexed") else ("failed" if st == "failed" else "waiting"),
            "embedding_status": "complete" if st == "indexed" else ("failed" if st == "failed" else "waiting"),
            "indexing_status": "complete" if st == "indexed" else ("failed" if st == "failed" else "waiting"),
            "chunks_total": 0,
            "chunks_embedded": 0,
        }

    @staticmethod
    def _validate_file_signature(file_ext: str, content: bytes) -> None:
        """Validate file magic bytes / binary safety against claimed extension."""
        if file_ext == ".pdf":
            if not content.lstrip()[:5].startswith(b"%PDF-"):
                raise BadRequestException("Invalid PDF signature: file content does not match PDF format.")
        elif file_ext in (".docx", ".pptx"):
            if not content.startswith(b"PK\x03\x04"):
                raise BadRequestException(f"Invalid {file_ext.upper()} archive signature: file may be corrupted or mismatched.")
        elif file_ext in (".txt", ".md", ".markdown"):
            if b"\x00" in content[:4096]:
                raise BadRequestException("Binary null bytes detected inside text/markdown document.")

    @staticmethod
    async def _extract_and_index_document(db: AsyncSession, doc: UploadedDocument) -> UploadedDocument:
        """Extract text, detect structural sections, chunk, embed, and index vectors into ChromaDB."""
        _DOC_PROGRESS[doc.id] = {
            "document_id": doc.id,
            "filename": doc.original_filename,
            "extraction_status": "running",
            "embedding_status": "waiting",
            "indexing_status": "waiting",
            "chunks_total": 0,
            "chunks_embedded": 0,
        }
        extracted_pages = await asyncio.to_thread(DocumentLoader.load_document, doc.file_path, doc.mime_type)
        cleaned_pages = await asyncio.to_thread(TextCleaner.clean_document_pages, extracted_pages)
        if doc.file_hash:
            if len(_EXTRACTED_PAGES_CACHE) >= 4:
                _EXTRACTED_PAGES_CACHE.pop(next(iter(_EXTRACTED_PAGES_CACHE)))
            _EXTRACTED_PAGES_CACHE[doc.file_hash] = cleaned_pages
        total_chars = sum(p["char_count"] for p in cleaned_pages)
        page_count = len(cleaned_pages)

        # Extract structural sections/headings when loader supports it
        structure = None
        if hasattr(DocumentLoader, "extract_structure"):
            try:
                structure = await asyncio.to_thread(DocumentLoader.extract_structure, doc.file_path, doc.mime_type)
            except Exception as struct_err:
                logger.debug(f"Structure extraction skipped for doc={doc.id}: {struct_err}")

        doc.page_count = page_count
        doc.character_count = total_chars
        doc.structure = structure
        doc.processing_status = "processed"
        doc.error_message = None
        await db.commit()
        await db.refresh(doc)

        async def _run_vector_indexing(doc_id: int, uid: int, fname: str, pages_data: List[dict]) -> None:
            async with _get_indexing_sem():
                _DOC_PROGRESS[doc_id] = {
                    "document_id": doc_id,
                    "filename": fname,
                    "extraction_status": "complete",
                    "embedding_status": "running",
                    "indexing_status": "waiting",
                    "chunks_total": 0,
                    "chunks_embedded": 0,
                }
                chunker = ChunkingService(chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP)
                chunks = await asyncio.to_thread(
                    chunker.chunk_pages,
                    pages=pages_data,
                    document_id=doc_id,
                    user_id=uid,
                    filename=fname,
                )
                if not chunks:
                    _DOC_PROGRESS[doc_id].update({"embedding_status": "complete", "indexing_status": "complete"})
                    return
                _DOC_PROGRESS[doc_id]["chunks_total"] = len(chunks)
                texts = [c["text"] for c in chunks]
                embeddings = await asyncio.to_thread(EmbeddingService.embed_texts, texts)
                _DOC_PROGRESS[doc_id].update({
                    "chunks_embedded": len(embeddings),
                    "embedding_status": "complete",
                    "indexing_status": "running",
                })
                await asyncio.to_thread(
                    VectorStoreManager.index_document_chunks,
                    user_id=uid,
                    document_id=doc_id,
                    chunks=chunks,
                    embeddings=embeddings,
                )
                async with AsyncSessionLocal() as bg_sess:
                    row = await bg_sess.get(UploadedDocument, doc_id)
                    if row:
                        row.processing_status = "indexed"
                        await bg_sess.commit()
                _DOC_PROGRESS[doc_id]["indexing_status"] = "complete"
                logger.info(f"Indexed document id={doc_id}: {page_count} pages, {len(chunks)} chunks")

        if "pytest" in sys.modules:
            await _run_vector_indexing(doc.id, doc.user_id, doc.original_filename, cleaned_pages)
            await db.refresh(doc)
        else:
            # Return immediately after text + structure extraction (~1s); embed & index vectors in background
            task = asyncio.create_task(
                _run_vector_indexing(doc.id, doc.user_id, doc.original_filename, cleaned_pages)
            )
            _doc_bg_tasks.add(task)
            task.add_done_callback(_doc_bg_tasks.discard)
            logger.info(f"Processed document id={doc.id} ({page_count} pages); background vector indexing queued")

        return doc

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

        DocumentService._validate_file_signature(file_ext, content)
        file_hash = hashlib.sha256(content).hexdigest()

        # Prevent duplicate processing for the same user & file hash
        dup_res = await db.execute(
            select(UploadedDocument).where(
                UploadedDocument.user_id == user_id,
                UploadedDocument.file_hash == file_hash,
                UploadedDocument.processing_status.in_(["processed", "indexed"]),
            )
        )
        existing_doc = dup_res.scalars().first()
        if existing_doc:
            raise ConflictException(
                f"Duplicate document: '{existing_doc.original_filename}' with identical content is already uploaded."
            )

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

        # Extract text via Universal DocumentLoader (offloaded to thread pool)
        try:
            doc = await DocumentService._extract_and_index_document(db, doc)
        except Exception as e:
            logger.warning(f"RAG processing failed for document id={doc.id}: {e}")
            doc.processing_status = "failed"
            doc.error_message = str(e)
            await db.commit()
            await db.refresh(doc)
            raise

        return DocumentResponse.model_validate(doc)

    @staticmethod
    async def reprocess_document(db: AsyncSession, user_id: int, doc_id: int) -> DocumentResponse:
        """Purge stale vectors and re-run extraction, chunking, and embedding indexing."""
        doc = await DocumentService.get_user_document(db, user_id, doc_id)
        if not Path(doc.file_path).exists():
            raise BadRequestException("Source file no longer exists on disk and cannot be reprocessed.")

        VectorStoreManager.delete_document_vectors(user_id=user_id, document_id=doc_id)
        from app.ai.rag.retriever import RAGRetriever
        RAGRetriever.invalidate_cache()
        try:
            doc = await DocumentService._extract_and_index_document(db, doc)
        except Exception as e:
            doc.processing_status = "failed"
            doc.error_message = str(e)
            await db.commit()
            await db.refresh(doc)
            raise
        return DocumentResponse.model_validate(doc)

    @staticmethod
    async def list_user_documents(
        db: AsyncSession,
        user_id: int,
        search: Optional[str] = None,
        status_filter: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[DocumentResponse]:
        query = select(UploadedDocument).where(UploadedDocument.user_id == user_id)
        if search:
            query = query.where(UploadedDocument.original_filename.ilike(f"%{search.strip()}%"))
        if status_filter:
            query = query.where(UploadedDocument.processing_status == status_filter.strip())
        query = query.order_by(UploadedDocument.id.desc()).offset(max(0, skip)).limit(min(max(1, limit), 200))
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
        from app.ai.rag.retriever import RAGRetriever
        RAGRetriever.invalidate_cache()

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
