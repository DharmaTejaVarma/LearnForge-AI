"""Phase 5: End-to-End Student Journey, Cross-User Isolation & Sandbox Security Audit Tests."""
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.code_sandbox import (
    _USER_RUN_TIMESTAMPS,
    check_sandbox_rate_limit,
    execute_python_sandbox,
    validate_python_code,
)


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    "hostile_code,label",
    [
        ("open('secret.txt', 'w').write('x')", "filesystem open()"),
        ("import os\nprint(os.environ)", "os + env access"),
        ("import pathlib\nprint(pathlib.Path('.').resolve())", "pathlib access"),
        ("import socket\ns = socket.socket()", "network socket"),
        ("import urllib.request\nurllib.request.urlopen('http://127.0.0.1')", "urllib network"),
        ("import subprocess\nsubprocess.run(['whoami'])", "subprocess spawn"),
        ("import multiprocessing\nmultiprocessing.Process()", "multiprocessing spawn"),
        ("x = ().__class__.__mro__[1].__subclasses__()", "dunder MRO subclasses escape"),
        ("def f(): pass\nprint(f.__globals__)", "dunder __globals__ escape"),
        ("def f(): pass\nprint(f.__code__)", "dunder __code__ escape"),
        ("eval('1+1')", "eval builtin"),
        ("exec('import os')", "exec builtin"),
        ("__import__('os').system('echo hi')", "__import__ builtin"),
    ],
)
def test_sandbox_blocks_hostile_code(hostile_code: str, label: str):
    ok, err = validate_python_code(hostile_code)
    assert not ok, f"AST validator failed to block {label}"
    res = execute_python_sandbox(hostile_code)
    assert res["passed"] is False, f"Sandbox executed {label}"
    assert res["stderr"]


def test_sandbox_blocks_hostile_test_assert_code():
    res = execute_python_sandbox(
        "x = 42\nprint(x)",
        test_cases=[{"description": "hostile assert", "assert_code": "__import__('os').listdir('.')"}],
    )
    assert res["passed"] is False
    assert "Restricted" in res["stderr"]


def test_sandbox_handles_infinite_loop_and_recursion_and_cleans_tempdir():
    before_dirs = set(Path(tempfile.gettempdir()).glob("lf_sandbox_*"))

    loop_res = execute_python_sandbox("while True:\n    pass", timeout_seconds=1)
    assert loop_res["passed"] is False
    assert loop_res["timed_out"] is True

    rec_res = execute_python_sandbox("def f():\n    return f()\nf()")
    assert rec_res["passed"] is False
    assert "RecursionError" in rec_res["stderr"]

    after_dirs = set(Path(tempfile.gettempdir()).glob("lf_sandbox_*"))
    assert after_dirs == before_dirs, "Sandbox leaked temporary directories"


def test_sandbox_rate_limit_enforced():
    uid = 987654321
    _USER_RUN_TIMESTAMPS.pop(uid, None)
    try:
        for _ in range(3):
            check_sandbox_rate_limit(uid, max_per_minute=3)
        with pytest.raises(HTTPException) as exc_info:
            check_sandbox_rate_limit(uid, max_per_minute=3)
        assert exc_info.value.status_code == 429
    finally:
        _USER_RUN_TIMESTAMPS.pop(uid, None)


@pytest.mark.asyncio
async def test_e2e_student_journey_and_cross_user_isolation():
    suffix = uuid.uuid4().hex[:8]
    email_a = f"student_a_{suffix}@learnforge.ai"
    email_b = f"student_b_{suffix}@learnforge.ai"
    password = "StrongPassword123!"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register Student A & login
        reg_a = await client.post("/api/v1/auth/register", json={
            "email": email_a,
            "password": password,
            "full_name": "Student Alpha",
        })
        assert reg_a.status_code == 201, reg_a.text

        login_a = await client.post("/api/v1/auth/login", json={
            "email": email_a,
            "password": password,
        })
        assert login_a.status_code == 200
        token_a = login_a.json()["access_token"]
        headers_a = _auth_headers(token_a)

        # 2. Register Student B
        reg_b = await client.post("/api/v1/auth/register", json={
            "email": email_b,
            "password": password,
            "full_name": "Student Beta",
        })
        assert reg_b.status_code == 201
        token_b = reg_b.json()["access_token"]
        headers_b = _auth_headers(token_b)

        # 3. Upload educational document as Student A
        sample_md = (
            "# Chapter 1: FastAPI Services and APIs\n"
            "Service APIs communicate across network boundaries using HTTP requests and JSON payloads.\n"
            "FastAPI uses Python type hints and Pydantic models to validate input and output schemas.\n\n"
            "## Services And APIs\n"
            "A RESTful endpoint pairs a resource URL such as /creatures with HTTP methods GET, POST, PATCH, and DELETE.\n"
            "Stateless endpoints carry all request context per call.\n"
        ).encode("utf-8")

        up_res = await client.post(
            "/api/v1/documents/upload",
            headers=headers_a,
            files={"file": (f"fastapi_guide_{suffix}.md", sample_md, "text/markdown")},
        )
        assert up_res.status_code == 201, up_res.text
        doc_id = up_res.json()["id"]

        # 4. Generate course from document
        gen_res = await client.post(
            "/api/v1/courses/generate",
            headers=headers_a,
            json={
                "document_id": doc_id,
                "title": f"FastAPI E2E Course {suffix}",
                "difficulty_level": "intermediate",
            },
        )
        assert gen_res.status_code == 201, gen_res.text
        course = gen_res.json()
        course_id = course["id"]
        assert len(course["chapters"]) >= 1
        first_chapter = course["chapters"][0]
        chapter_id = first_chapter["id"]
        first_topic = first_chapter["topics"][0]
        lesson_id = first_topic["lesson"]["id"]

        # 5. Open lesson (triggers synthesis or returns ready lesson)
        lesson_res = await client.get(f"/api/v1/lessons/{lesson_id}", headers=headers_a)
        assert lesson_res.status_code == 200, lesson_res.text
        lesson = lesson_res.json()
        assert lesson["title"]
        if lesson.get("structured_sections"):
            assert "matching_exercise" in lesson["structured_sections"]

        # 6. Run project milestone sandbox endpoint
        sb_res = await client.post(
            "/api/v1/courses/sandbox/run",
            headers=headers_a,
            json={
                "code": "ENDPOINTS = {'create': ('POST', '/creatures', 201)}\nprint(ENDPOINTS['create'][2])",
                "test_cases": [{"description": "returns 201", "assert_code": "assert ENDPOINTS['create'][2] == 201"}],
            },
        )
        assert sb_res.status_code == 200, sb_res.text
        assert sb_res.json()["passed"] is True

        # 7. Complete lesson & verify persistence
        comp_res = await client.post(f"/api/v1/lessons/{lesson_id}/toggle-complete", headers=headers_a)
        assert comp_res.status_code == 200
        assert comp_res.json()["is_completed"] is True

        # 8. Submit exercises if present
        for ex in lesson.get("exercises") or []:
            ex_id = ex["id"]
            ex_type = ex["exercise_type"]
            if ex_type in ("coding", "debug") and ex.get("starter_code"):
                r = await client.post(
                    f"/api/v1/lessons/{lesson_id}/exercises/{ex_id}/run",
                    headers=headers_a,
                    json={"code": ex["starter_code"]},
                )
                assert r.status_code == 200
            sub = await client.post(
                f"/api/v1/lessons/{lesson_id}/exercises/{ex_id}/submit",
                headers=headers_a,
                json={"answer": ex.get("correct_answer") or "ok", "code": ex.get("starter_code") or ""},
            )
            assert sub.status_code == 200

        # 9. Module & Final Assessment (server strips correct_answer from GET response for integrity)
        mod_assess = await client.get(f"/api/v1/courses/{course_id}/modules/{chapter_id}/assessment", headers=headers_a)
        assert mod_assess.status_code == 200
        mod_data = mod_assess.json()
        assert len(mod_data["questions"]) >= 1
        assert "correct_answer" not in mod_data["questions"][0]
        mod_answers = {q["id"]: q["options"][0] for q in mod_data["questions"]}
        mod_sub = await client.post(
            f"/api/v1/courses/{course_id}/assessments/{mod_data['id']}/submit",
            headers=headers_a,
            json={"answers": mod_answers},
        )
        assert mod_sub.status_code == 200
        assert "score" in mod_sub.json()
        assert "topic_breakdown" in mod_sub.json()

        fin_assess = await client.get(f"/api/v1/courses/{course_id}/final-assessment", headers=headers_a)
        assert fin_assess.status_code == 200
        fin_data = fin_assess.json()
        assert len(fin_data["questions"]) >= 1
        fin_answers = {q["id"]: q["options"][0] for q in fin_data["questions"]}
        fin_sub = await client.post(
            f"/api/v1/courses/{course_id}/assessments/{fin_data['id']}/submit",
            headers=headers_a,
            json={"answers": fin_answers},
        )
        assert fin_sub.status_code == 200
        assert "score" in fin_sub.json()

        # 10. Verify progress stats & reopened course persistence
        stats_res = await client.get("/api/v1/progress/stats", headers=headers_a)
        assert stats_res.status_code == 200
        reopen = await client.get(f"/api/v1/courses/{course_id}", headers=headers_a)
        assert reopen.status_code == 200
        assert reopen.json()["chapters"][0]["topics"][0]["lesson"]["is_completed"] is True

        # 11. Cross-user isolation: Student B MUST NOT access Student A's resources
        for method, path in [
            ("get", f"/api/v1/documents/{doc_id}"),
            ("get", f"/api/v1/courses/{course_id}"),
            ("get", f"/api/v1/lessons/{lesson_id}"),
            ("post", f"/api/v1/lessons/{lesson_id}/toggle-complete"),
            ("get", f"/api/v1/courses/{course_id}/modules/{chapter_id}/assessment"),
            ("delete", f"/api/v1/courses/{course_id}"),
            ("delete", f"/api/v1/documents/{doc_id}"),
        ]:
            resp = await getattr(client, method)(path, headers=headers_b)
            assert resp.status_code in (403, 404), f"Isolation breach on {method.upper()} {path}: {resp.status_code}"

        # Cleanup Student A's test course & document
        await client.delete(f"/api/v1/courses/{course_id}", headers=headers_a)
        await client.delete(f"/api/v1/documents/{doc_id}", headers=headers_a)
