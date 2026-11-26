from datetime import datetime
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.ai.agents.document_agent import DocumentAgent
from app.ai.agents.flashcard_agent import FlashcardAgent
from app.ai.agents.question_agent import QuestionAgent
from app.ai.agents.tutor_agent import TutorAgent
from app.ai.agents.assessment_agent import AssessmentAgent
from app.ai.agents.resource_agent import ResourceAgent
from app.ai.agents.supervisor import SupervisorAgent
from app.core.logging import logger


class LearningGraphState(TypedDict, total=False):
    """Typed LangGraph state schema coordinating multi-agent workflows."""
    workflow_type: str  # tutor_chat, flashcard_generation, quiz_generation, assessment_review, document_understanding, resource_lookup
    user_id: int
    document_id: Optional[int]
    document_ids: Optional[List[int]]
    course_id: Optional[int]
    course_title: Optional[str]
    lesson_id: Optional[int]
    lesson_title: Optional[str]
    lesson_context: Optional[str]
    exercise_prompt: Optional[str]
    tutor_mode: Optional[str]
    query: Optional[str]
    history: Optional[List[Dict[str, str]]]
    count: int
    difficulty: str
    question_type: str
    existing_fronts: Optional[List[str]]
    pages: Optional[List[Dict[str, Any]]]
    filename: Optional[str]
    quiz_questions: Optional[List[Dict[str, Any]]]
    student_answers: Optional[Dict[int, str]]
    context_chunks: List[Dict[str, Any]]
    supplementary_resources: List[Dict[str, Any]]
    generated_output: Dict[str, Any]
    resources_attached: bool
    validation_passed: bool
    retry_count: int
    max_retries: int
    trace: List[Dict[str, Any]]
    error: Optional[str]


async def _supervisor_plan_node(state: LearningGraphState) -> LearningGraphState:
    return SupervisorAgent.plan_workflow(state)


async def _tutor_node(state: LearningGraphState) -> LearningGraphState:
    trace = list(state.get("trace") or [])
    try:
        res = await TutorAgent.respond_to_query(
            question=state.get("query", ""),
            user_id=state["user_id"],
            document_id=state.get("document_id"),
            document_ids=state.get("document_ids"),
            course_id=state.get("course_id"),
            course_title=state.get("course_title"),
            lesson_id=state.get("lesson_id"),
            lesson_title=state.get("lesson_title"),
            lesson_context=state.get("lesson_context"),
            exercise_prompt=state.get("exercise_prompt"),
            tutor_mode=state.get("tutor_mode"),
            history=state.get("history"),
        )
        trace.append({"node": "tutor_agent", "status": "ok", "timestamp": datetime.utcnow().isoformat()})
        return {**state, "generated_output": res, "error": None, "trace": trace}
    except Exception as e:
        trace.append({"node": "tutor_agent", "status": "error", "error": str(e), "timestamp": datetime.utcnow().isoformat()})
        return {
            **state,
            "retry_count": int(state.get("retry_count", 0)) + 1,
            "error": str(e),
            "trace": trace,
        }


async def _flashcard_node(state: LearningGraphState) -> LearningGraphState:
    trace = list(state.get("trace") or [])
    try:
        cards = await FlashcardAgent.generate_cards(
            user_id=state["user_id"],
            document_id=state.get("document_id"),
            document_ids=state.get("document_ids"),
            count=int(state.get("count", 5) or 5),
            difficulty=state.get("difficulty", "medium") or "medium",
            existing_fronts=state.get("existing_fronts"),
        )
        trace.append({"node": "flashcard_agent", "count": len(cards), "timestamp": datetime.utcnow().isoformat()})
        return {**state, "generated_output": {"cards": cards}, "error": None, "trace": trace}
    except Exception as e:
        trace.append({"node": "flashcard_agent", "status": "error", "error": str(e), "timestamp": datetime.utcnow().isoformat()})
        return {
            **state,
            "retry_count": int(state.get("retry_count", 0)) + 1,
            "error": str(e),
            "trace": trace,
        }


async def _quiz_node(state: LearningGraphState) -> LearningGraphState:
    trace = list(state.get("trace") or [])
    try:
        questions = await QuestionAgent.generate_questions(
            user_id=state["user_id"],
            document_id=state.get("document_id"),
            document_ids=state.get("document_ids"),
            count=int(state.get("count", 5) or 5),
            difficulty=state.get("difficulty", "medium") or "medium",
            question_type=state.get("question_type", "mcq") or "mcq",
        )
        trace.append({"node": "quiz_agent", "count": len(questions), "timestamp": datetime.utcnow().isoformat()})
        return {**state, "generated_output": {"questions": questions}, "error": None, "trace": trace}
    except Exception as e:
        trace.append({"node": "quiz_agent", "status": "error", "error": str(e), "timestamp": datetime.utcnow().isoformat()})
        return {
            **state,
            "retry_count": int(state.get("retry_count", 0)) + 1,
            "error": str(e),
            "trace": trace,
        }


async def _assessment_node(state: LearningGraphState) -> LearningGraphState:
    trace = list(state.get("trace") or [])
    eval_res = AssessmentAgent.evaluate_quiz(
        questions=state.get("quiz_questions") or [],
        student_answers=state.get("student_answers") or {},
    )
    trace.append({"node": "assessment_agent", "score": eval_res.get("score_percentage"), "timestamp": datetime.utcnow().isoformat()})
    return {**state, "generated_output": eval_res, "error": None, "trace": trace}


async def _document_node(state: LearningGraphState) -> LearningGraphState:
    trace = list(state.get("trace") or [])
    analysis = DocumentAgent.analyze_document(
        pages=state.get("pages") or [],
        filename=state.get("filename") or "document",
    )
    trace.append({"node": "document_agent", "domain": analysis.get("subject_domain"), "timestamp": datetime.utcnow().isoformat()})
    return {**state, "generated_output": analysis, "error": None, "trace": trace}


async def _resource_node(state: LearningGraphState) -> LearningGraphState:
    trace = list(state.get("trace") or [])
    output = dict(state.get("generated_output") or {})
    citations = output.get("citations") or []
    resources = ResourceAgent.recommend_resources(
        query=state.get("query") or "",
        citations=citations,
        course_title=state.get("course_title"),
        lesson_title=state.get("lesson_title"),
    )
    output["resources"] = resources
    trace.append({"node": "resource_agent", "count": len(resources), "timestamp": datetime.utcnow().isoformat()})
    return {
        **state,
        "supplementary_resources": resources,
        "generated_output": output,
        "resources_attached": True,
        "trace": trace,
    }


async def _error_node(state: LearningGraphState) -> LearningGraphState:
    trace = list(state.get("trace") or [])
    trace.append({"node": "error_handler", "error": state.get("error"), "timestamp": datetime.utcnow().isoformat()})
    return {**state, "trace": trace}


async def _validate_node(state: LearningGraphState) -> LearningGraphState:
    return SupervisorAgent.validate_output(state)


class LearningGraph:
    """Compiled LangGraph StateGraph orchestrating LearnForge AI specialized agents."""

    _checkpointer = MemorySaver()
    _compiled_graph = None

    @classmethod
    def get_compiled_graph(cls):
        if cls._compiled_graph is not None:
            return cls._compiled_graph

        builder = StateGraph(LearningGraphState)
        builder.add_node("supervisor_plan", _supervisor_plan_node)
        builder.add_node("tutor_agent", _tutor_node)
        builder.add_node("flashcard_agent", _flashcard_node)
        builder.add_node("quiz_agent", _quiz_node)
        builder.add_node("assessment_agent", _assessment_node)
        builder.add_node("document_agent", _document_node)
        builder.add_node("resource_agent", _resource_node)
        builder.add_node("error_handler", _error_node)
        builder.add_node("supervisor_validate", _validate_node)

        builder.set_entry_point("supervisor_plan")
        builder.add_conditional_edges(
            "supervisor_plan",
            SupervisorAgent.route_to_agent,
            {
                "tutor_agent": "tutor_agent",
                "flashcard_agent": "flashcard_agent",
                "quiz_agent": "quiz_agent",
                "assessment_agent": "assessment_agent",
                "document_agent": "document_agent",
                "resource_agent": "resource_agent",
                "error_handler": "error_handler",
            },
        )

        for worker_node in ("tutor_agent", "flashcard_agent", "quiz_agent", "assessment_agent", "document_agent"):
            builder.add_edge(worker_node, "supervisor_validate")

        builder.add_edge("resource_agent", END)
        builder.add_edge("error_handler", END)

        builder.add_conditional_edges(
            "supervisor_validate",
            SupervisorAgent.decide_after_validation,
            {
                "tutor_agent": "tutor_agent",
                "flashcard_agent": "flashcard_agent",
                "quiz_agent": "quiz_agent",
                "assessment_agent": "assessment_agent",
                "document_agent": "document_agent",
                "resource_agent": "resource_agent",
                "end": END,
            },
        )

        cls._compiled_graph = builder.compile(checkpointer=cls._checkpointer)
        return cls._compiled_graph

    @classmethod
    async def run_workflow(
        cls,
        state: LearningGraphState,
        thread_id: Optional[str] = None,
    ) -> LearningGraphState:
        """Execute a multi-agent workflow through the compiled LangGraph StateGraph."""
        graph = cls.get_compiled_graph()
        tid = thread_id or f"lf_{state.get('user_id', 0)}_{state.get('workflow_type', 'default')}"
        config = {"configurable": {"thread_id": tid}}
        final_state = await graph.ainvoke(state, config=config)
        logger.info(
            f"LangGraph workflow '{final_state.get('workflow_type')}' completed "
            f"(nodes={len(final_state.get('trace', []))}, valid={final_state.get('validation_passed')})"
        )
        return final_state
