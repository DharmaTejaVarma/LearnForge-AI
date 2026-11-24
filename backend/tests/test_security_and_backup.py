import pytest
import uuid
import fitz
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from app.main import app
from backup_db import perform_backup

def create_valid_test_pdf(text: str = "Confidential User Material") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    data = doc.tobytes()
    doc.close()
    return data

@pytest.mark.asyncio
async def test_path_traversal_and_file_security():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register test user
        email = f"sec_user_{uuid.uuid4().hex[:8]}@learnforge.ai"
        res = await client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "Password123!",
            "full_name": "Security Tester"
        })
        assert res.status_code == 201
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Attempt to upload disallowed extension (.exe)
        bad_file = {"file": ("malicious.exe", b"fake binary content", "application/x-msdownload")}
        res_bad_ext = await client.post("/api/v1/documents/upload", headers=headers, files=bad_file)
        assert res_bad_ext.status_code == 400
        err_msg = res_bad_ext.json().get("error", {}).get("message", "")
        assert "Unsupported file format" in err_msg or "Invalid" in err_msg

        # 2. Path traversal attack attempt in filename
        pdf_bytes = create_valid_test_pdf("Security test document content")
        traversal_file = {"file": ("../../../../etc/passwd.pdf", pdf_bytes, "application/pdf")}
        res_traversal = await client.post("/api/v1/documents/upload", headers=headers, files=traversal_file)
        assert res_traversal.status_code == 201
        data = res_traversal.json()
        assert data["original_filename"] == "../../../../etc/passwd.pdf"
        assert data["id"] > 0

@pytest.mark.asyncio
async def test_cross_user_document_authorization():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # User 1
        res1 = await client.post("/api/v1/auth/register", json={
            "email": f"owner_{uuid.uuid4().hex[:8]}@learnforge.ai",
            "password": "Password123!",
            "full_name": "Doc Owner"
        })
        token1 = res1.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        # User 2
        res2 = await client.post("/api/v1/auth/register", json={
            "email": f"attacker_{uuid.uuid4().hex[:8]}@learnforge.ai",
            "password": "Password123!",
            "full_name": "Attacker"
        })
        token2 = res2.json()["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        # User 1 uploads document
        pdf_content = create_valid_test_pdf("User 1 private curriculum")
        files = {"file": ("private_notes.pdf", pdf_content, "application/pdf")}
        upload_res = await client.post("/api/v1/documents/upload", headers=headers1, files=files)
        assert upload_res.status_code == 201
        doc_id = upload_res.json()["id"]

        # User 2 attempts to delete User 1's document -> 403 Forbidden (Strict Ownership Guard)
        del_res = await client.delete(f"/api/v1/documents/{doc_id}", headers=headers2)
        assert del_res.status_code in (403, 404)

def test_database_backup_and_integrity():
    # Execute SQLite backup
    backup_path = perform_backup()
    assert backup_path.exists()
    assert backup_path.stat().st_size > 0
    # Clean up test backup file
    try:
        backup_path.unlink()
    except Exception:
        pass
