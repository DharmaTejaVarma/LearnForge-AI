"""Comprehensive tests for LearnForge AI v2 course generation, exercises, sandbox, cache & assessments."""
from __future__ import annotations

import time
import uuid
import fitz
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from unittest.mock import AsyncMock, patch

from app.main import app
from app.db.database import AsyncSessionLocal
from app.ai.agents.content_agent import ContentAgent
from app.ai.rag.document_loader import DocumentLoader
from app.core.course_validator import CourseValidator
from app.core.sanitizer import EducationalSanitizer
from app.db.models.course import Lesson
from app.services.code_sandbox import execute_python_sandbox, validate_python_code


def _make_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_sanitizer_strips_hex_prefix_scraper_and_isbn():
    raw = "07b811c8e2e04685b3482351d590631d_dokumenpub_fastapi-modern-python-web-1nbsped-9781098135508.pdf"
    cleaned = EducationalSanitizer.clean_title(raw)
    assert "dokumen" not in cleaned.lower()
    assert "07b811" not in cleaned.lower()
    assert "9781098" not in cleaned
    assert "FastAPI" in cleaned


def test_frontmatter_filtering_and_textbook_hierarchy():
    assert DocumentLoader._is_frontback_matter("Cover") is True
    assert DocumentLoader._is_frontback_matter("Copyright") is True
    assert DocumentLoader._is_frontback_matter("Table of Contents") is True
    assert DocumentLoader._is_frontback_matter("Conventions Used in This Book") is True
    assert DocumentLoader._is_frontback_matter("Appendix A. Installing Tools") is True
    assert DocumentLoader._is_frontback_matter("Index") is True
    # Preserve legitimate instructional titles
    assert DocumentLoader._is_frontback_matter("Introduction to FastAPI") is False
    assert DocumentLoader._is_frontback_matter("Database Indexes") is False

    sections = [
        {"title": "Part I. What's New?", "level": 1, "page_start": 19, "page_end": 48, "printed_page_start": "1", "printed_page_end": "30"},
        {"title": "Chapter 1. The Modern Web", "level": 2, "page_start": 21, "page_end": 32, "printed_page_start": "3", "printed_page_end": "14"},
        {"title": "Preview", "level": 3, "page_start": 21, "page_end": 21},
        {"title": "Services and APIs", "level": 3, "page_start": 22, "page_end": 25, "printed_page_start": "4", "printed_page_end": "7"},
        {"title": "Concurrency", "level": 3, "page_start": 26, "page_end": 28, "printed_page_start": "8", "printed_page_end": "10"},
        {"title": "Chapter 2. Modern Python", "level": 2, "page_start": 33, "page_end": 44, "printed_page_start": "15", "printed_page_end": "26"},
        {"title": "Preview", "level": 3, "page_start": 33, "page_end": 33},
        {"title": "Type Hints", "level": 3, "page_start": 36, "page_end": 40, "printed_page_start": "18", "printed_page_end": "22"},
    ]
    chapters = ContentAgent._sections_to_chapters(sections, max_chapters=10)
    assert len(chapters) == 2
    assert chapters[0]["title"] == "Chapter 1. The Modern Web"
    assert [t["title"] for t in chapters[0]["topics"]] == ["Services And APIs", "Concurrency"]
    assert chapters[1]["title"] == "Chapter 2. Modern Python"
    assert [t["title"] for t in chapters[1]["topics"]] == ["Type Hints"]

    ok, msg = CourseValidator.validate_course_outline({
        "title": "Modern Web Development with FastAPI",
        "chapters": chapters,
    })
    assert ok is True, msg


def test_python_sandbox_security_and_execution():
    # Forbidden imports / builtins rejected by AST check
    ok_os, err_os = validate_python_code("import os\nprint(os.listdir('.'))")
    assert ok_os is False
    assert "os" in (err_os or "").lower()

    ok_open, err_open = validate_python_code("f = open('secret.txt')")
    assert ok_open is False
    assert "open" in (err_open or "").lower()

    # Valid Python code runs in isolated subprocess and evaluates assertions
    code = (
        "def build_response(status_code, data=None):\n"
        "    is_ok = 200 <= status_code < 300\n"
        "    return {'status': status_code, 'ok': is_ok, 'data': data if is_ok else None}\n"
    )
    res = execute_python_sandbox(
        code,
        test_cases=[
            {"description": "2xx", "assert_code": "assert build_response(200, {'x': 1})['ok'] is True"},
            {"description": "404", "assert_code": "assert build_response(404, {'x': 1})['data'] is None"},
        ],
    )
    assert res["passed"] is True
    assert res["passed_tests"] == 2
    assert res["total_tests"] == 2

    # Failing assertion returns honest failure without raising
    bad_res = execute_python_sandbox(
        "def build_response(status_code, data=None):\n    return {'ok': False}\n",
        test_cases=[{"description": "2xx", "assert_code": "assert build_response(200)['ok'] is True"}],
    )
    assert bad_res["passed"] is False
    assert bad_res["passed_tests"] == 0


@pytest.mark.asyncio
async def test_interactive_exercises_notes_assessments_and_cache():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        email = f"v2student_{uuid.uuid4().hex[:8]}@learnforge.ai"
        reg_res = await client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "StrongPassword123!",
            "full_name": "V2 Learner",
        })
        assert reg_res.status_code == 201
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        pdf_bytes = _make_pdf_bytes(
            "Services and APIs\n"
            "FastAPI enables asynchronous RESTful HTTP services validated cleanly via Pydantic models.\n"
            "Use explicit schema types and avoid blocking synchronous I/O inside async route handlers.\n"
            "Python type hints define expected request and response payload contracts cleanly.\n"
        )
        up_res = await client.post(
            "/api/v1/documents/upload",
            headers=headers,
            files={"file": ("fastapi_notes.pdf", pdf_bytes, "application/pdf")},
        )
        assert up_res.status_code == 201
        doc_id = up_res.json()["id"]

        sample_lesson_md = (
            "# Services and APIs\n\n"
            "## Learning Objectives\n"
            "- Design clean asynchronous HTTP endpoints with FastAPI\n"
            "- Separate validation schemas from service business logic\n\n"
            "## Introduction\n"
            "Modern web services communicate over HTTP using well-defined JSON contracts so frontend and backend "
            "clients evolve independently without breaking integration boundaries or leaking runtime internals.\n\n"
            "## Core Concepts\n"
            "FastAPI inspects **Type Hints** and **Pydantic** models to parse incoming HTTP payloads, generate "
            "OpenAPI documentation, and return structured `200 OK` or `422 Unprocessable Entity` responses safely.\n\n"
            "## Worked Example\n"
            "```python\n"
            "def build_response(status_code, data=None):\n"
            "    is_ok = 200 <= status_code < 300\n"
            "    return {'status': status_code, 'ok': is_ok, 'data': data if is_ok else None}\n"
            "```\n\n"
            "## Common Mistakes\n"
            "- Skipping explicit response schemas exposes internal fields.\n"
            "- Blocking calls inside async endpoints freeze concurrency.\n\n"
            "## Key Takeaways\n"
            "- **Explicit Validation** prevents malformed request payloads from reaching business logic.\n"
            "- Separating API handlers from service modules improves maintainability.\n\n"
            "## Check Your Understanding\n"
            "1. Why validate payloads at API boundaries? To fail fast with clear client errors.\n"
        )

        mock_gen = AsyncMock(return_value={
            "content": sample_lesson_md,
            "provider_used": "mock:test",
            "latency_ms": 12.0,
        })
        mock_tutor = AsyncMock(return_value={
            "answer": "Focus on checking `200 <= status_code < 300` first without returning error payloads.",
            "citations": [],
            "provider_used": "mock:tutor",
            "latency_ms": 8.0,
            "intent": "educational_question",
        })

        with patch("app.ai.agents.lesson_agent.model_router.generate", mock_gen):
            gen_res = await client.post(
                "/api/v1/courses/generate",
                headers=headers,
                json={"document_id": doc_id, "difficulty_level": "intermediate", "target_chapters_count": 4},
            )
        assert gen_res.status_code == 201
        course_data = gen_res.json()
        course_id = course_data["id"]
        chapter_id = course_data["chapters"][0]["id"]
        lesson_id = course_data["chapters"][0]["topics"][0]["lesson"]["id"]

        # Fetch lesson & verify structured fields + auto-generated interactive exercises
        lesson_res = await client.get(f"/api/v1/lessons/{lesson_id}", headers=headers)
        assert lesson_res.status_code == 200
        lesson_json = lesson_res.json()
        assert lesson_json["estimated_minutes"] >= 4
        assert len(lesson_json["exercises"]) >= 4

        ex_mcq = next(e for e in lesson_json["exercises"] if e["exercise_type"] == "mcq")
        sub_mcq = await client.post(
            f"/api/v1/lessons/{lesson_id}/exercises/{ex_mcq['id']}/submit",
            headers=headers,
            json={"answer": ex_mcq["options"][0]},
        )
        assert sub_mcq.status_code == 200
        assert sub_mcq.json()["is_correct"] is True

        # Verify structured interactive sections populated automatically
        structured = lesson_json.get("structured_sections") or {}
        assert isinstance(structured.get("concept_cards"), list) and len(structured["concept_cards"]) >= 1
        assert structured.get("architecture_diagram") is not None
        assert structured.get("simulator") is not None
        assert structured.get("project_step") is not None

        # Run topic-specific coding sandbox & submit coding exercise
        ex_code = next((e for e in lesson_json["exercises"] if e["exercise_type"] == "coding"), None)
        assert ex_code is not None
        run_res = await client.post(
            f"/api/v1/lessons/{lesson_id}/exercises/{ex_code['id']}/run",
            headers=headers,
            json={
                "code": (
                    "def dispatch_message(pattern, subscribers, message):\n"
                    "    if pattern == 'pub_sub':\n"
                    "        return [{'worker': s, 'msg': message} for s in subscribers]\n"
                    "    if pattern == 'queue' and subscribers:\n"
                    "        return [{'worker': subscribers[0], 'msg': message}]\n"
                    "    return []\n"
                )
            },
        )
        assert run_res.status_code == 200
        assert run_res.json()["passed"] is True

        # Save & retrieve lesson notes + bookmark
        put_note = await client.put(
            f"/api/v1/lessons/{lesson_id}/notes",
            headers=headers,
            json={"content": "Remember 2xx check!", "is_bookmarked": True},
        )
        assert put_note.status_code == 200
        assert put_note.json()["is_bookmarked"] is True
        assert put_note.json()["content"] == "Remember 2xx check!"

        # Module & Final Assessments
        mod_assess_res = await client.get(
            f"/api/v1/courses/{course_id}/modules/{chapter_id}/assessment",
            headers=headers,
        )
        assert mod_assess_res.status_code == 200
        mod_assess = mod_assess_res.json()
        assert len(mod_assess["questions"]) >= 1

        answers = {q["id"]: q["options"][0] for q in mod_assess["questions"] if q["options"]}
        submit_assess = await client.post(
            f"/api/v1/courses/{course_id}/assessments/{mod_assess['id']}/submit",
            headers=headers,
            json={"answers": answers},
        )
        assert submit_assess.status_code == 200
        assert submit_assess.json()["score"] >= 0.0

        final_assess_res = await client.get(f"/api/v1/courses/{course_id}/final-assessment", headers=headers)
        assert final_assess_res.status_code == 200
        assert final_assess_res.json()["assessment_type"] == "final"

        # Contextual AI Tutor inside lesson
        with patch("app.ai.agents.tutor_agent.TutorAgent.respond_to_query", mock_tutor):
            tutor_res = await client.post(
                "/api/v1/tutor/chat",
                headers=headers,
                json={
                    "question": "Give me a hint",
                    "course_id": course_id,
                    "lesson_id": lesson_id,
                    "exercise_id": ex_mcq["id"],
                    "tutor_mode": "hint_only",
                },
            )
        assert tutor_res.status_code == 200
        assert "status_code" in tutor_res.json()["answer"]

        # Cache hit benchmark check: populate remaining lesson first, then regenerate from same doc
        second_lesson_id = course_data["chapters"][0]["topics"][1]["lesson"]["id"]
        with patch("app.ai.agents.lesson_agent.model_router.generate", mock_gen):
            res2 = await client.get(f"/api/v1/lessons/{second_lesson_id}", headers=headers)
            assert res2.status_code == 200

        async with AsyncSessionLocal() as db_sess:
            db_lessons = (
                await db_sess.execute(select(Lesson).where(Lesson.cache_key.is_not(None)))
            ).scalars().all()
            assert len(db_lessons) >= 2

        with patch("app.ai.agents.lesson_agent.LessonAgent.generate_lesson", new_callable=AsyncMock) as spy_lesson, \
             patch("app.ai.agents.content_agent.ContentAgent._generate_meta", new_callable=AsyncMock, return_value=("Cached Course Desc", ["Obj 1"])):
            t0 = time.perf_counter()
            cached_course_res = await client.post(
                "/api/v1/courses/generate",
                headers=headers,
                json={"document_id": doc_id, "difficulty_level": "intermediate", "target_chapters_count": 4},
            )
            cached_elapsed_ms = (time.perf_counter() - t0) * 1000
        assert cached_course_res.status_code == 201
        assert spy_lesson.call_count == 0
        assert cached_elapsed_ms < 5000


def test_real_fastapi_pdf_all_18_chapters_and_lesson_granularity():
    from pathlib import Path
    from app.ai.agents.document_agent import DocumentAgent
    from app.ai.agents.exercise_agent import ExerciseAgent
    from app.ai.agents.lesson_agent import LessonAgent

    pdf_path = Path("uploads/07b811c8e2e04685b3482351d590631d_dokumenpub_fastapi-modern-pyth.pdf")
    if not pdf_path.exists():
        pytest.skip("Validation FastAPI PDF not present on disk")

    assert DocumentLoader._is_frontback_matter("Chapter 17. Data Discovery and Visualization") is False
    sections = DocumentLoader.extract_structure(str(pdf_path))
    pages = DocumentLoader.extract_pdf(str(pdf_path))
    bp = DocumentAgent.analyze_document(pages, pdf_path.name)
    assert bp.get("author") == "Bill Lubanovic"

    chapters = ContentAgent._sections_to_chapters(sections, max_chapters=24)
    assert len(chapters) == 18
    titles = [c["title"] for c in chapters]
    assert any("16." in t and "Forms" in t for t in titles)
    assert any("17." in t and "Data Discovery" in t for t in titles)
    assert any("18." in t and "Games" in t for t in titles)

    # Printed book pages should align with physical pages for Chapter 1 (Book p. 3-14 = PDF 21-32)
    assert chapters[0]["printed_page_start"] == "3"
    assert chapters[0]["printed_page_end"] == "14"
    ch1_topics = [t["title"] for t in chapters[0]["topics"]]
    assert len(ch1_topics) >= 5
    assert any("HTTP" in t for t in ch1_topics)
    assert any("JSON" in t for t in ch1_topics)

    # Lesson validation repairs dangling code fences & validates Python code cleanly
    repaired, checks = LessonAgent._finalize_and_validate_content(
        content=(
            "# Services And APIs\n\n## Learning Objectives\n- Distinguish RPC and queues\n\n"
            "## Introduction\nAPIs connect frontends and backends cleanly.\n\n"
            "## Core Concepts\nServices handle business rules and HTTP routing.\n\n"
            "## Worked Example\n```python\ndef ping():\n    return {'ok': True}"
        ),
        topic_title="Services And APIs",
        chapter_title="Chapter 1. The Modern Web",
        pages_range="Book Page 4",
        source_text="Services and APIs connect clients",
        subtopics=["Kinds of APIs"],
    )
    assert repaired.count("```") % 2 == 0
    assert "## Key Takeaways" in repaired
    assert "## Check Your Understanding" in repaired
    assert checks["python_syntax_valid"] is True
    assert checks["passed"] is True

    # Topic-specific exercise verification (HTTP & RESTful vs Concurrency never share generic debug task)
    http_ex = ExerciseAgent._build_grounded_exercises(
        topic_title="HTTP & RESTful",
        chapter_title="Chapter 1. The Modern Web",
        lesson_content="# HTTP & RESTful\nGET retrieves data. PATCH updates partially.",
        source_text="REST uses HTTP verbs GET, POST, PUT, PATCH, DELETE.",
        domain="computer_science",
        content_type="programming",
        difficulty="intermediate",
        key_takeaways=["GET reads safely without modifying resources."],
        source_reference="Chapter 1, Book p. 5-7",
    )
    debug_http = next(e for e in http_ex if e["exercise_type"] == "debugging")
    assert "update_or_get_route" in (debug_http["buggy_code"] or "")
    assert "summarize_route_metrics" not in (debug_http["buggy_code"] or "")

