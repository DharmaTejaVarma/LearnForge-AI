from typing import TypedDict, List, Dict, Any, Optional
from app.ai.agents.document_agent import DocumentAgent
from app.ai.agents.content_agent import ContentAgent
from app.ai.agents.lesson_agent import LessonAgent
from app.ai.agents.question_agent import QuestionAgent
from app.ai.agents.flashcard_agent import FlashcardAgent
from app.ai.agents.tutor_agent import TutorAgent
from app.ai.agents.assessment_agent import AssessmentAgent
from app.ai.agents.supervisor import SupervisorAgent

class LearningGraphState(TypedDict):
    """LangGraph state schema coordinating course synthesis and learning workflows."""
    user_id: int
    document_id: Optional[int]
    course_id: Optional[int]
    workflow_type: str # course_generation, flashcard_generation, quiz_generation, tutor_chat
    query: Optional[str]
    context_chunks: List[Dict[str, Any]]
    generated_output: Dict[str, Any]
    error: Optional[str]

class LearningGraph:
    """Workflow coordination graph using supervisor pattern."""

    @staticmethod
    async def run_workflow(state: LearningGraphState) -> LearningGraphState:
        workflow = state.get("workflow_type", "tutor_chat")

        if workflow == "tutor_chat":
            res = await TutorAgent.respond_to_query(
                question=state.get("query", ""),
                user_id=state["user_id"],
                document_id=state.get("document_id")
            )
            state["generated_output"] = res

        elif workflow == "flashcard_generation":
            cards = await FlashcardAgent.generate_cards(
                user_id=state["user_id"],
                document_id=state.get("document_id"),
                count=5
            )
            state["generated_output"] = {"cards": cards}

        elif workflow == "quiz_generation":
            questions = await QuestionAgent.generate_questions(
                user_id=state["user_id"],
                document_id=state.get("document_id"),
                count=5
            )
            state["generated_output"] = {"questions": questions}

        return state
