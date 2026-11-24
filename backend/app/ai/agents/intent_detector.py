import re
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.core.logging import logger

class TutorIntent(str, Enum):
    GREETING = "greeting"
    GENERAL_CONVERSATION = "general_conversation"
    EDUCATIONAL_QUESTION = "educational_question"
    FOLLOW_UP = "follow_up"
    LEARNING_ASSISTANCE = "learning_assistance"
    UNRELATED = "unrelated"

class IntentResult(BaseModel):
    intent: TutorIntent
    confidence: float
    contextualized_query: str
    action_type: Optional[str] = None  # e.g., "summary", "practice", "step_by_step", "example"

class IntentDetector:
    """Classifies student messages into intents before RAG retrieval."""

    GREETING_PATTERNS = [
        r"^(hi|hello|hey|heya|howdy|greetings|hola)\b",
        r"^good\s+(morning|afternoon|evening|day)\b",
        r"^welcome\b",
        r"^hi\s+(there|tutor|bot|ai)\b",
        r"^hello\s+(there|tutor|bot|ai)\b",
    ]

    GENERAL_CHAT_PATTERNS = [
        r"^(how\s+are\s+you|how's\s+it\s+going|how\s+do\s+you\s+do)\b",
        r"^(who\s+are\s+you|what\s+are\s+you|what\s+is\s+your\s+name|what\s+can\s+you\s+do)\b",
        r"^(thank\s+you|thanks|thx|thank\s+u|appreciate\s+it)\b",
        r"^(bye|goodbye|see\s+you|cya|good\s+night)\b",
        r"^(ok|okay|cool|great|awesome|understood|got\s+it|nice|perfect)\b",
    ]

    LEARNING_ASSISTANCE_PATTERNS = [
        (r"\b(summarize|summary|overview|recap)\b", "summary"),
        (r"\b(step\s*by\s*step|walkthrough|guide\s*me\s*through)\b", "step_by_step"),
        (r"\b(practice\s*questions?|quiz\s*me|test\s*my\s*understanding|test\s*me)\b", "practice"),
        (r"\b(real\s*world|practical|another)\s*examples?\b", "example"),
        (r"\b(compare|contrast|difference\s*between|versus|vs)\b", "comparison"),
        (r"\b(explain\s*this\s*code|debug|how\s*does\s*this\s*code\s*work)\b", "code_explanation"),
        (r"\b(explain\s*this\s*formula|derive|equation)\b", "formula_explanation"),
    ]

    FOLLOW_UP_INDICATORS = [
        r"\b(it|this|that|them|these|those)\b",
        r"\b(more\s*simply|simpler|in\s*simple\s*terms|like\s*i'm\s*five|eli5)\b",
        r"\b(another\s*example|one\s*more\s*example)\b",
        r"\b(why\s*is\s*(this|that|it)\s*used)\b",
        r"\b(the\s*(first|second|third|last|previous)\s*(point|one|part|step))\b",
        r"\b(what\s*about\s*(it|this|that))\b",
        r"\b(what\s*does\s*that\s*mean)\b",
        r"\b(can\s*you\s*elaborate)\b",
        r"\b(continue|go\s*on|tell\s*me\s*more)\b",
    ]

    UNRELATED_PATTERNS = [
        r"\b(weather|forecast|rain\s*today|temperature\s*in)\b",
        r"\b(who\s*won|who\s*is\s*winning|football|soccer|cricket|baseball|nba|nfl|superbowl|world\s*cup)\b",
        r"\b(recipe\s*for|how\s*to\s*cook|how\s*to\s*bake|bake\s*a\s*cake|chocolate\s*cake)\b",
        r"\b(stock\s*price|crypto|bitcoin|dogecoin)\b",
        r"\b(movie\s*review|celebrity|gossip|dating)\b",
    ]

    @classmethod
    def detect_intent(
        cls,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        course_title: Optional[str] = None,
    ) -> IntentResult:
        clean_msg = message.strip()
        lower_msg = clean_msg.lower()

        # 1. Check Greetings & Pleasantries
        is_greeting = any(re.search(pat, lower_msg) for pat in cls.GREETING_PATTERNS)
        is_chat = any(re.search(pat, lower_msg) for pat in cls.GENERAL_CHAT_PATTERNS)

        if (is_greeting or is_chat) and len(clean_msg.split()) <= 8:
            # If no technical concept query words are present, treat purely as conversational
            if not re.search(r"\b(what\s*is|how\s*does|explain|define|why\s*is|formula|algorithm|code|function|class)\b", lower_msg):
                chosen_intent = TutorIntent.GREETING if is_greeting else TutorIntent.GENERAL_CONVERSATION
                return IntentResult(
                    intent=chosen_intent,
                    confidence=0.98,
                    contextualized_query=clean_msg,
                    action_type="greeting" if is_greeting else "general_chat",
                )

        # 3. Check Explicit Unrelated Questions
        for pat in cls.UNRELATED_PATTERNS:
            if re.search(pat, lower_msg):
                return IntentResult(
                    intent=TutorIntent.UNRELATED,
                    confidence=0.92,
                    contextualized_query=clean_msg,
                    action_type="unrelated",
                )

        # 4. Check Follow-Up Questions (when conversation history exists)
        has_history = bool(history and len(history) > 0)
        is_followup = False
        action = None

        if has_history:
            # Check for follow-up pronoun cues or brevity
            for pat in cls.FOLLOW_UP_INDICATORS:
                if re.search(pat, lower_msg):
                    is_followup = True
                    break

            # Very short questions with history are often follow-ups (e.g., "Why?", "How come?", "Example?")
            if len(clean_msg.split()) <= 3 and not re.search(r"^(what\s*is|who\s*is|define)\b", lower_msg):
                is_followup = True

        if is_followup:
            # Contextualize query with previous topic
            contextualized = cls.contextualize_query(clean_msg, history)
            return IntentResult(
                intent=TutorIntent.FOLLOW_UP,
                confidence=0.88,
                contextualized_query=contextualized,
                action_type="follow_up",
            )

        # 5. Check Learning Assistance Requests
        for pat, act in cls.LEARNING_ASSISTANCE_PATTERNS:
            if re.search(pat, lower_msg):
                contextualized = cls.contextualize_query(clean_msg, history) if has_history else clean_msg
                return IntentResult(
                    intent=TutorIntent.LEARNING_ASSISTANCE,
                    confidence=0.90,
                    contextualized_query=contextualized,
                    action_type=act,
                )

        # 6. Default to Educational Question
        return IntentResult(
            intent=TutorIntent.EDUCATIONAL_QUESTION,
            confidence=0.85,
            contextualized_query=clean_msg,
            action_type="direct_question",
        )

    @classmethod
    def contextualize_query(cls, query: str, history: Optional[List[Dict[str, str]]]) -> str:
        """Resolves pronouns and context from history so retrieval finds the correct topic."""
        if not history:
            return query

        # Find the most recent user question that had conceptual content
        recent_questions = []
        for msg in reversed(history):
            content = msg.get("content", "").strip()
            role = msg.get("role", "")
            if role in ("user", "student") and len(content.split()) > 2:
                # Exclude pure greetings
                if not any(re.search(p, content.lower()) for p in cls.GREETING_PATTERNS):
                    recent_questions.append(content)
                    if len(recent_questions) >= 2:
                        break

        if not recent_questions:
            return query

        last_topic_q = recent_questions[0]
        # Clean question punctuation
        clean_topic = re.sub(r"[^\w\s]", "", last_topic_q).strip()

        # Combine prior topic with current follow-up
        contextualized = f"{clean_topic} : {query}"
        logger.debug(f"Contextualized query '{query}' -> '{contextualized}'")
        return contextualized

    @classmethod
    def get_conversational_response(
        cls,
        intent: TutorIntent,
        query: str,
        course_title: Optional[str] = None,
    ) -> str:
        """Produces instant, warm, natural responses for greetings and general chatter."""
        clean_title = course_title.strip() if course_title else "your enrolled course"
        lower = query.lower().strip()

        if intent == TutorIntent.GREETING:
            if re.search(r"good\s+morning", lower):
                return f"Good morning! I'm your AI tutor for **{clean_title}**. What concept or lesson would you like to explore today?"
            if re.search(r"good\s+evening", lower):
                return f"Good evening! Ready to dive into **{clean_title}**? Let me know what questions you have!"
            return (
                f"Hello! Welcome back. I'm your AI tutor for **{clean_title}**. "
                f"Ask me about any concept, formula, or code snippet from your learning materials and we'll break it down together!"
            )

        if intent == TutorIntent.GENERAL_CONVERSATION:
            if re.search(r"how\s+are\s+you", lower):
                return (
                    f"I'm doing well and fully ready to help you learn **{clean_title}**! "
                    f"Which topic would you like to review right now?"
                )
            if re.search(r"who\s+are\s+you|what\s+are\s+you", lower):
                return (
                    f"I am your dedicated **LearnForge AI Tutor** for **{clean_title}**. "
                    f"I explain complex topics, provide practical examples, and guide you using your uploaded study materials. "
                    f"What would you like to learn today?"
                )
            if re.search(r"thank|thx|appreciate", lower):
                return (
                    "You're very welcome! Keep up the great studying. "
                    "Whenever you have more questions or need another concept clarified, just ask!"
                )
            if re.search(r"bye|goodbye|see\s+you|good\s+night", lower):
                return "Goodbye! Great session today. Your progress is saved, so feel free to return whenever you're ready to continue learning!"
            if re.search(r"ok|cool|great|awesome|understood|got\s+it", lower):
                return "Excellent! Let me know if you'd like an example, a practice question, or if you're ready to move on to the next topic."

        if intent == TutorIntent.UNRELATED:
            return (
                f"I'm specifically focused on tutoring you in **{clean_title}** and your uploaded study materials. "
                f"While I cannot assist with outside inquiries like general weather or trivia, I'd love to help you master any "
                f"topic, definition, or practical problem in this course! What course concept would you like to discuss?"
            )

        return f"Hello! How can I assist you with **{clean_title}** today?"
