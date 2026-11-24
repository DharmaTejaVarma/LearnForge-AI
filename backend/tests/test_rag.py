import pytest
import uuid
from httpx import AsyncClient, ASGITransport
import fitz
from app.main import app
from app.ai.rag.text_cleaner import TextCleaner
from app.ai.rag.chunking import ChunkingService
from app.ai.rag.retriever import RAGRetriever
from app.ai.rag.vector_store import VectorStoreManager

def make_test_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    data = doc.tobytes()
    doc.close()
    return data

def test_text_cleaner():
    raw = "  Hello   World!\u00a0\n\n\n\nThis is    a    test.  \r\n"
    cleaned = TextCleaner.clean(raw)
    assert cleaned == "Hello World!\n\nThis is a test."

def test_chunking_service():
    chunker = ChunkingService(chunk_size=100, chunk_overlap=20)
    pages = [
        {"page_number": 1, "text": "Paragraph 1 about artificial intelligence and its extensive applications across computer science.\n\nParagraph 2 about deep neural networks, transformers, and representation learning."}
    ]
    chunks = chunker.chunk_pages(pages, document_id=10, user_id=1, filename="ai.pdf")
    assert len(chunks) >= 2
    assert chunks[0]["metadata"]["document_id"] == 10
    assert chunks[0]["metadata"]["page_number"] == 1
    assert "artificial intelligence" in chunks[0]["text"]

@pytest.mark.asyncio
async def test_rag_end_to_end_and_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register User Alpha
        email_a = f"alpha_rag_{uuid.uuid4().hex[:8]}@learnforge.ai"
        res_a = await client.post("/api/v1/auth/register", json={
            "email": email_a,
            "password": "Password123!",
            "full_name": "Alpha Student"
        })
        assert res_a.status_code == 201
        token_a = res_a.json()["access_token"]
        user_a_id = res_a.json()["user"]["id"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # 2. User Alpha uploads Quantum Computing notes
        quantum_text = (
            "Quantum Superposition is a fundamental principle of quantum mechanics. "
            "It states that much like waves in classical physics, any two or more quantum states can be added together, "
            "and the result will be another valid quantum state. Conversely, that every quantum state can be represented "
            "as a sum of two or more other distinct states. Qubits can exist in a superposition of |0> and |1> states."
        )
        pdf_bytes = make_test_pdf(quantum_text)
        files = {"file": ("quantum_mechanics.pdf", pdf_bytes, "application/pdf")}
        upload_res = await client.post("/api/v1/documents/upload", headers=headers_a, files=files)
        assert upload_res.status_code == 201
        doc_a = upload_res.json()
        assert doc_a["processing_status"] == "indexed"
        doc_id = doc_a["id"]

        # 3. Retrieve relevant context for User Alpha
        passages = RAGRetriever.retrieve(
            query="What is quantum superposition and qubits?",
            user_id=user_a_id,
            document_id=doc_id,
            top_k=2
        )
        assert len(passages) >= 1
        assert "Superposition" in passages[0]["text"]
        assert passages[0]["page_number"] == 1
        assert passages[0]["similarity_score"] > 0.3

        # 4. Register User Beta
        email_b = f"beta_rag_{uuid.uuid4().hex[:8]}@learnforge.ai"
        res_b = await client.post("/api/v1/auth/register", json={
            "email": email_b,
            "password": "Password123!",
            "full_name": "Beta Student"
        })
        assert res_b.status_code == 201
        user_b_id = res_b.json()["user"]["id"]

        # 5. User Beta queries the same question -> MUST return 0 passages (Strict user isolation!)
        passages_b = RAGRetriever.retrieve(
            query="What is quantum superposition and qubits?",
            user_id=user_b_id,
            document_id=doc_id,
            top_k=2
        )
        assert len(passages_b) == 0

        # 6. Delete document for User Alpha -> ChromaDB vectors must be removed
        del_res = await client.delete(f"/api/v1/documents/{doc_id}", headers=headers_a)
        assert del_res.status_code == 200

        # Subsequent retrieval must return empty
        passages_after = RAGRetriever.retrieve(
            query="What is quantum superposition and qubits?",
            user_id=user_a_id,
            document_id=doc_id,
            top_k=2
        )
        assert len(passages_after) == 0
