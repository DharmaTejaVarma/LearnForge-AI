import sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import (
    LearnForgeException,
    learnforge_exception_handler,
    validation_exception_handler,
    global_exception_handler,
)
from app.db.database import engine, check_db_health
from app.api.v1 import (
    health,
    auth,
    users,
    documents,
    courses,
    lessons,
    tutor,
    flashcards,
    questions,
    quizzes,
    progress,
)

# Frontend build directory (sibling of backend/)
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Verify database connection & configuration
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")
    if settings.ENVIRONMENT.lower() == "production":
        if "dev_secret_key" in settings.SECRET_KEY:
            raise RuntimeError("SECRET_KEY must be overridden with a strong secret in production!")
        if settings.DEBUG:
            logger.warning("SECURITY WARNING: DEBUG=True is enabled in production environment.")
    db_status = await check_db_health()
    logger.info(f"Database initial check: {db_status}")
    try:
        from app.db.base import Base
        import app.db.models  # noqa: F401
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as table_err:
        logger.warning(f"Table metadata sync warning: {table_err}")
    try:
        if "pytest" not in sys.modules:
            from app.ai.models.model_router import model_router
            await model_router.probe_cloud_once()
    except Exception as e:
        logger.warning(f"Cloud provider probe skipped at startup: {e}")

    # Reset any interrupted lessons/jobs and pre-warm local embedding model in background
    if "pytest" not in sys.modules:
        import asyncio as _asyncio
        from app.services.job_queue import LessonJobService
        await LessonJobService.recover_interrupted_jobs()
        _asyncio.create_task(_resume_queued_lessons())
        _asyncio.create_task(_prewarm_embeddings())

    yield
    # Shutdown: Cancel active job workers & cleanly dispose async database engine connections
    if "pytest" not in sys.modules:
        from app.services.job_queue import LessonJobService
        await LessonJobService.shutdown_workers()
    logger.info("Shutting down database engine connections...")
    await engine.dispose()
    logger.info("Application shutdown complete.")


async def _prewarm_embeddings() -> None:
    """Load local SentenceTransformer in background so first document upload doesn't stall."""
    import asyncio
    await asyncio.sleep(2)
    try:
        from app.ai.embeddings.embedding_service import EmbeddingService
        await asyncio.to_thread(EmbeddingService.get_model)
    except Exception as exc:
        logger.debug(f"Embedding prewarm skipped: {exc}")


async def _resume_queued_lessons() -> None:
    """On startup, reset any interrupted 'generating' lessons back to 'queued' for on-demand synthesis."""
    import asyncio
    await asyncio.sleep(3)
    try:
        from sqlalchemy import update
        from app.db.database import AsyncSessionLocal
        from app.db.models.course import Lesson, GenerationJob

        async with AsyncSessionLocal() as session:
            # Reset lessons left in 'generating' when the previous server stopped
            res = await session.execute(
                update(Lesson)
                .where(Lesson.generation_status == "generating", Lesson.content == "")
                .values(generation_status="queued")
            )
            # Mark any stale running GenerationJobs as completed (remaining lessons use on-demand + prefetch)
            await session.execute(
                update(GenerationJob)
                .where(GenerationJob.status == "running")
                .values(status="completed", current_stage="Ready for on-demand learning")
            )
            await session.commit()
            if res.rowcount:
                logger.info(f"Startup: Reset {res.rowcount} interrupted lessons to 'queued' (on-demand ready).")
    except Exception as exc:
        logger.warning(f"Startup lesson cleanup failed: {exc}")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Intelligent Local-First AI Learning Platform API",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENVIRONMENT.lower() != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT.lower() != "production" else None,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Rate Limiting Middleware
from app.core.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware, max_requests_per_minute=settings.RATE_LIMIT_PER_MINUTE)

# Centralized Exception Handlers
app.add_exception_handler(LearnForgeException, learnforge_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# Health endpoints (Root and versioned)
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(health.router, prefix="/api/v1/health", tags=["Health"])

# API v1 Routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(courses.router, prefix="/api/v1/courses", tags=["Courses"])
app.include_router(lessons.router, prefix="/api/v1/lessons", tags=["Lessons"])
app.include_router(tutor.router, prefix="/api/v1/tutor", tags=["Tutor"])
app.include_router(flashcards.router, prefix="/api/v1/flashcards", tags=["Flashcards"])
app.include_router(questions.router, prefix="/api/v1/questions", tags=["Questions"])
app.include_router(quizzes.router, prefix="/api/v1/quizzes", tags=["Quizzes"])
app.include_router(progress.router, prefix="/api/v1/progress", tags=["Progress"])

# ---------------------------------------------------------------------------
# Serve built React frontend from FastAPI (production / preview mode)
# If the frontend/dist directory exists, mount the static assets and return
# index.html for any unmatched route so React Router handles navigation.
# ---------------------------------------------------------------------------
if FRONTEND_DIST.exists() and "pytest" not in sys.modules:
    # Mount /assets, /vite.svg, etc.
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_DIST / "assets")),
        name="frontend-assets",
    )

    @app.get("/vite.svg", include_in_schema=False)
    async def vite_svg():
        return FileResponse(str(FRONTEND_DIST / "vite.svg"))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str, request: Request):
        """
        Catch-all: return index.html for any path that is not an API route.
        React Router handles client-side routing from there.
        """
        # Never intercept API, health or docs routes
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("redoc") or full_path.startswith("health"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404)
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            return FileResponse(str(index))
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Frontend build not found. Run: cd frontend && npm run build")
