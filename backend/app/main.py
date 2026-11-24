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
    db_status = await check_db_health()
    logger.info(f"Database initial check: {db_status}")
    yield
    # Shutdown: Cleanly dispose async database engine connections
    logger.info("Shutting down database engine connections...")
    await engine.dispose()
    logger.info("Application shutdown complete.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Intelligent Local-First AI Learning Platform API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
