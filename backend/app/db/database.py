import os
import sys
from pathlib import Path
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings
from app.core.logging import logger

# Ensure database directory exists if path is specified
if "sqlite" in settings.DATABASE_URL:
    db_path_str = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
    db_path = Path(db_path_str)
    if db_path.parent and not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)

# Create Async Engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False, "timeout": 30.0} if "sqlite" in settings.DATABASE_URL else {},
)

# Enforce SQLite Pragmas (Foreign Keys and WAL mode)
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in settings.DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA busy_timeout=30000;")
        cursor.close()

# Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def get_db():
    """FastAPI dependency yielding an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            if e.__class__.__name__ != "ClientDisconnected":
                logger.error(f"Database session rollback due to error: {e}")
            raise
        finally:
            await session.close()

async def check_db_health() -> dict:
    """Check database connection, foreign keys, and WAL journal mode."""
    try:
        async with engine.connect() as conn:
            fk_res = await conn.execute(text("PRAGMA foreign_keys;"))
            fk_val = fk_res.scalar()
            wal_res = await conn.execute(text("PRAGMA journal_mode;"))
            wal_val = wal_res.scalar()
            return {
                "status": "connected",
                "foreign_keys_enabled": bool(fk_val),
                "journal_mode": str(wal_val).upper(),
                "database": "SQLite (aiosqlite)"
            }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "database": "SQLite (aiosqlite)"
        }
