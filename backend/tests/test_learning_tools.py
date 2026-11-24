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
async def test_complete_learning_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        unique_email = f"learner_{uuid.uuid4().hex[:8]}@learnforge.ai"
        # 1. Register Student
        reg_res = await client.post("/api/v1/auth/register", json={
            "email": unique_email,
            "password": "Password123!",
            "full_name": "Active Learner"
        })
        assert reg_res.status_code == 201
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Upload Document on Data Structures & Algorithms
        dsa_text = (
            "Binary Search Trees (BST) are node-based binary tree data structures which have the following properties: "
            "The left subtree of a node contains only nodes with keys lesser than the node's key. "
            "The right subtree of a node contains only nodes with keys greater than the node's key. "
            "Both the left and right subtrees must also be binary search trees. "
            "Search, insertion, and deletion operations take O(log n) time in balanced trees."
        )
        pdf_bytes = make_test_pdf(dsa_text)
        files = {"file": ("data_structures.pdf", pdf_bytes, "application/pdf")}
        doc_res = await client.post("/api/v1/documents/upload", headers=headers, files=files)
        assert doc_res.status_code == 201
        doc_id = doc_res.json()["id"]

        # 3. Generate Course
        from unittest.mock import patch
        mock_lesson_content = (
            "# Binary Search Trees\n\n"
            "## Learning Objectives\n"
            "- Master binary search tree invariants and properties.\n"
            "- Understand key operations including search, insertion, and traversal.\n"
            "- Evaluate time and space complexity across balanced and unbalanced variants.\n\n"
            "## Introduction\n"
            "A Binary Search Tree (BST) is a foundational non-linear data structure used throughout computer science. "
            "It organizes keys hierarchically so that search operations can eliminate half the search space with each comparison. "
            "This hierarchical organization provides efficient dynamic set operations compared to linear arrays.\n\n"
            "## Core Concepts\n"
            "In a binary search tree, every node satisfies the binary search property. "
            "Specifically, for any given node x, all keys in its left subtree are strictly less than x.key, "
            "and all keys in its right subtree are strictly greater than x.key. "
            "This invariant enables in-order tree traversal to output elements in monotonically increasing sorted order.\n\n"
            "## Worked Example\n"
            "Consider inserting the sequence 8, 3, 10, 1, 6 into an initially empty tree. "
            "The root becomes 8. Next, 3 is placed as the left child of 8. "
            "Then 10 is placed as the right child of 8. Following this rule, 1 becomes the left child of 3, "
            "and 6 becomes the right child of 3.\n\n"
            "## Common Mistakes\n"
            "A frequent misconception is assuming all binary trees are automatically binary search trees. "
            "Another critical pitfall is failing to rebalance the tree, which can cause operations to degrade from O(log n) to O(n).\n\n"
            "## Key Takeaways\n"
            "- Invariant: left child < parent < right child.\n"
            "- Average time complexity for search, insert, and delete is O(log n).\n"
            "- Worst-case complexity degrades to O(n) when elements are inserted in sorted order.\n\n"
            "## Check Your Understanding\n"
            "Q: What is the average time complexity for searching a balanced BST?\n"
            "A: O(log n) because half the remaining nodes are pruned at each step."
        )
        with patch("app.ai.agents.lesson_agent.model_router.generate", return_value={"content": mock_lesson_content}):
            course_res = await client.post("/api/v1/courses/generate", headers=headers, json={
                "document_id": doc_id,
                "difficulty_level": "intermediate",
                "target_chapters_count": 3
            })
        assert course_res.status_code == 201
        course_data = course_res.json()
        course_id = course_data["id"]
        assert len(course_data["chapters"]) >= 1
        first_chapter = course_data["chapters"][0]
        assert len(first_chapter["topics"]) >= 1
        first_topic = first_chapter["topics"][0]
        lesson_id = first_topic["lesson"]["id"]
        assert lesson_id is not None

        # 4. View Lesson & Toggle Completion
        lesson_res = await client.get(f"/api/v1/lessons/{lesson_id}", headers=headers)
        assert lesson_res.status_code == 200
        assert "Binary Search Trees" in lesson_res.json()["content"] or "Overview" in lesson_res.json()["content"]

        toggle_res = await client.post(f"/api/v1/lessons/{lesson_id}/toggle-complete", headers=headers)
        assert toggle_res.status_code == 200
        assert toggle_res.json()["is_completed"] is True

        # 5. Generate Flashcards
        fc_gen = await client.post("/api/v1/flashcards/generate", headers=headers, json={
            "document_id": doc_id,
            "course_id": course_id,
            "count": 3
        })
        assert fc_gen.status_code == 201
        cards = fc_gen.json()
        assert len(cards) >= 1
        card_id = cards[0]["id"]

        # 6. Review Flashcard (Mark Mastered)
        rev_res = await client.post(f"/api/v1/flashcards/{card_id}/review", headers=headers, json={"mastered": True})
        assert rev_res.status_code == 200
        assert rev_res.json()["mastery_level"] == "mastered"
        assert rev_res.json()["review_count"] == 1

        # 7. Generate Quiz
        quiz_gen = await client.post("/api/v1/quizzes/generate", headers=headers, json={
            "document_id": doc_id,
            "course_id": course_id,
            "question_count": 2,
            "difficulty": "medium"
        })
        assert quiz_gen.status_code == 201
        quiz_data = quiz_gen.json()
        quiz_id = quiz_data["id"]
        assert len(quiz_data["questions"]) >= 1

        # 8. Submit Quiz
        q0 = quiz_data["questions"][0]
        answers = {str(q0["id"]): q0["correct_answer"]}
        submit_res = await client.post(f"/api/v1/quizzes/{quiz_id}/submit", headers=headers, json={"answers": answers})
        assert submit_res.status_code == 200
        attempt_data = submit_res.json()
        assert attempt_data["score_percentage"] >= 50.0

        # 9. Ask Socratic AI Tutor
        tutor_res = await client.post("/api/v1/tutor/chat", headers=headers, json={
            "question": "What is the search time complexity of a balanced binary search tree?",
            "document_id": doc_id
        })
        assert tutor_res.status_code == 200
        tutor_data = tutor_res.json()
        assert len(tutor_data["answer"]) > 10
        assert len(tutor_data["citations"]) >= 1

        # 10. Check Progress Analytics
        prog_res = await client.get("/api/v1/progress/stats", headers=headers)
        assert prog_res.status_code == 200
        prog_data = prog_res.json()
        assert prog_data["total_courses"] >= 1
        assert prog_data["completed_lessons"] >= 1
        assert prog_data["flashcards_mastered"] >= 1
        assert prog_data["quizzes_taken"] >= 1
