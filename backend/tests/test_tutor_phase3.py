import pytest
import uuid
from httpx import AsyncClient, ASGITransport
import fitz
from app.main import app
from app.ai.agents.intent_detector import IntentDetector, TutorIntent
from app.ai.agents.tutor_agent import TutorAgent

def make_test_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    data = doc.tobytes()
    doc.close()
    return data

def test_intent_detection_greetings_and_general_chat():
    """Verify that greetings and pleasantries are accurately classified without RAG."""
    # Greetings
    for g in ["Hi", "Hello", "Hey", "Good morning", "Hello tutor"]:
        res = IntentDetector.detect_intent(g)
        assert res.intent == TutorIntent.GREETING, f"Expected GREETING for '{g}', got {res.intent}"

    # General chat
    for chat in ["How are you?", "Thank you", "Thanks a lot", "Bye", "Who are you?"]:
        res = IntentDetector.detect_intent(chat)
        assert res.intent == TutorIntent.GENERAL_CONVERSATION, f"Expected GENERAL_CONVERSATION for '{chat}', got {res.intent}"

    # Unrelated queries
    for unrelated in ["What is the weather today?", "Who won the football game?", "Give me a recipe for chocolate cake"]:
        res = IntentDetector.detect_intent(unrelated)
        assert res.intent == TutorIntent.UNRELATED, f"Expected UNRELATED for '{unrelated}', got {res.intent}"

def test_intent_detection_educational_and_followup():
    """Verify educational questions and pronoun-based follow-ups."""
    # Direct educational questions
    q_res = IntentDetector.detect_intent("What is a binary search tree in computer science?")
    assert q_res.intent == TutorIntent.EDUCATIONAL_QUESTION

    # Follow-up with history
    mock_history = [
        {"role": "user", "content": "What is a binary search tree in computer science?"},
        {"role": "assistant", "content": "A binary search tree is a node-based binary tree data structure..."},
    ]

    followup_res = IntentDetector.detect_intent("Can you give another example of it?", history=mock_history)
    assert followup_res.intent == TutorIntent.FOLLOW_UP
    assert "binary search tree" in followup_res.contextualized_query.lower()

    # Learning assistance request
    summary_res = IntentDetector.detect_intent("Summarize this lesson step by step", history=mock_history)
    assert summary_res.intent in (TutorIntent.LEARNING_ASSISTANCE, TutorIntent.FOLLOW_UP)

@pytest.mark.asyncio
async def test_tutor_greetings_bypass_rag_completely():
    """Verify greetings receive instant conversational responses with 0 citations and no vector search."""
    res = await TutorAgent.respond_to_query(
        question="Hello! How are you doing today?",
        user_id=1,
        course_title="Data Structures & Algorithms",
    )
    assert "Hello" in res["answer"] or "Welcome" in res["answer"] or "Data Structures & Algorithms" in res["answer"]
    assert res["citations"] == []
    assert res["provider_used"].startswith("rule_based")
    assert res["intent"] in ("greeting", "general_conversation")

@pytest.mark.asyncio
async def test_tutor_unrelated_query_scope_guard():
    """Verify unrelated questions (weather, recipes) are politely declined without RAG."""
    res = await TutorAgent.respond_to_query(
        question="What is the weather forecast in Paris today?",
        user_id=1,
        course_title="Linear Algebra",
    )
    assert "Linear Algebra" in res["answer"]
    assert "focused" in res["answer"].lower() or "outside" in res["answer"].lower() or "cannot assist" in res["answer"].lower()
    assert res["citations"] == []
    assert res["intent"] == "unrelated"

@pytest.mark.asyncio
async def test_tutor_end_to_end_educational_and_conversation_flow():
    """Full end-to-end test of the AI Tutor API with document grounding, follow-ups, and user isolation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register Student Alice
        email_a = f"alice_tutor_{uuid.uuid4().hex[:8]}@learnforge.ai"
        res_a = await client.post("/api/v1/auth/register", json={
            "email": email_a,
            "password": "Password123!",
            "full_name": "Alice Learner"
        })
        assert res_a.status_code == 201
        token_a = res_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # 2. Alice uploads Operating Systems document
        os_text = (
            "Virtual Memory and Paging Mechanics: "
            "Paging is a memory management scheme by which a computer stores and retrieves data from secondary storage "
            "for use in main memory. The operating system retrieves data from secondary storage in same-size blocks "
            "called pages. Page tables map virtual addresses into physical frame addresses. Page faults occur when "
            "a requested page is not currently resident in physical RAM."
        )
        pdf_bytes = make_test_pdf(os_text)
        upload_res = await client.post(
            "/api/v1/documents/upload",
            headers=headers_a,
            files={"file": ("operating_systems_notes.pdf", pdf_bytes, "application/pdf")}
        )
        assert upload_res.status_code == 201
        doc_id = upload_res.json()["id"]

        # 3. Test Greeting endpoint
        greet_res = await client.post(
            "/api/v1/tutor/chat",
            headers=headers_a,
            json={"question": "Hi tutor!", "document_id": doc_id}
        )
        assert greet_res.status_code == 200
        greet_data = greet_res.json()
        assert len(greet_data["citations"]) == 0
        assert greet_data["intent"] == "greeting"
        conv_id = greet_data["conversation_id"]
        assert conv_id is not None

        # 4. Test Educational Question Grounded in Uploaded Material
        edu_res = await client.post(
            "/api/v1/tutor/chat",
            headers=headers_a,
            json={
                "question": "What is paging and when do page faults occur?",
                "document_id": doc_id,
                "conversation_id": conv_id,
            }
        )
        assert edu_res.status_code == 200
        edu_data = edu_res.json()
        assert "paging" in edu_data["answer"].lower() or "page fault" in edu_data["answer"].lower() or "memory" in edu_data["answer"].lower()
        assert len(edu_data["citations"]) > 0
        assert edu_data["citations"][0]["page_number"] == 1

        # 5. Test Follow-up question relying on previous turn
        follow_res = await client.post(
            "/api/v1/tutor/chat",
            headers=headers_a,
            json={
                "question": "Can you give me a simple real-world analogy of it?",
                "document_id": doc_id,
                "conversation_id": conv_id,
            }
        )
        assert follow_res.status_code == 200
        follow_data = follow_res.json()
        assert follow_data["intent"] in ("follow_up", "learning_assistance", "educational_question")
        assert len(follow_data["answer"]) > 40

        # 6. Test Source Limitations (Asking about completely unmentioned topic)
        unmentioned_res = await client.post(
            "/api/v1/tutor/chat",
            headers=headers_a,
            json={
                "question": "What does my document say about photosystem II and chloroplasts?",
                "document_id": doc_id,
                "conversation_id": conv_id,
            }
        )
        assert unmentioned_res.status_code == 200
        unmentioned_data = unmentioned_res.json()
        assert "couldn't find" in unmentioned_data["answer"].lower() or "not" in unmentioned_data["answer"].lower()

        # 7. Test History Retrieval
        history_res = await client.get(
            f"/api/v1/tutor/history?conversation_id={conv_id}",
            headers=headers_a
        )
        assert history_res.status_code == 200
        history_items = history_res.json()
        assert len(history_items) >= 4  # Greeting + Edu + Follow-up + Unmentioned

        # 8. Test Dynamic Suggestions
        sugg_res = await client.get("/api/v1/tutor/suggestions", headers=headers_a)
        assert sugg_res.status_code == 200
        suggestions = sugg_res.json()["suggestions"]
        assert len(suggestions) >= 3

        # 9. Test User Isolation (Bob cannot see Alice's history)
        email_b = f"bob_tutor_{uuid.uuid4().hex[:8]}@learnforge.ai"
        res_b = await client.post("/api/v1/auth/register", json={
            "email": email_b,
            "password": "Password123!",
            "full_name": "Bob Learner"
        })
        assert res_b.status_code == 201
        token_b = res_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Bob requests Alice's conversation history -> MUST be empty
        bob_history = await client.get(
            f"/api/v1/tutor/history?conversation_id={conv_id}",
            headers=headers_b
        )
        assert bob_history.status_code == 200
        assert len(bob_history.json()) == 0

        # Bob attempts to chat with Alice's document -> must raise 404/403
        bob_chat = await client.post(
            "/api/v1/tutor/chat",
            headers=headers_b,
            json={"question": "Tell me about this document", "document_id": doc_id}
        )
        assert bob_chat.status_code in (403, 404)
