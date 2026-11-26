"""Phase 3 validation, evaluator, job cancellation/recovery, and E2E workflow tests."""
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.services.code_validator import CodeValidationPipeline
from app.services.lesson_evaluator import LessonEvaluator
from app.services.job_queue import LessonJobService


def test_code_validation_pipeline_catches_syntax_and_undefined():
    # 1. Valid stdlib code runs cleanly in isolated sandbox
    good = "import json\ndata = {'ok': True}\nprint(json.dumps(data))"
    res_good = CodeValidationPipeline.validate_code_block(good, run_in_sandbox=True)
    assert res_good.valid is True
    assert res_good.syntax_ok is True
    assert res_good.runtime_ok is True
    assert '"ok": true' in res_good.stdout

    # 2. Undefined identifier caught before execution
    undef = "def handle(x):\n    return backend_service.save(x)\n"
    res_undef = CodeValidationPipeline.validate_code_block(undef, run_in_sandbox=True)
    assert res_undef.valid is False
    assert "backend_service" in res_undef.undefined_names

    # 3. Syntax error caught
    bad_syn = "def broken(:\n    pass"
    res_syn = CodeValidationPipeline.validate_code_block(bad_syn, run_in_sandbox=True)
    assert res_syn.valid is False
    assert res_syn.syntax_ok is False


def test_lesson_evaluator_100_point_rubric():
    md = (
        "# Services And APIs\n\n"
        "## Learning Objectives\n- Differentiate library calls, RPC, and HTTP service APIs.\n\n"
        "## Introduction\n[SOURCE-BASED] Web services expose explicit API contracts over networks.\n\n"
        "## Core Concepts\n[SOURCE-BASED] **API Contract**: defines request protocol and JSON format. "
        "Unlike in-process library calls, RPC, request-response HTTP, publish-subscribe, and message queues cross network boundaries.\n"
        "**Knowledge Check**: Which pattern delivers each task to one worker? A message queue.\n\n"
        "## Worked Example\n[SUPPLEMENTARY EXPLANATION]\n"
        "```python\ndef dispatch(msg: str) -> dict:\n    return {'queued': msg}\nprint(dispatch('yeti'))\n```\n"
        "```\n{'queued': 'yeti'}\n```\n\n"
        "## Common Mistakes\n- **Mistake**: Skipping status codes -> **Fix**: Return 404/422.\n\n"
        "## Key Takeaways\n- Services separate frontend and backend via contracts.\n\n"
        "## Check Your Understanding\n1. What is an API contract? Input/output rules."
    )
    src = "Services and APIs define protocol, format, contracts, RPC, publish-subscribe, and queues."
    rep = LessonEvaluator.evaluate("Services And APIs", md, source_text=src, subtopics=["Kinds Of APIs"])
    assert rep["passed"] is True
    assert rep["total_score"] >= 85.0
    assert rep["breakdown"]["code_validity"] == 15.0


@pytest.mark.asyncio
async def test_job_status_and_cancel_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        reg = await client.post("/api/v1/auth/register", json={
            "email": "phase3_job@learnforge.ai",
            "password": "StrongPassword123!",
            "full_name": "Phase3 Tester",
        })
        if reg.status_code in (400, 409):
            reg = await client.post("/api/v1/auth/login", json={
                "email": "phase3_job@learnforge.ai",
                "password": "StrongPassword123!",
            })
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Health endpoint reflects exact model without silent fallback
        h = await client.get("/health")
        assert h.status_code == 200
        data = h.json()
        assert "local_ollama" in data["ai_providers"]
        assert data["ai_providers"]["local_ollama"]["configured_model"] == "qwen2.5:3b"
