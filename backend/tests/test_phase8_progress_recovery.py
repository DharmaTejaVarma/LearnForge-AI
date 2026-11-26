"""Phase 8: Course Progress API, Stale-Job Recovery, Error Classification & Isolation Tests."""
import datetime
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.database import AsyncSessionLocal
from app.db.models.course import Lesson, LessonGenerationJob
from app.main import app
from app.services.job_queue import LessonJobService, _format_actionable_error


def test_error_classification_messages():
    c1, m1 = _format_actionable_error(ConnectionError("Cannot connect to http://localhost:11434"))
    assert c1 == "OLLAMA_UNAVAILABLE"
    assert "Ollama is running" in m1

    c2, m2 = _format_actionable_error(RuntimeError("model 'qwen2.5:3b' not found"))
    assert c2 == "MODEL_MISSING"
    assert "ollama pull" in m2

    c3, m3 = _format_actionable_error(RuntimeError("ChromaDB collection error"))
    assert c3 == "CHROMA_FAILED"
    assert "ChromaDB" in m3

    c4, m4 = _format_actionable_error(TimeoutError("ReadTimeout after 180s"))
    assert c4 == "LLM_TIMEOUT"
    assert "Retry" in m4


@pytest.mark.asyncio
async def test_phase8_progress_api_stale_recovery_and_isolation():
    suffix = uuid.uuid4().hex[:8]
    email_a = f"p8_a_{suffix}@learnforge.ai"
    email_b = f"p8_b_{suffix}@learnforge.ai"
    password = "StrongPassword123!"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        r_a = await client.post("/api/v1/auth/register", json={"email": email_a, "password": password, "full_name": "P8 A"})
        assert r_a.status_code == 201
        h_a = {"Authorization": f"Bearer {r_a.json()['access_token']}"}

        r_b = await client.post("/api/v1/auth/register", json={"email": email_b, "password": password, "full_name": "P8 B"})
        assert r_b.status_code == 201
        h_b = {"Authorization": f"Bearer {r_b.json()['access_token']}"}

        md = (
            "# Chapter 1: APIs\n"
            "Service APIs communicate over HTTP with JSON payloads.\n\n"
            "## Services And APIs\n"
            "RESTful endpoints use GET, POST, PATCH, and DELETE.\n"
        ).encode("utf-8")

        up = await client.post("/api/v1/documents/upload", headers=h_a, files={"file": (f"p8_{suffix}.md", md, "text/markdown")})
        assert up.status_code == 201
        doc_id = up.json()["id"]

        gen = await client.post("/api/v1/courses/generate", headers=h_a, json={"document_id": doc_id, "title": f"P8 Course {suffix}"})
        assert gen.status_code == 201
        course = gen.json()
        course_id = course["id"]
        lesson_id = course["chapters"][0]["topics"][0]["lesson"]["id"]

        # 1. Course generation-progress & lessons endpoints
        prog = await client.get(f"/api/v1/courses/{course_id}/generation-progress", headers=h_a)
        assert prog.status_code == 200
        pdata = prog.json()
        assert pdata["total_lessons"] >= 1
        assert pdata["curriculum_percentage"] == 100.0
        assert "content_readiness_percentage" in pdata

        l_list = await client.get(f"/api/v1/courses/{course_id}/lessons", headers=h_a)
        assert l_list.status_code == 200
        assert len(l_list.json()) == pdata["total_lessons"]

        # 2. Pause / Resume prefetch
        p_res = await client.post(f"/api/v1/courses/{course_id}/prefetch/pause", headers=h_a)
        assert p_res.status_code == 200 and p_res.json()["prefetch_paused"] is True
        r_res = await client.post(f"/api/v1/courses/{course_id}/prefetch/resume", headers=h_a)
        assert r_res.status_code == 200 and r_res.json()["prefetch_paused"] is False

        # 3. Simulate stale job in RETRIEVING_SOURCE with expired heartbeat (60s ago) and no live worker
        old_iso = (datetime.datetime.utcnow() - datetime.timedelta(seconds=60)).isoformat()
        async with AsyncSessionLocal() as session:
            user_id = (await session.get(Lesson, lesson_id)).topic_id  # only need course.user_id via query or job
            # Fetch actual user_id from progress/me or LessonGenerationJob
            me = await client.get("/api/v1/users/me", headers=h_a)
            uid = me.json()["id"]
            stale_job = LessonGenerationJob(
                course_id=course_id,
                lesson_id=lesson_id,
                user_id=uid,
                job_type="on_demand",
                status="RETRIEVING_SOURCE",
                current_stage="Retrieving relevant source passages",
                started_at=old_iso,
                retry_count=0,
                metrics={"heartbeat_at": old_iso, "stage_started_at": old_iso},
            )
            session.add(stale_job)
            await session.commit()

        LessonJobService._active_lesson_ids.discard(lesson_id)
        st = await client.get(f"/api/v1/lessons/{lesson_id}/status", headers=h_a)
        assert st.status_code == 200
        st_data = st.json()
        assert st_data["status"] == "FAILED"
        assert st_data["error_code"] == "STALE_JOB_TIMEOUT"
        assert st_data["total_stages"] == 10

        # 4. Cross-user isolation on progress, lessons, and status
        for path in [
            f"/api/v1/courses/{course_id}/generation-progress",
            f"/api/v1/courses/{course_id}/lessons",
            f"/api/v1/lessons/{lesson_id}/status",
        ]:
            resp = await client.get(path, headers=h_b)
            assert resp.status_code in (403, 404)

        # Cleanup
        await client.delete(f"/api/v1/courses/{course_id}", headers=h_a)
        await client.delete(f"/api/v1/documents/{doc_id}", headers=h_a)
