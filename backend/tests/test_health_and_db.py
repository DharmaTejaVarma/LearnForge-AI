import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.database import check_db_health, engine
from sqlalchemy import text

@pytest.mark.asyncio
async def test_sqlite_pragmas():
    """Verify that foreign keys and WAL journal mode are active."""
    async with engine.connect() as conn:
        fk = (await conn.execute(text("PRAGMA foreign_keys;"))).scalar()
        wal = (await conn.execute(text("PRAGMA journal_mode;"))).scalar()
        assert fk == 1, f"Expected foreign_keys=1, got {fk}"
        assert str(wal).lower() == "wal", f"Expected journal_mode=WAL, got {wal}"

@pytest.mark.asyncio
async def test_health_endpoint():
    """Test the /health and /api/v1/health endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"]["status"] == "connected"
        assert data["database"]["foreign_keys_enabled"] is True
        assert data["database"]["journal_mode"] == "WAL"
        assert data["storage"]["uploads_writable"] is True
        assert data["storage"]["chroma_writable"] is True

@pytest.mark.asyncio
async def test_exception_handler():
    """Test that centralized exception handler catches and formats custom exceptions."""
    from app.core.exceptions import NotFoundException
    transport = ASGITransport(app=app)
    
    # Temporarily mount a test route that raises NotFoundException
    from fastapi import APIRouter
    test_router = APIRouter()
    @test_router.get("/test-error")
    async def trigger_error():
        raise NotFoundException("Sample test error message", details={"item_id": 999})
    app.include_router(test_router)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/test-error")
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "NotFoundException"
        assert data["error"]["message"] == "Sample test error message"
        assert data["error"]["details"]["item_id"] == 999
