"""Exercise and Assessment Generation Agent for LearnForge AI.

Builds grounded interactive practice exercises (concept-check MCQs, fill-in-the-blank,
topic-matched Coding Labs, realistic Debug Challenges, and non-CS scenario tasks) and
module/final assessments strictly connected to the current lesson & source text.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from app.ai.models.model_router import model_router
from app.core.logging import logger
from app.core.sanitizer import EducationalSanitizer


class ExerciseAgent:
    """Generates document- and lesson-grounded interactive exercises and assessments."""

    @classmethod
    async def generate_lesson_exercises(
        cls,
        topic_title: str,
        chapter_title: str,
        lesson_content: str,
        source_text: str = "",
        domain: str = "general",
        content_type: str = "theoretical",
        difficulty: str = "intermediate",
        key_takeaways: Optional[List[str]] = None,
        source_reference: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Generate 5-6 topic-relevant interactive exercises grounded in lesson & source text."""
        if not model_router.is_local_only() and lesson_content.strip():
            llm_exercises = await cls._generate_via_llm(
                topic_title=topic_title,
                chapter_title=chapter_title,
                lesson_content=lesson_content,
                source_text=source_text,
                domain=domain,
                content_type=content_type,
                difficulty=difficulty,
                source_reference=source_reference,
            )
            if llm_exercises:
                return llm_exercises

        return cls._build_grounded_exercises(
            topic_title=topic_title,
            chapter_title=chapter_title,
            lesson_content=lesson_content,
            source_text=source_text,
            domain=domain,
            content_type=content_type,
            difficulty=difficulty,
            key_takeaways=key_takeaways or [],
            source_reference=source_reference,
        )

    @classmethod
    async def _generate_via_llm(
        cls,
        topic_title: str,
        chapter_title: str,
        lesson_content: str,
        source_text: str,
        domain: str,
        content_type: str,
        difficulty: str,
        source_reference: Optional[str],
    ) -> List[Dict[str, Any]]:
        is_code = domain == "computer_science" or content_type == "programming" or "```python" in lesson_content
        prompt = (
            f"Create 5 high-quality interactive exercises STRICTLY testing the technical concepts in '{topic_title}' "
            f"(Module: '{chapter_title}', Source: {source_reference or chapter_title}, Difficulty: {difficulty}).\n\n"
            "STRICT RULES:\n"
            "- NEVER use learning objective sentences as MCQ answers.\n"
            "- Every distractor must be plausible and domain-related.\n"
            "- Include: 3 MCQs (concept understanding, scenario application, misconception check), 1 fill_blank, and "
            + ("1 coding lab (complete Python assertions)." if is_code else "1 mini_task (scenario analysis).")
            + "\nReturn ONLY valid JSON list of exercise objects.\n"
            f"\nLesson:\n{lesson_content[:2000]}\n\nSource:\n{source_text[:1200]}"
        )
        try:
            res = await model_router.generate(
                prompt=prompt,
                task_type="quiz_generation",
                temperature=0.25,
                max_tokens=1600,
                format="json",
                allow_local_fallback=False,
            )
            raw = (res.get("content") or "").strip()
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()
            parsed = json.loads(raw)
            items = parsed if isinstance(parsed, list) else parsed.get("exercises", [])
            cleaned: List[Dict[str, Any]] = []
            for idx, item in enumerate(items[:6]):
                if not isinstance(item, dict) or not item.get("prompt"):
                    continue
                cleaned.append({
                    "order_index": idx,
                    "exercise_type": str(item.get("exercise_type", "mcq")),
                    "title": str(item.get("title") or f"{topic_title} Practice {idx + 1}"),
                    "prompt": str(item.get("prompt")),
                    "starter_code": item.get("starter_code"),
                    "buggy_code": item.get("buggy_code"),
                    "options": item.get("options") or [],
                    "option_explanations": item.get("option_explanations") or [],
                    "correct_answer": str(item.get("correct_answer") or ""),
                    "expected_output": item.get("expected_output"),
                    "test_cases": item.get("test_cases") or [],
                    "hints": item.get("hints") or [f"Review Core Concepts of {topic_title}."],
                    "explanation": str(item.get("explanation") or ""),
                    "difficulty": difficulty,
                })
            if len(cleaned) >= 3:
                return cleaned
        except Exception as exc:
            logger.debug(f"LLM exercise generation skipped for '{topic_title}': {exc}")
        return []

    @classmethod
    def _build_grounded_exercises(
        cls,
        topic_title: str,
        chapter_title: str,
        lesson_content: str,
        source_text: str,
        domain: str,
        content_type: str,
        difficulty: str,
        key_takeaways: List[str],
        source_reference: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Build specific, non-generic exercises tailored directly to the lesson topic & source content."""
        combined = f"{lesson_content}\n\n{source_text}".strip()
        low_topic = f"{topic_title} {chapter_title}".lower()
        is_code = (
            domain == "computer_science"
            or content_type == "programming"
            or "```python" in lesson_content
            or any(k in combined.lower() for k in ("fastapi", "pydantic", "async ", "http", "endpoint", "def ", "python"))
        )

        ref_tag = f" *(Source: {source_reference})*" if source_reference else ""

        # 1-3. Topic-specific Concept / Scenario / Misconception MCQs
        mcqs = cls._build_topic_mcqs(topic_title, chapter_title, lesson_content, source_text, key_takeaways, difficulty, ref_tag)
        exercises: List[Dict[str, Any]] = []
        order = 0
        for q in mcqs:
            q["order_index"] = order
            exercises.append(q)
            order += 1

        # 4. Fill-in-the-blank from authentic technical declarations (NEVER learning objectives!)
        fill_ex = cls._build_fill_blank(topic_title, lesson_content, source_text, difficulty, ref_tag, order)
        exercises.append(fill_ex)
        order += 1

        # 5 & 6. Subject-aware coding + debugging labs (only when topic involves code/CS mechanics)
        if is_code:
            exercises.append(cls._build_coding_exercise(low_topic, topic_title, order, difficulty))
            order += 1
            exercises.append(cls._build_debugging_exercise(low_topic, topic_title, order, difficulty))
        else:
            exercises.append({
                "order_index": order,
                "exercise_type": "mini_task",
                "title": f"Scenario Analysis: {topic_title}",
                "prompt": (
                    f"Analyze a practical case from **{chapter_title}**: describe how **{topic_title}** "
                    f"operates step by step and explain one critical decision or failure mode.{ref_tag}"
                ),
                "correct_answer": topic_title.split()[0],
                "hints": [f"Connect core definitions of '{topic_title}' to a concrete real-world constraint."],
                "explanation": f"Complete responses trace exact steps from {topic_title} and identify a realistic trade-off.",
                "difficulty": difficulty,
            })

        return exercises

    @classmethod
    def _build_topic_mcqs(
        cls,
        topic_title: str,
        chapter_title: str,
        lesson_content: str,
        source_text: str,
        key_takeaways: List[str],
        difficulty: str,
        ref_tag: str,
    ) -> List[Dict[str, Any]]:
        low = f"{topic_title} {chapter_title}".lower()

        if any(k in low for k in ("http", "rest", "crud", "endpoint")):
            return [
                {
                    "exercise_type": "mcq",
                    "title": "Scenario: Selecting the Right HTTP Method",
                    "prompt": f"A client needs to retrieve a list of creatures from a FastAPI service without modifying server data. Which HTTP method and status code pair applies?{ref_tag}",
                    "options": [
                        "`GET /creatures` returning `200 OK`",
                        "`POST /creatures` returning `201 Created`",
                        "`PUT /creatures` returning `204 No Content`",
                        "`PATCH /creatures` returning `404 Not Found`",
                    ],
                    "option_explanations": [
                        "Correct: `GET` is used for safe read/retrieve operations and returns `200 OK` on success.",
                        "Incorrect: `POST` creates a new resource rather than reading existing ones.",
                        "Incorrect: `PUT` replaces an existing resource completely.",
                        "Incorrect: `PATCH` partially updates a resource, and `404` signals missing resource.",
                    ],
                    "correct_answer": "`GET /creatures` returning `200 OK`",
                    "hints": ["Map CRUD 'Read' to its corresponding HTTP verb and 2xx success code."],
                    "explanation": "In RESTful HTTP APIs, `GET` performs Read (`CRUD`) operations cleanly and returns a `2xx` status code such as `200`.",
                    "difficulty": difficulty,
                },
                {
                    "exercise_type": "mcq",
                    "title": "Concept Distinction: Partial Update vs Full Replacement",
                    "prompt": f"How does `PATCH` differ from `PUT` when updating a resource in a RESTful API?{ref_tag}",
                    "options": [
                        "`PATCH` modifies selected fields partially, whereas `PUT` replaces the resource completely",
                        "`PATCH` deletes the resource before recreating it synchronously",
                        "`PUT` is restricted strictly to static HTML responses",
                        "`PATCH` bypasses HTTP request headers and query parameters",
                    ],
                    "option_explanations": [
                        "Correct: `PUT` replaces a representation wholly, whereas `PATCH` applies a partial update.",
                        "Incorrect: Deleting and recreating would invalidate resource identity semantics.",
                        "Incorrect: `PUT` is a standard REST HTTP method for JSON and binary resources.",
                        "Incorrect: Every HTTP request carries headers and a URL path regardless of method.",
                    ],
                    "correct_answer": "`PATCH` modifies selected fields partially, whereas `PUT` replaces the resource completely",
                    "hints": ["Compare complete modification vs partial modification in HTTP verbs."],
                    "explanation": "REST maps `PUT` to replacing an entire resource and `PATCH` to updating specific fields.",
                    "difficulty": difficulty,
                },
                {
                    "exercise_type": "mcq",
                    "title": "Error Diagnosis: HTTP Status Code Semantics",
                    "prompt": f"A client requests `/creatures/unicorn` which does not exist in the database. Which HTTP status family communicates a client-side missing-resource error?{ref_tag}",
                    "options": [
                        "`4xx` client error (specifically `404 Not Found`)",
                        "`2xx` success (e.g. `200 OK` with an empty string)",
                        "`3xx` redirection indicating permanent URL move",
                        "`5xx` server crash indicating an unhandled syntax bug",
                    ],
                    "option_explanations": [
                        "Correct: `4xx` codes signal client errors such as invalid input or nonexistent resource paths (`404`).",
                        "Incorrect: Returning `200` for missing resources hides errors from clients.",
                        "Incorrect: `3xx` instructs the client to follow a redirect location.",
                        "Incorrect: `5xx` indicates an internal server failure, not a nonexistent path.",
                    ],
                    "correct_answer": "`4xx` client error (specifically `404 Not Found`)",
                    "hints": ["Distinguish `4xx` client errors from `5xx` server errors."],
                    "explanation": "`200s` indicate success, `300s` redirection, `400s` client error (like `404`), and `500s` server errors.",
                    "difficulty": difficulty,
                },
            ]

        if any(k in low for k in ("service", "api", "rpc", "messaging", "kinds of api")):
            return [
                {
                    "exercise_type": "mcq",
                    "title": "Messaging Patterns: Pub-Sub vs Queues",
                    "prompt": f"When handing off a slow background task (such as sending a confirmation email) to a pool of worker processes so that only ONE worker processes each job, which messaging pattern applies?{ref_tag}",
                    "options": [
                        "Message Queue (one worker in a pool claims and handles each message)",
                        "Publish-Subscribe (every subscriber receives and repeats the exact same email)",
                        "In-process Library API function call inside the synchronous HTTP thread",
                        "Static HTML template rendering",
                    ],
                    "option_explanations": [
                        "Correct: In a Queue, only one subscriber from a worker pool grabs and processes each message.",
                        "Incorrect: Pub-Sub broadcasts messages to all matching subscribers.",
                        "Incorrect: An in-process library call runs synchronously instead of offloading across workers.",
                        "Incorrect: HTML is for display, not asynchronous worker dispatch.",
                    ],
                    "correct_answer": "Message Queue (one worker in a pool claims and handles each message)",
                    "hints": ["Compare `Publish-Subscribe` (broadcast) vs `Queues` (shared worker pool)."],
                    "explanation": "Queues resemble pub-sub for decoupling, but each queued task is consumed once by a single worker from the pool.",
                    "difficulty": difficulty,
                },
                {
                    "exercise_type": "mcq",
                    "title": "API Architecture: Contract Between Frontend & Backend",
                    "prompt": f"Why is an API described as a 'contract' between a frontend UI and a backend web service?{ref_tag}",
                    "options": [
                        "It strictly defines expected endpoints, input parameters, and response structures so both sides interoperate cleanly",
                        "It embeds database table schemas directly inside client JavaScript variables",
                        "It eliminates the HTTP protocol in favor of direct disk file sharing",
                        "It forces backend and frontend codebases to be written in the same language",
                    ],
                    "option_explanations": [
                        "Correct: Explicit API contracts let specialized frontend and backend teams evolve independently.",
                        "Incorrect: APIs abstract storage details rather than exposing raw DB tables.",
                        "Incorrect: Web APIs communicate across networks over HTTP or RPC.",
                        "Incorrect: JSON and HTTP allow Python backends to serve JavaScript, Swift, or Kotlin clients.",
                    ],
                    "correct_answer": "It strictly defines expected endpoints, input parameters, and response structures so both sides interoperate cleanly",
                    "hints": ["Think about why specialized frontend and backend developers rely on explicit contracts."],
                    "explanation": "Just like a database schema enforces data structure, an API defines predictable communication contracts across network boundaries.",
                    "difficulty": difficulty,
                },
                {
                    "exercise_type": "mcq",
                    "title": "Concept Check: Library APIs vs Network Services",
                    "prompt": f"Which key distinction separates a local Library API from a remote Service API (such as RPC or HTTP)?{ref_tag}",
                    "options": [
                        "Library APIs invoke functions directly in the same program's memory, while Service APIs exchange messages over a network",
                        "Library APIs always require JSON payloads whereas Service APIs prohibit JSON",
                        "Service APIs cannot return structured error codes",
                        "Library APIs only work on remote cloud servers",
                    ],
                    "option_explanations": [
                        "Correct: Library calls happen in-process via language calls; service calls cross network boundaries.",
                        "Incorrect: Local library functions receive native language arguments directly.",
                        "Incorrect: Service APIs standardize error signaling using codes such as HTTP 4xx/5xx.",
                        "Incorrect: Library APIs are imported locally inside the same runtime.",
                    ],
                    "correct_answer": "Library APIs invoke functions directly in the same program's memory, while Service APIs exchange messages over a network",
                    "hints": ["Check how functions are invoked locally vs over RPC/HTTP."],
                    "explanation": "Calling a Python package function stays inside process memory; calling a web service crosses the network via a defined protocol.",
                    "difficulty": difficulty,
                },
            ]

        if any(k in low for k in ("json", "graphql", "data format")):
            return [
                {
                    "exercise_type": "mcq",
                    "title": "Data Exchange: Why JSON Replaced XML for Web APIs",
                    "prompt": f"Why is JavaScript Object Notation (JSON) favored over plain text or verbose XML for RESTful APIs?{ref_tag}",
                    "options": [
                        "JSON encodes structured lists and key-value objects cleanly in a lightweight text format readable by Python and JavaScript alike",
                        "JSON automatically encrypts passwords without HTTPS",
                        "XML cannot represent hierarchical objects or nested lists",
                        "JSON only works when stored inside relational SQL tables",
                    ],
                    "option_explanations": [
                        "Correct: JSON maps naturally to dictionaries/lists across languages with low overhead.",
                        "Incorrect: Transport security comes from HTTPS/TLS, not JSON syntax.",
                        "Incorrect: XML represents hierarchies too, but with much heavier tag verbosity.",
                        "Incorrect: JSON is a serialization wire format independent of SQL storage.",
                    ],
                    "correct_answer": "JSON encodes structured lists and key-value objects cleanly in a lightweight text format readable by Python and JavaScript alike",
                    "hints": ["Compare plain ASCII text / XML against JSON's Python-like structures."],
                    "explanation": "JSON makes lists, nested dictionaries, strings, and numbers trivial to serialize across heterogeneous web clients and Python servers.",
                    "difficulty": difficulty,
                },
                {
                    "exercise_type": "mcq",
                    "title": "Scenario: REST vs JSON:API vs GraphQL",
                    "prompt": f"A mobile client needs to request complex, custom nested fields in one flexible query because fixed REST endpoints return either too much or too little data. Which technology specifically targets this problem?{ref_tag}",
                    "options": [
                        "GraphQL (Graph Query Language)",
                        "Plain HTML `<img>` tags",
                        "Local Python synchronous loops",
                        "Raw CSV text exports",
                    ],
                    "option_explanations": [
                        "Correct: Meta designed GraphQL so clients specify exact nested data queries when rigid REST endpoints feel cumbersome.",
                        "Incorrect: HTML displays presentation markup, not flexible API data queries.",
                        "Incorrect: Synchronous loops affect execution concurrency, not query schema.",
                        "Incorrect: CSV represents flat tabular rows rather than hierarchical queries.",
                    ],
                    "correct_answer": "GraphQL (Graph Query Language)",
                    "hints": ["Recall why Meta designed Graph Query Language as an alternative to REST endpoints."],
                    "explanation": "GraphQL lets clients declare exact shapes of nested data, whereas JSON:API standardizes REST response envelopes.",
                    "difficulty": difficulty,
                },
                {
                    "exercise_type": "mcq",
                    "title": "Convention Check: JSON:API Role",
                    "prompt": f"When building a large REST API, what benefit does a convention such as JSON:API provide?{ref_tag}",
                    "options": [
                        "Standardized rules for resource envelopes, pagination, relationships, and errors across teams",
                        "Automatic GPU acceleration for SQL joins",
                        "Replacing HTTP status codes with custom TCP ports",
                        "Eliminating the need for JSON serialization",
                    ],
                    "option_explanations": [
                        "Correct: JSON:API gives teams shared structural conventions so they don't argue over ad-hoc payload shapes.",
                        "Incorrect: JSON:API is a payload formatting specification, not a compute engine.",
                        "Incorrect: JSON:API works directly on top of standard HTTP.",
                        "Incorrect: JSON:API specifically standardizes JSON payloads.",
                    ],
                    "correct_answer": "Standardized rules for resource envelopes, pagination, relationships, and errors across teams",
                    "hints": ["Consider why teams adopt JSON:API conventions when agreeing on response shapes."],
                    "explanation": "JSON:API resolves team debates over linking, sorting, filtering, and error formatting inside JSON responses.",
                    "difficulty": difficulty,
                },
            ]

        if any(k in low for k in ("async", "concurren", "starlette", "event loop")):
            return [
                {
                    "exercise_type": "mcq",
                    "title": "Performance Metrics: Latency vs Throughput",
                    "prompt": f"How do **latency** and **throughput** differ when measuring a web service's efficiency?{ref_tag}",
                    "options": [
                        "Latency is upfront wait time per request; throughput is the number of bytes or requests served per second",
                        "Latency measures total storage size; throughput measures password strength",
                        "Increasing throughput always forces latency per request to approach infinity",
                        "Throughput only applies to frontend CSS rendering",
                    ],
                    "option_explanations": [
                        "Correct: Low latency reduces how long each caller waits; high throughput increases aggregate volume per second.",
                        "Incorrect: Latency is elapsed time, and throughput is rate per second.",
                        "Incorrect: Asynchronous I/O can simultaneously reduce average wait contention and increase throughput.",
                        "Incorrect: Both metrics describe backend service request performance.",
                    ],
                    "correct_answer": "Latency is upfront wait time per request; throughput is the number of bytes or requests served per second",
                    "hints": ["Check the exact definitions of Latency vs Throughput in Chapter 1 / Chapter 4."],
                    "explanation": "FastAPI's async support boosts throughput under concurrent I/O waits while keeping per-request latency low.",
                    "difficulty": difficulty,
                },
                {
                    "exercise_type": "mcq",
                    "title": "Pitfall Check: CPU Work Inside Async Event Loops",
                    "prompt": f"What happens if an `async def` FastAPI endpoint runs heavy CPU-intensive number crunching synchronously on the main event loop?{ref_tag}",
                    "options": [
                        "It stalls the event loop and delays all other concurrent async requests",
                        "FastAPI automatically compiles the loop into parallel WebAssembly threads",
                        "Starlette converts the CPU work into non-blocking SQL I/O",
                        "Concurrent callers finish faster because async skips CPU execution",
                    ],
                    "option_explanations": [
                        "Correct: Cooperative async relies on yielding at `await`; unyielding CPU loops block the single event loop.",
                        "Incorrect: Python async endpoints share one event loop unless offloaded to worker threads/processes.",
                        "Incorrect: Pure CPU computation has no automatic async yield point.",
                        "Incorrect: Blocking the event loop degrades concurrency across active connections.",
                    ],
                    "correct_answer": "It stalls the event loop and delays all other concurrent async requests",
                    "hints": ["Recall why async processing isn't magic for CPU-bound tasks."],
                    "explanation": "Async excels during network/DB I/O waits (`await`); CPU-heavy tasks should be delegated to thread/process pools.",
                    "difficulty": difficulty,
                },
                {
                    "exercise_type": "mcq",
                    "title": "Concurrency Architecture: Synchronous vs Async",
                    "prompt": f"When an endpoint fetches data from an external HTTP service cleanly using an async client and `await`, why does FastAPI handle more connections efficiently?{ref_tag}",
                    "options": [
                        "The event loop pauses that coroutine during the network wait and serves other requests in the meantime",
                        "Each HTTP request opens a new database server instance",
                        "`await` disables error handling across Starlette routes",
                        "Asynchronous execution skips TCP network round trips",
                    ],
                    "option_explanations": [
                        "Correct: Cooperative yielding lets one worker interleave many concurrent I/O waits.",
                        "Incorrect: Database servers remain shared pools; only coroutine execution yields.",
                        "Incorrect: Exception propagation works normally across `await` boundaries.",
                        "Incorrect: Network requests still happen; idle wait time is reclaimed for other tasks.",
                    ],
                    "correct_answer": "The event loop pauses that coroutine during the network wait and serves other requests in the meantime",
                    "hints": ["Think about what the event loop does between sending a DB query and receiving its response."],
                    "explanation": "Non-blocking `async`/`await` reclaims idle I/O wait time so one server process scales across many connections.",
                    "difficulty": difficulty,
                },
            ]

        if any(k in low for k in ("layer", "service layer", "data layer", "web layer")):
            return [
                {
                    "exercise_type": "mcq",
                    "title": "Architecture: Separation of Responsibilities",
                    "prompt": f"In a three-layer FastAPI application (**Web Layer**, **Service Layer**, **Data Layer**), which layer should convert HTTP headers, query params, and return status codes?{ref_tag}",
                    "options": [
                        "The Web Layer (keeping HTTP transport separate from business rules and storage)",
                        "The Data Layer directly inside SQL query functions",
                        "The Database engine itself",
                        "The Frontend CSS stylesheet",
                    ],
                    "option_explanations": [
                        "Correct: The Web Layer handles HTTP request parsing, status codes, and response formatting.",
                        "Incorrect: Data modules should stay decoupled from HTTP status codes or FastAPI routers.",
                        "Incorrect: Databases execute persistence operations, not HTTP transport.",
                        "Incorrect: CSS controls presentation on the client.",
                    ],
                    "correct_answer": "The Web Layer (keeping HTTP transport separate from business rules and storage)",
                    "hints": ["Separate HTTP concerns (Web) from domain rules (Service) and storage (Data)."],
                    "explanation": "Layering hides database internals from HTTP endpoints and lets you test business logic independently.",
                    "difficulty": difficulty,
                },
                {
                    "exercise_type": "mcq",
                    "title": "Design Flaw Check: Bypassing the Service Layer",
                    "prompt": f"What maintenance problem arises if FastAPI route functions execute raw SQL database calls directly inside Web endpoints?{ref_tag}",
                    "options": [
                        "HTTP routing, business logic, and SQL details become tightly coupled, breaking information hiding",
                        "Python refuses to execute SQL inside `async def` functions",
                        "Clients lose access to GET requests",
                        "JSON dictionaries stop serializing strings",
                    ],
                    "option_explanations": [
                        "Correct: Tightly coupling routes to SQL prevents swapping storage backends or reusing business logic cleanly.",
                        "Incorrect: Python does not prohibit it syntactically, which is why architectural discipline matters.",
                        "Incorrect: GET requests still function, though the code becomes brittle.",
                        "Incorrect: JSON serialization works regardless, unless raw DB tuples leak directly.",
                    ],
                    "correct_answer": "HTTP routing, business logic, and SQL details become tightly coupled, breaking information hiding",
                    "hints": ["Consider what happens when changing from SQLite to PostgreSQL or adding CLI access to business logic."],
                    "explanation": "Delegating from Web -> Service -> Data preserves clean boundaries and testable models.",
                    "difficulty": difficulty,
                },
                {
                    "exercise_type": "mcq",
                    "title": "Concept Check: Role of Shared Data Models",
                    "prompt": f"Why are shared domain **Models** passed between Web, Service, and Data layers?{ref_tag}",
                    "options": [
                        "They provide a consistent, typed data contract across every architectural tier",
                        "They replace HTTP routing tables entirely",
                        "They eliminate all database queries",
                        "They restrict the API to plain unformatted ASCII strings",
                    ],
                    "option_explanations": [
                        "Correct: Shared typed models standardize payloads cleanly from storage to API response.",
                        "Incorrect: Routers still map URL paths to handlers.",
                        "Incorrect: Data layer queries populate or store model instances.",
                        "Incorrect: Structured models serialize cleanly into rich JSON objects.",
                    ],
                    "correct_answer": "They provide a consistent, typed data contract across every architectural tier",
                    "hints": ["Think about how data travels cleanly from Database -> Data -> Service -> Web."],
                    "explanation": "Models define clear shapes so Web, Service, and Data modules pass structured objects safely.",
                    "difficulty": difficulty,
                },
            ]

        # Dynamic fact-grounded builder for all remaining chapters/topics (Pydantic, Dependencies, Auth, Testing, Non-CS domains)
        facts = cls._extract_factual_claims(lesson_content, source_text)
        terms = cls._extract_key_terms(lesson_content, topic_title)
        t_primary = terms[0] if terms else topic_title
        t_secondary = terms[1] if len(terms) > 1 else chapter_title
        fact_1 = facts[0] if facts else f"{topic_title} standardizes explicit contracts and modular separation within {chapter_title}."
        fact_2 = facts[1] if len(facts) > 1 else f"Explicit validation in {t_primary} prevents runtime type mismatches across boundaries."
        fact_3 = facts[2] if len(facts) > 2 else f"Neglecting boundary validation when using {t_primary} causes subtle integration failures."

        return [
            {
                "exercise_type": "mcq",
                "title": f"Core Mechanism: {t_primary}",
                "prompt": f"In the context of **{topic_title}** ({chapter_title}), what is the primary technical purpose of **{t_primary}**?{ref_tag}",
                "options": [
                    cls._concise(fact_1),
                    f"To merge presentation markup directly into raw persistence tables",
                    f"To disable all validation checks when inputs cross module boundaries",
                    f"To replace all modular abstractions with duplicated inline globals",
                ],
                "option_explanations": [
                    f"Correct: Directly reflects how {t_primary} functions in {topic_title}.",
                    "Incorrect: Clean architecture separates presentation from persistence.",
                    "Incorrect: Explicit boundary validation prevents invalid states.",
                    "Incorrect: Modular abstractions avoid brittle duplication.",
                ],
                "correct_answer": cls._concise(fact_1),
                "hints": [f"Review how '{t_primary}' is defined in Core Concepts of {topic_title}."],
                "explanation": fact_1,
                "difficulty": difficulty,
            },
            {
                "exercise_type": "mcq",
                "title": f"Applied Scenario: {topic_title}",
                "prompt": f"When integrating **{t_primary}** with **{t_secondary}** in production workflows, which practice ensures reliable behavior?{ref_tag}",
                "options": [
                    cls._concise(fact_2),
                    "Rely on unvalidated raw dictionaries without explicit schema contracts",
                    "Swallow errors silently so callers receive HTTP 200 on invalid states",
                    "Coupling storage drivers directly to client UI elements",
                ],
                "option_explanations": [
                    "Correct: Aligns directly with the worked example and architectural guidance in this lesson.",
                    "Incorrect: Unvalidated data silently propagates bugs downstream.",
                    "Incorrect: Failing fast with accurate diagnostics protects callers.",
                    "Incorrect: Direct UI-to-storage coupling breaks maintainability.",
                ],
                "correct_answer": cls._concise(fact_2),
                "hints": [f"Check Worked Example and Real-World Application for {topic_title}."],
                "explanation": fact_2,
                "difficulty": difficulty,
            },
            {
                "exercise_type": "mcq",
                "title": f"Error Prevention: {topic_title}",
                "prompt": f"Which oversight most commonly leads to bugs when implementing **{topic_title}**?{ref_tag}",
                "options": [
                    cls._concise(fact_3),
                    "Separating responsibilities into clean helper modules",
                    "Validating edge inputs before mutating state",
                    "Returning clear status feedback on malformed inputs",
                ],
                "option_explanations": [
                    "Correct: Highlights a key pitfall covered in Common Mistakes.",
                    "Incorrect: Modular separation reduces bugs.",
                    "Incorrect: Early validation is a best practice, not a bug cause.",
                    "Incorrect: Clear feedback helps callers diagnose invalid requests.",
                ],
                "correct_answer": cls._concise(fact_3),
                "hints": ["Look at Common Mistakes in this lesson."],
                "explanation": fact_3,
                "difficulty": difficulty,
            },
        ]

    @classmethod
    def _build_fill_blank(
        cls,
        topic_title: str,
        lesson_content: str,
        source_text: str,
        difficulty: str,
        ref_tag: str,
        order_index: int,
    ) -> Dict[str, Any]:
        low = topic_title.lower()
        presets = [
            ("http", "A RESTful web service pairs each resource URL with an HTTP ____ (such as GET, POST, PUT, PATCH, or DELETE).", "method", "HTTP methods (verbs) specify the CRUD operation performed on a URL resource."),
            ("rest", "Because REST APIs are ____, each request carries all context needed without relying on prior server session memory.", "stateless", "Statelessness lets servers scale horizontally without pinned session affinity."),
            ("json", "Unlike verbose XML, ____ encodes lists and key-value objects in a lightweight wire format familiar to Python and JavaScript.", "JSON", "JavaScript Object Notation (JSON) is the dominant structured payload format for modern REST APIs."),
            ("graphql", "____ allows clients to specify exact nested fields in a query instead of accepting fixed REST response shapes.", "GraphQL", "Facebook/Meta created GraphQL to solve over-fetching and under-fetching across REST endpoints."),
            ("service", "An API acts as a formal ____ between software components, specifying protocols, inputs, and response structures.", "contract", "Defining an explicit API contract keeps frontend and backend evolution decoupled."),
            ("concurren", "Asynchronous `async`/`await` execution boosts ____ (bytes or requests per second) when waiting on I/O.", "throughput", "While latency is upfront wait time, throughput measures sustained volume per second."),
            ("async", "Running heavy CPU-bound loops inside a single-threaded event loop blocks ____ execution across requests.", "asynchronous", "Event loops rely on cooperative `await` yields rather than preemptive CPU threading."),
            ("layer", "Separating Web, Service, and Data components enforces information ____ so storage changes do not break HTTP routes.", "hiding", "Information hiding isolates internal implementation details behind layer interfaces."),
            ("pydantic", "FastAPI relies on Python type hints and ____ models to validate incoming JSON request payloads automatically.", "Pydantic", "Pydantic parses, coerces, and raises clear 422 errors on invalid request schemas."),
        ]
        for kw, template, ans, exp in presets:
            if kw in low:
                return {
                    "order_index": order_index,
                    "exercise_type": "fill_blank",
                    "title": f"Key Concept Completion: {topic_title}",
                    "prompt": f"{template}{ref_tag}",
                    "correct_answer": ans,
                    "hints": [f"Starts with '{ans[0]}', {len(ans)} characters long."],
                    "explanation": exp,
                    "difficulty": difficulty,
                }

        # Generic factual declarative sentence fallback (explicitly excludes Learning Objectives / headings!)
        facts = cls._extract_factual_claims(lesson_content, source_text)
        terms = cls._extract_key_terms(lesson_content, topic_title)
        for term in terms:
            if " " not in term and 4 <= len(term) <= 22:
                for sentence in facts:
                    if re.search(rf"\b{re.escape(term)}\b", sentence, re.IGNORECASE):
                        blanked = re.sub(rf"\b{re.escape(term)}\b", "____", sentence, count=1, flags=re.IGNORECASE)
                        return {
                            "order_index": order_index,
                            "exercise_type": "fill_blank",
                            "title": f"Technical Recall: {topic_title}",
                            "prompt": f"Complete the technical statement:{ref_tag}\n\n> {blanked}",
                            "correct_answer": term,
                            "hints": [f"Think of the core term discussed in {topic_title} ({len(term)} chars, starts with '{term[0]}')."],
                            "explanation": f"The missing term is **{term}**, a key mechanism in {topic_title}.",
                            "difficulty": difficulty,
                        }

        ans = terms[0].split()[0] if terms else "contract"
        return {
            "order_index": order_index,
            "exercise_type": "fill_blank",
            "title": f"Technical Recall: {topic_title}",
            "prompt": f"Complete the statement: Clear system boundaries in **{topic_title}** depend on enforcing an explicit ____ between components.{ref_tag}",
            "correct_answer": "contract",
            "hints": ["Think of the agreement specifying valid inputs and outputs (8 letters)."],
            "explanation": "An explicit contract defines what enters and leaves a component cleanly.",
            "difficulty": difficulty,
        }

    @classmethod
    def _build_coding_exercise(
        cls,
        low: str,
        topic_title: str,
        order_index: int,
        difficulty: str,
    ) -> Dict[str, Any]:
        """Return a topic-authentic Python coding lab evaluated in the isolated subprocess sandbox."""
        if any(k in low for k in ("http", "rest", "crud", "endpoint")):
            return {
                "order_index": order_index,
                "exercise_type": "coding",
                "title": f"Coding Lab: REST Resource Dispatcher ({topic_title})",
                "prompt": (
                    "Implement `handle_creature_request(method, creatures, name=None, payload=None)` handling REST CRUD semantics:\n"
                    "- `'GET'`: if `name` is given, return `(200, creatures[name])` if found else `(404, {'error': 'Not Found'})`; otherwise return `(200, list(creatures.values()))`.\n"
                    "- `'POST'`: insert `payload['name']` and return `(201, payload)` (or `(400, {'error': 'Missing name'})` if missing).\n"
                    "- `'DELETE'`: remove `name` and return `(200, {'deleted': name})` if present else `(404, {'error': 'Not Found'})`."
                ),
                "starter_code": (
                    "def handle_creature_request(method, creatures, name=None, payload=None):\n"
                    "    m = method.upper()\n"
                    "    # TODO: Handle GET, POST, DELETE returning (status_code, data)\n"
                    "    pass\n"
                ),
                "expected_output": "(201, {'name': 'Yeti'})",
                "test_cases": [
                    {
                        "description": "GET existing returns 200 and missing returns 404",
                        "assert_code": (
                            "store = {'yeti': {'name': 'yeti', 'country': 'CN'}}\n"
                            "assert handle_creature_request('GET', store, 'yeti')[0] == 200\n"
                            "assert handle_creature_request('GET', store, 'dragon')[0] == 404"
                        ),
                    },
                    {
                        "description": "POST creates resource with 201 status",
                        "assert_code": (
                            "store = {}\n"
                            "code, body = handle_creature_request('POST', store, payload={'name': 'bigfoot'})\n"
                            "assert code == 201 and 'bigfoot' in store"
                        ),
                    },
                    {
                        "description": "DELETE removes existing resource",
                        "assert_code": (
                            "store = {'nessie': {'name': 'nessie'}}\n"
                            "code, _ = handle_creature_request('DELETE', store, 'nessie')\n"
                            "assert code == 200 and 'nessie' not in store"
                        ),
                    },
                ],
                "hints": [
                    "Check `if m == 'GET':`, `elif m == 'POST':`, `elif m == 'DELETE':`.",
                    "On `POST`, verify `payload` is a dict containing `'name'`, save `creatures[payload['name']] = payload`, and return `(201, payload)`.",
                ],
                "explanation": "Mapping HTTP verbs to CRUD operations with exact 200/201/400/404 status codes is the core of RESTful route design.",
                "difficulty": difficulty,
            }

        if any(k in low for k in ("json", "graphql", "data format")):
            return {
                "order_index": order_index,
                "exercise_type": "coding",
                "title": f"Coding Lab: REST vs JSON:API & GraphQL Field Selector",
                "prompt": (
                    "Implement `format_api_payload(item, fields=None, use_jsonapi=False)`:\n"
                    "- When `fields` is provided (simulating GraphQL field selection), filter `item` to only requested keys present in `item`.\n"
                    "- When `use_jsonapi=True`, wrap the filtered dictionary in `{'data': {'type': 'creature', 'attributes': filtered}}`."
                ),
                "starter_code": (
                    "def format_api_payload(item, fields=None, use_jsonapi=False):\n"
                    "    # TODO: Filter fields when specified and optionally wrap in JSON:API envelope\n"
                    "    pass\n"
                ),
                "expected_output": "{'data': {'type': 'creature', 'attributes': {'name': 'Yeti'}}}",
                "test_cases": [
                    {
                        "description": "Selects requested fields cleanly",
                        "assert_code": "assert format_api_payload({'name': 'Yeti', 'country': 'CN'}, fields=['name']) == {'name': 'Yeti'}",
                    },
                    {
                        "description": "Wraps payload in JSON:API envelope when use_jsonapi=True",
                        "assert_code": (
                            "out = format_api_payload({'name': 'Yeti'}, use_jsonapi=True)\n"
                            "assert out == {'data': {'type': 'creature', 'attributes': {'name': 'Yeti'}}}"
                        ),
                    },
                ],
                "hints": [
                    "Use `{k: item[k] for k in fields if k in item}` when `fields` is not None.",
                    "If `use_jsonapi`, return `{'data': {'type': 'creature', 'attributes': filtered}}`.",
                ],
                "explanation": "GraphQL avoids over-fetching via explicit field selection, while JSON:API standardizes the top-level `'data'`/`'attributes'` wrapper.",
                "difficulty": difficulty,
            }

        if any(k in low for k in ("layer", "web layer", "service layer", "data layer")):
            return {
                "order_index": order_index,
                "exercise_type": "coding",
                "title": f"Coding Lab: Web -> Service -> Data Layer Flow",
                "prompt": (
                    "Implement `service_get_creature(name, data_fetch_fn)` and `web_endpoint(name, service_fn)` demonstrating clean layer boundaries:\n"
                    "- `service_get_creature` normalizes `name.strip().lower()` and delegates lookup to `data_fetch_fn(key)`.\n"
                    "- `web_endpoint` returns `{'status': 200, 'body': record}` if found, or `{'status': 404, 'body': {'error': 'Not Found'}}` when `service_fn` returns `None`."
                ),
                "starter_code": (
                    "def service_get_creature(name, data_fetch_fn):\n"
                    "    # Normalize name and call data_fetch_fn without HTTP coupling\n"
                    "    pass\n\n"
                    "def web_endpoint(name, service_fn):\n"
                    "    # Call service_fn and map result to HTTP status 200 or 404\n"
                    "    pass\n"
                ),
                "expected_output": "{'status': 200, 'body': {'name': 'yeti'}}",
                "test_cases": [
                    {
                        "description": "Service layer normalizes key and delegates cleanly",
                        "assert_code": "assert service_get_creature(' Yeti ', lambda k: {'name': k} if k == 'yeti' else None) == {'name': 'yeti'}",
                    },
                    {
                        "description": "Web layer wraps service output with HTTP 200/404",
                        "assert_code": (
                            "assert web_endpoint('yeti', lambda n: {'name': 'yeti'}) == {'status': 200, 'body': {'name': 'yeti'}}\n"
                            "assert web_endpoint('x', lambda n: None)['status'] == 404"
                        ),
                    },
                ],
                "hints": [
                    "Inside `service_get_creature`, compute `key = (name or '').strip().lower()`.",
                    "Keep status codes purely inside `web_endpoint`, never inside `service_get_creature`.",
                ],
                "explanation": "Keeping normalization/rules in Service and HTTP status formatting in Web decouples transport from domain logic.",
                "difficulty": difficulty,
            }

        if any(k in low for k in ("async", "concurren", "starlette")):
            return {
                "order_index": order_index,
                "exercise_type": "coding",
                "title": f"Coding Lab: Async I/O vs Blocking Comparison",
                "prompt": (
                    "Implement `estimate_wait_ms(task_durations_ms, is_async)`:\n"
                    "- For synchronous execution (`is_async=False`), requests wait sequentially (`sum(task_durations_ms)`).\n"
                    "- For ideal non-blocking async I/O (`is_async=True`), I/O waits overlap (`max(task_durations_ms, default=0)`)."
                ),
                "starter_code": (
                    "def estimate_wait_ms(task_durations_ms, is_async):\n"
                    "    # Return total wait time (sum for sync, max for concurrent async I/O)\n"
                    "    pass\n"
                ),
                "expected_output": "120",
                "test_cases": [
                    {
                        "description": "Sequential sync sums all I/O wait durations",
                        "assert_code": "assert estimate_wait_ms([100, 120, 80], False) == 300",
                    },
                    {
                        "description": "Concurrent async I/O overlaps wait durations",
                        "assert_code": "assert estimate_wait_ms([100, 120, 80], True) == 120",
                    },
                    {
                        "description": "Empty task list returns 0",
                        "assert_code": "assert estimate_wait_ms([], True) == 0",
                    },
                ],
                "hints": ["Use `if not task_durations_ms: return 0` first, then `max(...) if is_async else sum(...)`."],
                "explanation": "Asynchronous concurrency reduces total wait time during multiple overlapping I/O calls cleanly.",
                "difficulty": difficulty,
            }

        if any(k in low for k in ("pydantic", "model", "type hint")):
            return {
                "order_index": order_index,
                "exercise_type": "coding",
                "title": f"Coding Lab: Typed Model Validator ({topic_title})",
                "prompt": (
                    "Implement `parse_creature(payload)` that validates `payload` has non-empty strings `'name'` and `'country'`, "
                    "sets optional `'aka'` defaulting to `''`, and raises `ValueError` with a descriptive message if missing or non-string."
                ),
                "starter_code": (
                    "def parse_creature(payload):\n"
                    "    # Validate 'name' and 'country' are non-empty str; default 'aka' to ''\n"
                    "    pass\n"
                ),
                "expected_output": "{'name': 'Yeti', 'country': 'CN', 'aka': ''}",
                "test_cases": [
                    {
                        "description": "Accepts valid payload and defaults aka",
                        "assert_code": "assert parse_creature({'name': 'Yeti', 'country': 'CN'}) == {'name': 'Yeti', 'country': 'CN', 'aka': ''}",
                    },
                    {
                        "description": "Raises ValueError on invalid types or blank fields",
                        "assert_code": (
                            "try:\n    parse_creature({'name': 123, 'country': 'CN'})\n    assert False, 'Expected ValueError'\nexcept ValueError:\n    pass"
                        ),
                    },
                ],
                "hints": ["Check `isinstance(val, str) and val.strip()` for both `'name'` and `'country'`."],
                "explanation": "Type validation libraries like Pydantic enforce these schema invariants automatically at FastAPI endpoints.",
                "difficulty": difficulty,
            }

        # Default Service / API Contract lab
        return {
            "order_index": order_index,
            "exercise_type": "coding",
            "title": f"Coding Lab: Messaging & Service Dispatcher ({topic_title})",
            "prompt": (
                "Implement `dispatch_message(pattern, subscribers, message)` simulating API messaging styles:\n"
                "- `'pub_sub'`: every subscriber receives `message` -> return `[{'worker': s, 'msg': message} for s in subscribers]`.\n"
                "- `'queue'`: only the first subscriber consumes `message` -> return `[{'worker': subscribers[0], 'msg': message}]` if subscribers else `[]`."
            ),
            "starter_code": (
                "def dispatch_message(pattern, subscribers, message):\n"
                "    # Implement 'pub_sub' broadcast vs 'queue' single-consumer dispatch\n"
                "    pass\n"
            ),
            "expected_output": "[{'worker': 'w1', 'msg': 'email'}]",
            "test_cases": [
                {
                    "description": "Pub-sub delivers message to all subscribers",
                    "assert_code": "assert len(dispatch_message('pub_sub', ['w1', 'w2'], 'ev')) == 2",
                },
                {
                    "description": "Queue delivers message to only one worker",
                    "assert_code": "assert dispatch_message('queue', ['w1', 'w2'], 'job') == [{'worker': 'w1', 'msg': 'job'}]",
                },
                {
                    "description": "Handles empty subscriber list safely",
                    "assert_code": "assert dispatch_message('queue', [], 'job') == []",
                },
            ],
            "hints": ["Branch on `if pattern == 'pub_sub':` vs `elif pattern == 'queue':`."],
            "explanation": "Pub-Sub broadcasts events to all listeners, whereas a Queue ensures each job is processed once by a worker pool.",
            "difficulty": difficulty,
        }

    @classmethod
    def _build_debugging_exercise(
        cls,
        low: str,
        topic_title: str,
        order_index: int,
        difficulty: str,
    ) -> Dict[str, Any]:
        """Return a topic-specific debugging challenge (NEVER reused latency arithmetic across unrelated topics!)."""
        if any(k in low for k in ("http", "rest", "crud", "endpoint")):
            buggy = (
                "def update_or_get_route(method, creatures, name, new_country=None):\n"
                "    \"\"\"GET reads creature cleanly; PATCH updates country; unknown returns 404.\"\"\"\n"
                "    if name not in creatures:\n"
                "        return 200, {'error': 'Not found'}  # Bug 1: wrong status code!\n"
                "    if method == 'GET':\n"
                "        creatures[name]['country'] = 'MUTATED'  # Bug 2: GET must NOT mutate state!\n"
                "        return 200, creatures[name]\n"
                "    if method == 'PATCH' and new_country:\n"
                "        creatures[name]['country'] = new_country\n"
                "        return 200, creatures[name]\n"
                "    return 405, {'error': 'Method not allowed'}\n"
            )
            return {
                "order_index": order_index,
                "exercise_type": "debugging",
                "title": f"Debug Challenge: HTTP Status & Safe GET ({topic_title})",
                "prompt": (
                    "**Expected behavior:** Return `404` when `name` is missing, and keep `GET` read-only.\n"
                    "**Actual bug:** Missing creatures currently return `200`, and `GET` mutates `'country'` to `'MUTATED'`. Fix both bugs."
                ),
                "buggy_code": buggy,
                "starter_code": buggy,
                "test_cases": [
                    {"description": "Missing creature returns 404", "assert_code": "assert update_or_get_route('GET', {}, 'yeti')[0] == 404"},
                    {"description": "GET does not mutate stored data", "assert_code": "s = {'yeti': {'country': 'CN'}}; assert update_or_get_route('GET', s, 'yeti')[1]['country'] == 'CN'"},
                    {"description": "PATCH updates country cleanly", "assert_code": "s = {'yeti': {'country': 'CN'}}; assert update_or_get_route('PATCH', s, 'yeti', 'NP')[1]['country'] == 'NP'"},
                ],
                "hints": ["Change `200` on missing key to `404`.", "Remove the mutation assignment inside the `if method == 'GET':` branch."],
                "explanation": "RESTful `GET` must stay safe/side-effect free, and missing resources must return `404` instead of `200`.",
                "difficulty": difficulty,
            }

        if any(k in low for k in ("json", "graphql", "data format")):
            buggy = (
                "import json\n\n"
                "def build_json_response(payload):\n"
                "    \"\"\"Serialize payload cleanly and set application/json header.\"\"\"\n"
                "    headers = {'Content-Type': 'text/plain'}  # Bug 1: wrong MIME type!\n"
                "    body = str(payload)  # Bug 2: Python repr uses single quotes, invalid JSON!\n"
                "    return {'headers': headers, 'body': body}\n"
            )
            return {
                "order_index": order_index,
                "exercise_type": "debugging",
                "title": f"Debug Challenge: Invalid JSON Response Serialization",
                "prompt": (
                    "**Expected behavior:** Return `Content-Type: application/json` and valid double-quoted JSON body.\n"
                    "**Actual bug:** The handler sends `text/plain` and uses `str(payload)` (single quotes, invalid JSON). Fix both."
                ),
                "buggy_code": buggy,
                "starter_code": buggy,
                "test_cases": [
                    {"description": "Uses application/json Content-Type", "assert_code": "assert build_json_response({'ok': True})['headers']['Content-Type'] == 'application/json'"},
                    {"description": "Produces valid parseable JSON string", "assert_code": "import json; r = build_json_response({'ok': True}); assert json.loads(r['body']) == {'ok': True}"},
                ],
                "hints": ["Set `'Content-Type': 'application/json'`.", "Use `json.dumps(payload)` instead of `str(payload)`."],
                "explanation": "Python dict `str()` is not valid JSON; `json.dumps()` and `application/json` ensure client interoperability.",
                "difficulty": difficulty,
            }

        if any(k in low for k in ("async", "concurren", "starlette")):
            buggy = (
                "import asyncio\n\n"
                "async def gather_fetches(coros):\n"
                "    \"\"\"Run coroutines concurrently cleanly returning list of results.\"\"\"\n"
                "    # Bug: executes sequentially instead of concurrently!\n"
                "    results = []\n"
                "    for c in coros:\n"
                "        results.append(c)  # Bug: appends unawaited coroutine objects!\n"
                "    return results\n"
            )
            return {
                "order_index": order_index,
                "exercise_type": "debugging",
                "title": f"Debug Challenge: Unawaited Coroutines in Async Handler",
                "prompt": (
                    "**Expected behavior:** Await all supplied coroutines concurrently via `asyncio.gather(*coros)`.\n"
                    "**Actual bug:** Returns raw coroutine objects without awaiting them. Fix using `await asyncio.gather(*coros)`."
                ),
                "buggy_code": buggy,
                "starter_code": buggy,
                "test_cases": [
                    {
                        "description": "Awaits and returns concrete values concurrently",
                        "assert_code": (
                            "import asyncio\n"
                            "async def f(x): return x * 2\n"
                            "out = asyncio.run(gather_fetches([f(2), f(3)]))\n"
                            "assert out == [4, 6], f'Got {out}'"
                        ),
                    },
                ],
                "hints": ["Replace the loop with `return await asyncio.gather(*coros)`."],
                "explanation": "Forgetting `await` leaves unexecuted coroutine objects instead of concurrent results.",
                "difficulty": difficulty,
            }

        if any(k in low for k in ("layer", "web layer", "service layer", "data layer")):
            buggy = (
                "def web_handler(raw_id, db):\n"
                "    \"\"\"Web handler should call service_find rather than raw internal DB keys.\"\"\"\n"
                "    if raw_id not in db:\n"
                "        return {'status': 404, 'error': 'Missing'}\n"
                "    record = db[raw_id]\n"
                "    # Bug: leaks internal secret field from Data layer directly to Web response!\n"
                "    return {'status': 200, 'data': record}\n"
            )
            return {
                "order_index": order_index,
                "exercise_type": "debugging",
                "title": f"Debug Challenge: Layer Leak Exposing Internal Secret",
                "prompt": (
                    "**Expected behavior:** Exclude `'internal_hash'` from the returned `data` dict (information hiding across layers).\n"
                    "**Actual bug:** Raw DB dict including `'internal_hash'` leaks directly to the HTTP client. Strip `'internal_hash'` safely without mutating `db`."
                ),
                "buggy_code": buggy,
                "starter_code": buggy,
                "test_cases": [
                    {
                        "description": "Excludes internal_hash without mutating underlying db dict",
                        "assert_code": (
                            "db = {'yeti': {'name': 'Yeti', 'internal_hash': 'secret'}}\n"
                            "res = web_handler('yeti', db)\n"
                            "assert res['status'] == 200 and 'internal_hash' not in res['data']\n"
                            "assert 'internal_hash' in db['yeti']"
                        ),
                    },
                ],
                "hints": ["Build a new dict `{k: v for k, v in record.items() if k != 'internal_hash'}`."],
                "explanation": "Projection between Data and Web layers protects internal fields without mutating stored records.",
                "difficulty": difficulty,
            }

        # Services & APIs / Default domain debugging challenge
        buggy = (
            "def validate_api_contract(request_body):\n"
            "    \"\"\"Require non-empty 'endpoint' str and 'method' in {'GET', 'POST'}.\"\"\"\n"
            "    if not isinstance(request_body, dict):\n"
            "        return False, 'Body must be a dict'\n"
            "    # Bug 1: checks wrong key 'url' instead of 'endpoint'\n"
            "    if not request_body.get('url'):\n"
            "        return False, 'Missing endpoint'\n"
            "    # Bug 2: case-sensitive check rejects lowercase 'get' instead of normalizing .upper()\n"
            "    if request_body.get('method') not in {'GET', 'POST'}:\n"
            "        return False, 'Invalid method'\n"
            "    return True, 'OK'\n"
        )
        return {
            "order_index": order_index,
            "exercise_type": "debugging",
            "title": f"Debug Challenge: API Contract Validation Mismatch",
            "prompt": (
                "**Expected behavior:** Accept `'endpoint'` (not `'url'`) and normalize `'method'` case-insensitively (`'get'` -> `'GET'`).\n"
                "**Actual bug:** Fails valid contracts with `'endpoint'` or lowercase `'get'`. Fix both contract checks."
            ),
            "buggy_code": buggy,
            "starter_code": buggy,
            "test_cases": [
                {"description": "Validates 'endpoint' key properly", "assert_code": "assert validate_api_contract({'endpoint': '/creatures', 'method': 'GET'})[0] is True"},
                {"description": "Accepts lowercase HTTP method", "assert_code": "assert validate_api_contract({'endpoint': '/creatures', 'method': 'get'})[0] is True"},
                {"description": "Rejects empty endpoint", "assert_code": "assert validate_api_contract({'endpoint': '', 'method': 'POST'})[0] is False"},
            ],
            "hints": ["Replace `request_body.get('url')` with `request_body.get('endpoint')`.", "Normalize method with `str(request_body.get('method', '')).upper()`."],
            "explanation": "API contract validators must match exact agreed field names and normalize inputs consistently.",
            "difficulty": difficulty,
        }

    @classmethod
    def build_module_assessment(
        cls,
        course_id: int,
        chapter_id: int,
        chapter_title: str,
        lessons: List[Any],
    ) -> Dict[str, Any]:
        """Build a graded module assessment pulling concept-card checks & takeaways (deduplicated, no naive exact copies)."""
        questions: List[Dict[str, Any]] = []
        seen_prompts: set[str] = set()
        qid = 1

        def _add_question(q: Dict[str, Any]) -> bool:
            nonlocal qid
            norm = re.sub(r"\s+", " ", (q.get("prompt") or "").strip().lower())
            if not norm or norm in seen_prompts:
                return False
            seen_prompts.add(norm)
            q["id"] = f"m_{chapter_id}_{qid}"
            questions.append(q)
            qid += 1
            return True

        for lesson in lessons:
            l_title = getattr(lesson, "title", "Lesson")
            t_id = getattr(lesson, "topic_id", None)
            l_id = getattr(lesson, "id", None)
            sec = getattr(lesson, "structured_sections", None) or {}
            cards = sec.get("concept_cards") or []
            added_from_cards = 0

            # First pull embedded interactive concept-card checks (distinct from main lesson MCQ!)
            for card in cards:
                qc = card.get("quick_check")
                if qc and qc.get("options") and qc.get("correct_answer"):
                    if _add_question({
                        "question_type": "mcq",
                        "prompt": qc["question"],
                        "options": qc["options"],
                        "correct_answer": qc["correct_answer"],
                        "explanation": qc.get("explanation") or "",
                        "topic_id": t_id,
                        "topic_title": l_title,
                        "lesson_id": l_id,
                    }):
                        added_from_cards += 1
                        if added_from_cards >= 1:
                            break

            # Add 1 revision / synthesis question from lesson exercises (3rd or 2nd MCQ) so coverage spans all lessons
            exercises = list(getattr(lesson, "exercises", []) or [])
            mcqs = [e for e in exercises if getattr(e, "exercise_type", "") == "mcq" and getattr(e, "options", None)]
            added_from_ex = False
            if mcqs:
                pick = mcqs[-1] if added_from_cards else mcqs[0]
                added_from_ex = _add_question({
                    "question_type": "mcq",
                    "prompt": pick.prompt,
                    "options": pick.options,
                    "correct_answer": pick.correct_answer,
                    "explanation": pick.explanation or "",
                    "topic_id": t_id,
                    "topic_title": l_title,
                    "lesson_id": l_id,
                })
            if not added_from_cards and not added_from_ex:
                takeaways = list(getattr(lesson, "key_takeaways", []) or [])
                claim = takeaways[0] if takeaways else f"Modular boundaries clarify behavior across {l_title}."
                opts = [
                    cls._concise(claim),
                    f"Skipping explicit contracts speeds up long-term maintenance in {l_title}.",
                    f"Mixing storage queries directly into transport code strengthens {l_title}.",
                    "Ignoring error states avoids handling client requests.",
                ]
                _add_question({
                    "question_type": "mcq",
                    "prompt": f"Which statement reflects a verified architectural rule from **{l_title}**?",
                    "options": opts,
                    "correct_answer": opts[0],
                    "explanation": claim,
                    "topic_id": t_id,
                    "topic_title": l_title,
                    "lesson_id": l_id,
                })

        return {
            "course_id": course_id,
            "chapter_id": chapter_id,
            "assessment_type": "module",
            "title": f"Module Assessment: {chapter_title}",
            "description": f"Verify conceptual and applied mastery across all {len(lessons)} lesson(s) in {chapter_title}. Passing threshold: 70%.",
            "passing_score": 70.0,
            "questions": questions[:12],
        }

    @classmethod
    def build_final_assessment(
        cls,
        course_id: int,
        course_title: str,
        chapters: List[Any],
    ) -> Dict[str, Any]:
        """Build a Final Course Assessment sampling proportionately across every module."""
        questions: List[Dict[str, Any]] = []
        seen_prompts: set[str] = set()
        qid = 1
        per_chap = 1 if len(chapters) > 10 else 2
        for chapter in chapters:
            topics = list(getattr(chapter, "topics", []) or [])
            chapter_lessons = [getattr(t, "lesson", None) for t in topics if getattr(t, "lesson", None)]
            mod_data = cls.build_module_assessment(
                course_id=course_id,
                chapter_id=getattr(chapter, "id", 0),
                chapter_title=getattr(chapter, "title", "Module"),
                lessons=chapter_lessons,
            )
            added = 0
            for q in mod_data["questions"]:
                norm = re.sub(r"\s+", " ", (q.get("prompt") or "").strip().lower())
                if not norm or norm in seen_prompts:
                    continue
                seen_prompts.add(norm)
                q["id"] = f"final_{course_id}_{qid}"
                questions.append(q)
                qid += 1
                added += 1
                if added >= per_chap:
                    break

        return {
            "course_id": course_id,
            "chapter_id": None,
            "assessment_type": "final",
            "title": f"Final Mastery Exam: {course_title}",
            "description": f"Comprehensive exam sampling all {len(chapters)} modules of {course_title}. Passing threshold: 70%.",
            "passing_score": 70.0,
            "questions": questions[:20],
        }

    @staticmethod
    def _concise(text: str, max_len: int = 128) -> str:
        clean = re.sub(r"\s+", " ", re.sub(r"[*_`#]", "", text)).strip()
        if len(clean) <= max_len:
            return clean
        return clean[: max_len - 3].rsplit(" ", 1)[0] + "..."

    @staticmethod
    def _extract_factual_claims(lesson_content: str, source_text: str) -> List[str]:
        """Extract clean declarative claims while strictly skipping headings & Learning Objectives."""
        # Remove Learning Objectives & Check Your Understanding blocks
        stripped = re.sub(r"## Learning Objectives.*?(?=\n##|\Z)", "", lesson_content, flags=re.DOTALL)
        stripped = re.sub(r"## Check Your Understanding.*?(?=\n##|\Z)", "", stripped, flags=re.DOTALL)
        stripped = re.sub(r"```.*?```", " ", stripped, flags=re.DOTALL)
        combined = f"{stripped}\n\n{source_text[:1800]}"
        candidates: List[str] = []
        for line in combined.splitlines():
            s = line.strip().lstrip("-* ").strip()
            if not s or s.startswith("#") or s.startswith("|") or len(s) < 38 or len(s) > 220:
                continue
            if re.match(r"^(?:Define|Explain|Understand|Identify|Apply|Analyze|Evaluate|Create|Imagine)\b", s):
                continue
            if any(bad in s.lower() for bad in ("chapter ", "page ", "this book", "copyright", "o'reilly")):
                continue
            candidates.append(s)

        deduped: List[str] = []
        seen = set()
        for c in candidates:
            key = c[:45].lower()
            if key not in seen:
                seen.add(key)
                deduped.append(c)
        return deduped[:8]

    @staticmethod
    def _extract_key_terms(lesson_content: str, topic_title: str) -> List[str]:
        bold_terms = re.findall(r"\*\*([A-Za-z][A-Za-z0-9\s\-_/:]{2,32})\*\*", lesson_content)
        backtick_terms = re.findall(r"`([A-Za-z_][A-Za-z0-9_\.]{2,28})`", lesson_content)
        stop = {"introduction", "core concepts", "worked example", "common mistakes", "key takeaways", "check your understanding", "learning objectives", "real-world application", "mistake", "why", "correct approach"}
        terms: List[str] = []
        for raw in bold_terms + backtick_terms + [topic_title]:
            cleaned = raw.strip(" .:;-")
            if len(cleaned) >= 3 and cleaned.lower() not in stop and cleaned not in terms:
                terms.append(cleaned)
        return terms[:8] or [topic_title]
