from typing import Dict, Any, List
from datetime import datetime


class SupervisorAgent:
    """
    Orchestrator agent responsible for:
    - Identifying workflow intent and validating preconditions
    - Selecting the target specialized worker agent
    - Validating agent outputs and deciding retries or follow-up enrichment
    - Recording structured multi-agent execution trace entries
    """

    VALID_WORKFLOWS = {
        "tutor_chat",
        "flashcard_generation",
        "quiz_generation",
        "assessment_review",
        "document_understanding",
        "resource_lookup",
    }

    @classmethod
    def plan_workflow(cls, state: Dict[str, Any]) -> Dict[str, Any]:
        workflow = state.get("workflow_type") or "tutor_chat"
        if workflow not in cls.VALID_WORKFLOWS:
            workflow = "tutor_chat"

        trace = list(state.get("trace") or [])
        trace.append({
            "node": "supervisor_plan",
            "workflow": workflow,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "planned",
        })

        # Validate minimum required arguments cleanly
        error = None
        if workflow == "tutor_chat" and not str(state.get("query", "")).strip():
            error = "Tutor query cannot be empty."
        elif workflow == "assessment_review" and not state.get("quiz_questions"):
            error = "Quiz questions are required for assessment review."

        return {
            **state,
            "workflow_type": workflow,
            "retry_count": int(state.get("retry_count", 0)),
            "max_retries": int(state.get("max_retries", 1)),
            "validation_passed": error is None,
            "error": error,
            "trace": trace,
        }

    @classmethod
    def route_to_agent(cls, state: Dict[str, Any]) -> str:
        if state.get("error"):
            return "error_handler"

        mapping = {
            "tutor_chat": "tutor_agent",
            "flashcard_generation": "flashcard_agent",
            "quiz_generation": "quiz_agent",
            "assessment_review": "assessment_agent",
            "document_understanding": "document_agent",
            "resource_lookup": "resource_agent",
        }
        return mapping.get(state.get("workflow_type", "tutor_chat"), "tutor_agent")

    @classmethod
    def validate_output(cls, state: Dict[str, Any]) -> Dict[str, Any]:
        workflow = state.get("workflow_type", "tutor_chat")
        output = state.get("generated_output") or {}
        trace = list(state.get("trace") or [])
        passed = True
        reason = "ok"

        if state.get("error"):
            passed = False
            reason = str(state["error"])
        elif workflow == "tutor_chat":
            if not str(output.get("answer", "")).strip():
                passed = False
                reason = "Empty tutor answer."
        elif workflow == "flashcard_generation":
            if not isinstance(output.get("cards"), list):
                passed = False
                reason = "Invalid flashcard list output."
        elif workflow == "quiz_generation":
            if not isinstance(output.get("questions"), list):
                passed = False
                reason = "Invalid quiz questions output."

        trace.append({
            "node": "supervisor_validate",
            "workflow": workflow,
            "passed": passed,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return {
            **state,
            "validation_passed": passed,
            "trace": trace,
        }

    @classmethod
    def decide_after_validation(cls, state: Dict[str, Any]) -> str:
        if not state.get("validation_passed", False):
            retry_count = int(state.get("retry_count", 0))
            max_retries = int(state.get("max_retries", 1))
            if retry_count < max_retries and not state.get("error"):
                return cls.route_to_agent(state)
            return "end"

        # Enrich educational tutor responses with ResourceAgent when citations/topic context exists
        if state.get("workflow_type") == "tutor_chat":
            out = state.get("generated_output") or {}
            intent = out.get("intent", "")
            if intent in ("educational_question", "follow_up", "learning_assistance") and not state.get("resources_attached"):
                return "resource_agent"

        return "end"
