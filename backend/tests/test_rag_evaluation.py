"""
Phase 9 RAG Evaluation Suite:
Tests retrieval precision, recall, out-of-scope rejection, multi-passage coverage,
and technical/formula concept matching against deterministic indexed documents.
"""
import uuid
import pytest
import fitz
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.ai.rag.retriever import RAGRetriever
from app.ai.agents.tutor_agent import TutorAgent


def build_multi_page_pdf(page_texts: list[str]) -> bytes:
    doc = fitz.open()
    for text in page_texts:
        page = doc.new_page()
        page.insert_text((50, 72), text)
    raw = doc.tobytes()
    doc.close()
    return raw


@pytest.mark.asyncio
async def test_rag_evaluation_precision_recall_and_out_of_scope():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        email = f"rag_eval_{uuid.uuid4().hex[:8]}@learnforge.ai"
        reg = await client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "RAG Evaluator",
        })
        assert reg.status_code == 201
        user_id = reg.json()["user"]["id"]
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        pages = [
            "Page 1 Linear Algebra: Eigenvalues lambda satisfy the characteristic equation det(A - lambda I) = 0 for a square matrix A.",
            "Page 2 Optimization: Gradient descent updates parameters via theta = theta - alpha * grad(L(theta)) where alpha is the learning rate.",
            "Page 3 Neural Networks: Backpropagation applies the chain rule across layers to compute gradients with respect to weights.",
        ]
        pdf_bytes = build_multi_page_pdf(pages)
        up = await client.post(
            "/api/v1/documents/upload",
            headers=headers,
            files={"file": ("ml_math_foundations.pdf", pdf_bytes, "application/pdf")},
        )
        assert up.status_code == 201
        doc_id = up.json()["id"]

        # 1. Formula/Technical Concept Recall (Page 1)
        p_eigen = RAGRetriever.retrieve(
            query="How do eigenvalues satisfy the characteristic equation?",
            user_id=user_id,
            document_id=doc_id,
            top_k=3,
        )
        assert len(p_eigen) >= 1
        assert p_eigen[0]["page_number"] == 1
        assert "characteristic equation" in p_eigen[0]["text"].lower()

        # 2. Multi-passage Coverage (Gradient Descent + Backpropagation)
        p_multi = RAGRetriever.retrieve(
            query="How do gradient descent and backpropagation compute parameter updates?",
            user_id=user_id,
            document_id=doc_id,
            top_k=3,
        )
        retrieved_pages = {p["page_number"] for p in p_multi}
        assert len(retrieved_pages) >= 2
        assert 2 in retrieved_pages or 3 in retrieved_pages

        # 3. Uncovered / Out-of-Domain Query must NOT fabricate citations
        p_uncovered = RAGRetriever.retrieve(
            query="What temperature bakes sourdough bread best in French ovens?",
            user_id=user_id,
            document_id=doc_id,
            top_k=3,
            min_similarity=0.30,
        )
        assert len(p_uncovered) == 0

        # 4. Tutor scope guard on completely unrelated question
        tutor_unrelated = await TutorAgent.respond_to_query(
            question="What is the weather forecast tomorrow?",
            user_id=user_id,
            document_id=doc_id,
            course_title="ML Math",
        )
        assert tutor_unrelated["citations"] == []
        assert tutor_unrelated["intent"] == "unrelated"

        await client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
