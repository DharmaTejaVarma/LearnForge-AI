from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, status
from app.core.config import settings
from app.db.database import check_db_health
from app.ai.models.model_router import model_router

router = APIRouter()

@router.get("", status_code=status.HTTP_200_OK)
@router.get("/", status_code=status.HTTP_200_OK)
async def health_check():
    """Comprehensive system health check endpoint."""
    db_health = await check_db_health()
    
    # Check uploads directory
    uploads_path = Path(settings.UPLOAD_DIR)
    uploads_ok = uploads_path.exists() and os_access(uploads_path)
    
    # Check chroma_data directory
    chroma_path = Path(settings.CHROMA_PERSIST_DIRECTORY)
    chroma_ok = chroma_path.exists() and os_access(chroma_path)
    
    # Live probe of local & cloud AI providers
    ai_status = await model_router.get_providers_health()

    all_healthy = (db_health.get("status") == "connected") and uploads_ok and chroma_ok

    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_health,
        "storage": {
            "uploads_directory": str(uploads_path.resolve()),
            "uploads_writable": uploads_ok,
            "chroma_directory": str(chroma_path.resolve()),
            "chroma_writable": chroma_ok,
        },
        "ai_providers": {
            **ai_status,
            "embedding_model": settings.EMBEDDING_MODEL,
        }
    }

def os_access(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".health_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        return True
    except Exception:
        return False
