import uuid
import pytest
from httpx import AsyncClient, ASGITransport
import fitz
from app.main import app


def make_test_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.mark.asyncio
async def test_flashcards_course_scoping_and_management():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register user
        unique_email = f"fc_test_{uuid.uuid4().hex[:8]}@learnforge.ai"
        reg_res = await client.post("/api/v1/auth/register", json={
            "email": unique_email,
            "password": "Password123!",
            "full_name": "Flashcard Tester"
        })
        assert reg_res.status_code == 201
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Upload document
        text = "Polymorphism is the provision of a single interface to entities of different types. Inheritance enables a class to derive properties and characteristics from another class."
        pdf_bytes = make_test_pdf(text)
        files = {"file": ("oop.pdf", pdf_bytes, "application/pdf")}
        doc_res = await client.post("/api/v1/documents/upload", headers=headers, files=files)
        assert doc_res.status_code == 201
        doc_id = doc_res.json()["id"]

        # Generate course
        course_res = await client.post("/api/v1/courses/generate", headers=headers, json={
            "document_id": doc_id,
            "difficulty_level": "beginner",
            "target_chapters_count": 2
        })
        assert course_res.status_code == 201
        course_id = course_res.json()["id"]

        # 1. Generate flashcards scoped by course_id
        fc_gen = await client.post("/api/v1/flashcards/generate", headers=headers, json={
            "course_id": course_id,
            "count": 3,
            "difficulty": "easy"
        })
        assert fc_gen.status_code == 201
        cards = fc_gen.json()
        assert len(cards) >= 1
        card_id = cards[0]["id"]
        assert cards[0]["course_id"] == course_id

        # 2. List flashcards filtered by course_id
        list_res = await client.get(f"/api/v1/flashcards?course_id={course_id}", headers=headers)
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 1

        # 3. Delete single flashcard
        del_res = await client.delete(f"/api/v1/flashcards/{card_id}", headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["id"] == card_id

        # 4. Verify deleted
        list_after = await client.get(f"/api/v1/flashcards?course_id={course_id}", headers=headers)
        assert all(c["id"] != card_id for c in list_after.json())

        # 5. Clear remaining flashcards
        clear_res = await client.delete(f"/api/v1/flashcards?course_id={course_id}", headers=headers)
        assert clear_res.status_code == 200
        list_empty = await client.get(f"/api/v1/flashcards?course_id={course_id}", headers=headers)
        assert len(list_empty.json()) == 0


@pytest.mark.asyncio
async def test_quiz_course_scoping_results_and_deletion():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        unique_email = f"quiz_test_{uuid.uuid4().hex[:8]}@learnforge.ai"
        reg_res = await client.post("/api/v1/auth/register", json={
            "email": unique_email,
            "password": "Password123!",
            "full_name": "Quiz Tester"
        })
        assert reg_res.status_code == 201
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Upload document
        text = "Operating Systems manage computer hardware and provide common services for application software. The kernel is the core of an operating system that has complete control over everything in the system."
        pdf_bytes = make_test_pdf(text)
        files = {"file": ("os.pdf", pdf_bytes, "application/pdf")}
        doc_res = await client.post("/api/v1/documents/upload", headers=headers, files=files)
        assert doc_res.status_code == 201
        doc_id = doc_res.json()["id"]

        # Generate course
        course_res = await client.post("/api/v1/courses/generate", headers=headers, json={
            "document_id": doc_id,
            "difficulty_level": "intermediate",
            "target_chapters_count": 2
        })
        assert course_res.status_code == 201
        course_id = course_res.json()["id"]

        # 1. Generate quiz scoped by course_id
        quiz_gen = await client.post("/api/v1/quizzes/generate", headers=headers, json={
            "course_id": course_id,
            "question_count": 2,
            "difficulty": "hard"
        })
        assert quiz_gen.status_code == 201
        quiz_data = quiz_gen.json()
        quiz_id = quiz_data["id"]
        assert len(quiz_data["questions"]) >= 1
        assert quiz_data["course_id"] == course_id

        # 2. Submit quiz and check detailed question results
        q0 = quiz_data["questions"][0]
        answers = {str(q0["id"]): q0["correct_answer"]}
        submit_res = await client.post(f"/api/v1/quizzes/{quiz_id}/submit", headers=headers, json={"answers": answers})
        assert submit_res.status_code == 200
        attempt = submit_res.json()
        assert "question_results" in attempt
        assert len(attempt["question_results"]) >= 1
        q_result = attempt["question_results"][0]
        assert q_result["question_id"] == q0["id"]
        assert q_result["is_correct"] is True

        # 3. Check attempts list endpoint
        attempts_res = await client.get(f"/api/v1/quizzes/{quiz_id}/attempts", headers=headers)
        assert attempts_res.status_code == 200
        assert len(attempts_res.json()) >= 1

        # 4. Delete quiz
        del_quiz = await client.delete(f"/api/v1/quizzes/{quiz_id}", headers=headers)
        assert del_quiz.status_code == 200
        assert del_quiz.json()["id"] == quiz_id

        # 5. Verify quiz deleted (should return 404)
        get_res = await client.get(f"/api/v1/quizzes/{quiz_id}", headers=headers)
        assert get_res.status_code == 404
