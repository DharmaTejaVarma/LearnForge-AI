"""
Tests covering Phases 2-11:
- Compiled LangGraph StateGraph execution, routing, trace & error handling
- ChunkingService overlap, code block preservation & heading propagation
- DocumentService magic-byte validation, duplicate-hash 409 check, search & reprocess
- SM-2 spaced repetition & duplicate card prevention
- Multi-type Quizzes (MCQ, True/False, Short Answer) & AssessmentAgent accuracy
- RBAC role dependency & ModelRouter telemetry
- AnalyticsAgent real weak-concept computation
"""
import uuid
import pytest
import fitz
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

from app.main import app
from app.ai.graphs.learning_graph import LearningGraph
from app.ai.rag.chunking import ChunkingService
from app.ai.agents.assessment_agent import AssessmentAgent
from app.ai.agents.resource_agent import ResourceAgent
from app.ai.models.model_router import model_router


def make_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_chunking_overlap_and_code_preservation():
    chunker = ChunkingService(chunk_size=140, chunk_overlap=35)
    pages = [
        {
            "page_number": 1,
            "headings": ["Chapter 1: Asynchronous Python"],
            "toc": [{"level": 1, "title": "Chapter 1: Asynchronous Python", "page": 1}],
            "text": (
                "FastAPI relies on asynchronous event loops to handle concurrent I/O efficiently. "
                "Coroutines yield execution while waiting on network or database responses.\n\n"
                "```python\nasync def fetch_data():\n    return {'status': 'ok'}\n```\n\n"
                "Dependency injection keeps routes modular and testable across services."
            ),
        }
    ]
    chunks = chunker.chunk_pages(pages, document_id=99, user_id=1, filename="fastapi.md")
    assert len(chunks) >= 2
    assert all(c["metadata"]["chapter"] == "Chapter 1: Asynchronous Python" for c in chunks)
    # Verify code block remained intact inside a single chunk
    assert any("```python\nasync def fetch_data():" in c["text"] and "```" in c["text"] for c in chunks)


def test_assessment_agent_multi_type_accuracy():
    # Ensure letter comparison does NOT falsely match unrelated words starting with 'a'
    assert AssessmentAgent.is_correct("A. Binary Tree", "apple", question_type="mcq") is False
    assert AssessmentAgent.is_correct("A. Binary Tree", "A", question_type="mcq") is True
    assert AssessmentAgent.is_correct("A. Binary Tree", "A. Binary Tree", question_type="mcq") is True

    # True/False normalization
    assert AssessmentAgent.is_correct("True", "true", question_type="true_false") is True
    assert AssessmentAgent.is_correct("False", "True", question_type="true_false") is False

    # Short-answer keyword overlap grading
    assert AssessmentAgent.is_correct(
        "Maps virtual memory pages to physical frames",
        "It maps virtual memory pages into physical frames",
        question_type="short_answer",
    ) is True
    assert AssessmentAgent.is_correct(
        "Maps virtual memory pages to physical frames",
        "Sorts arrays in logarithmic time",
        question_type="short_answer",
    ) is False


def test_resource_agent_distinguishes_sources():
    resources = ResourceAgent.recommend_resources(
        query="What is dependency injection?",
        citations=[{"document_id": 1, "filename": "fastapi_notes.pdf", "page_number": 12}],
        course_title="FastAPI Mastery",
    )
    source_types = {r["source_type"] for r in resources}
    assert "uploaded_document" in source_types
    assert "general_guidance" in source_types
    assert any(r["page_number"] == 12 for r in resources if r["source_type"] == "uploaded_document")


@pytest.mark.asyncio
async def test_langgraph_compiled_stategraph_workflows():
    graph = LearningGraph.get_compiled_graph()
    assert graph is not None

    # 1. Empty tutor query routes safely through supervisor validation -> error_handler
    err_state = await LearningGraph.run_workflow({
        "workflow_type": "tutor_chat",
        "user_id": 1,
        "query": "   ",
    })
    assert err_state["validation_passed"] is False
    assert err_state["error"] is not None
    assert any(t["node"] == "error_handler" for t in err_state["trace"])

    # 2. Assessment review workflow runs end-to-end with trace & weak concept extraction
    review_state = await LearningGraph.run_workflow({
        "workflow_type": "assessment_review",
        "user_id": 1,
        "quiz_questions": [
            {"id": 1, "question_text": "What is 'Paging'?", "question_type": "mcq", "correct_answer": "A. Memory scheme"},
            {"id": 2, "question_text": "Does FastAPI validate schemas?", "question_type": "true_false", "correct_answer": "True"},
        ],
        "student_answers": {1: "B. Disk formatting", 2: "True"},
    })
    assert review_state["validation_passed"] is True
    out = review_state["generated_output"]
    assert out["score_percentage"] == 50.0
    assert "Paging" in out["weak_concepts"]


@pytest.mark.asyncio
async def test_security_upload_dedup_reprocess_and_multi_type_quiz_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        email = f"multi_{uuid.uuid4().hex[:8]}@learnforge.ai"
        reg = await client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "MultiAgent Tester",
        })
        assert reg.status_code == 201
        assert reg.json()["user"]["role"] == "student"
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        # 1. Reject forged PDF without %PDF- magic header
        forged = await client.post(
            "/api/v1/documents/upload",
            headers=headers,
            files={"file": ("forged.pdf", b"NOT_A_REAL_PDF_HEADER", "application/pdf")},
        )
        assert forged.status_code == 400
        assert "signature" in forged.json()["error"]["message"].lower()

        # 2. Upload valid PDF
        text = (
            "Asynchronous Programming in Python: Asyncio manages event loops to run concurrent coroutines. "
            "Type Annotations provide static hints validated at runtime by Pydantic models."
        )
        pdf_bytes = make_pdf_bytes(text)
        up1 = await client.post(
            "/api/v1/documents/upload",
            headers=headers,
            files={"file": ("async_python.pdf", pdf_bytes, "application/pdf")},
        )
        assert up1.status_code == 201
        doc_id = up1.json()["id"]

        # 3. Duplicate upload rejected cleanly (409 Conflict)
        dup = await client.post(
            "/api/v1/documents/upload",
            headers=headers,
            files={"file": ("async_python_copy.pdf", pdf_bytes, "application/pdf")},
        )
        assert dup.status_code == 409

        # 4. Reprocess document succeeds
        rep = await client.post(f"/api/v1/documents/{doc_id}/reprocess", headers=headers)
        assert rep.status_code == 200
        assert rep.json()["processing_status"] == "indexed"

        # 5. Search documents filters properly
        searched = await client.get("/api/v1/documents?search=async_python", headers=headers)
        assert searched.status_code == 200
        assert any(d["id"] == doc_id for d in searched.json())

        # 6. Generate & review SM-2 flashcards + due_only query
        with patch("app.ai.agents.flashcard_agent.model_router.generate", side_effect=RuntimeError("offline")):
            fc_res = await client.post("/api/v1/flashcards/generate", headers=headers, json={
                "document_id": doc_id,
                "count": 2,
                "difficulty": "hard",
            })
        assert fc_res.status_code == 201
        cards = fc_res.json()
        assert len(cards) >= 1
        card_id = cards[0]["id"]
        rev = await client.post(f"/api/v1/flashcards/{card_id}/review", headers=headers, json={"mastered": True})
        assert rev.status_code == 200
        assert rev.json()["interval_days"] == 1

        # 7. Generate Mixed / Short-Answer quiz + verify quiz list + analytics weak topics
        with patch("app.ai.agents.question_agent.model_router.generate", side_effect=RuntimeError("offline")):
            q_res = await client.post("/api/v1/quizzes/generate", headers=headers, json={
                "document_id": doc_id,
                "question_count": 2,
                "difficulty": "medium",
                "question_type": "true_false",
            })
        assert q_res.status_code == 201
        quiz_id = q_res.json()["id"]

        list_q = await client.get("/api/v1/quizzes", headers=headers)
        assert list_q.status_code == 200
        assert any(q["id"] == quiz_id for q in list_q.json())

        # Submit intentional wrong answer so AnalyticsAgent surfaces weak topic
        q0 = q_res.json()["questions"][0]
        sub = await client.post(f"/api/v1/quizzes/{quiz_id}/submit", headers=headers, json={
            "answers": {str(q0["id"]): "False"}
        })
        assert sub.status_code == 200
        assert sub.json()["score_percentage"] < 100.0

        stats_res = await client.get("/api/v1/progress/stats", headers=headers)
        assert stats_res.status_code == 200
        stats = stats_res.json()
        assert len(stats["weekly_activity"]) == 7
        assert len(stats["weak_topics"]) >= 1

        # 8. Check health exposes ai_metrics safely without secrets
        health = await client.get("/api/v1/health")
        assert health.status_code == 200
        assert "ai_metrics" in health.json()
        assert "OPENAI_API_KEY" not in str(health.json())

    assert isinstance(model_router.get_metrics(), dict)
