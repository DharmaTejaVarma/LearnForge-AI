import io
import uuid
import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport
import fitz  # PyMuPDF
import docx  # python-docx
from app.main import app

def create_sample_pdf(content: str = "This is a sample educational text for LearnForge AI.") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), content)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

def create_sample_docx(content: str = "This is a sample educational DOCX content for LearnForge AI testing.") -> bytes:
    doc = docx.Document()
    doc.add_heading("Chapter 1: Foundations", level=1)
    doc.add_paragraph(content)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()

@pytest.mark.asyncio
async def test_document_upload_and_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        owner_email = f"doc_owner_{uuid.uuid4().hex[:8]}@learnforge.ai"
        intruder_email = f"doc_intruder_{uuid.uuid4().hex[:8]}@learnforge.ai"

        # 1. Register User A
        res_a = await client.post("/api/v1/auth/register", json={
            "email": owner_email,
            "password": "Password123!",
            "full_name": "Doc Owner"
        })
        token_a = res_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # 2. Upload valid PDF
        pdf_bytes = create_sample_pdf("Welcome to Python Fundamentals. Python is an interpreted high-level language.")
        files = {"file": ("python_intro.pdf", pdf_bytes, "application/pdf")}
        upload_res = await client.post("/api/v1/documents/upload", headers=headers_a, files=files)
        assert upload_res.status_code == 201
        doc_data = upload_res.json()
        doc_id = doc_data["id"]
        assert doc_data["original_filename"] == "python_intro.pdf"
        assert doc_data["page_count"] == 1
        assert doc_data["character_count"] > 20
        assert doc_data["processing_status"] in ("processed", "indexed")

        # 3. Upload valid DOCX
        docx_bytes = create_sample_docx("Machine Learning Overview: Supervised and Unsupervised Learning.")
        files_docx = {"file": ("ml_notes.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        docx_res = await client.post("/api/v1/documents/upload", headers=headers_a, files=files_docx)
        assert docx_res.status_code == 201
        docx_data = docx_res.json()
        assert docx_data["original_filename"] == "ml_notes.docx"
        assert docx_data["processing_status"] in ("processed", "indexed")

        # 4. Reject invalid extension
        files_bad = {"file": ("malware.exe", b"binarycontent", "application/octet-stream")}
        bad_ext_res = await client.post("/api/v1/documents/upload", headers=headers_a, files=files_bad)
        assert bad_ext_res.status_code == 400

        # 5. Reject empty file (0 bytes)
        files_empty = {"file": ("empty.pdf", b"", "application/pdf")}
        empty_res = await client.post("/api/v1/documents/upload", headers=headers_a, files=files_empty)
        assert empty_res.status_code == 400

        # 6. Reject scanned/empty PDF with OCR message
        scanned_pdf = create_sample_pdf("   ")
        files_scanned = {"file": ("scanned.pdf", scanned_pdf, "application/pdf")}
        scanned_res = await client.post("/api/v1/documents/upload", headers=headers_a, files=files_scanned)
        assert scanned_res.status_code == 400
        assert "OCR" in scanned_res.json()["error"]["message"]

        # 7. List documents for User A
        list_res = await client.get("/api/v1/documents", headers=headers_a)
        assert list_res.status_code == 200
        docs_list = list_res.json()
        assert len(docs_list) >= 2
        assert any(d["id"] == doc_id for d in docs_list)

        # 8. Get document details
        detail_res = await client.get(f"/api/v1/documents/{doc_id}", headers=headers_a)
        assert detail_res.status_code == 200
        stored_file = detail_res.json()["stored_filename"]
        stored_path = Path("uploads") / stored_file
        assert stored_path.exists()

        # 9. Register User B and verify ownership isolation
        res_b = await client.post("/api/v1/auth/register", json={
            "email": intruder_email,
            "password": "Password123!",
            "full_name": "Doc Intruder"
        })
        token_b = res_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # User B cannot access User A's document
        forbidden_res = await client.get(f"/api/v1/documents/{doc_id}", headers=headers_b)
        assert forbidden_res.status_code == 403

        # User B cannot delete User A's document
        forbidden_del = await client.delete(f"/api/v1/documents/{doc_id}", headers=headers_b)
        assert forbidden_del.status_code == 403

        # User B's list should NOT contain User A's document
        list_b = await client.get("/api/v1/documents", headers=headers_b)
        assert all(d["id"] != doc_id for d in list_b.json())

        # 10. User A deletes document -> removes DB record and physical file
        del_res = await client.delete(f"/api/v1/documents/{doc_id}", headers=headers_a)
        assert del_res.status_code == 200
        assert not stored_path.exists()

        # Document is gone
        get_deleted = await client.get(f"/api/v1/documents/{doc_id}", headers=headers_a)
        assert get_deleted.status_code == 404
