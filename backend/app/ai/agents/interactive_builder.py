"""Interactive learning payload builder for LearnForge AI lessons.

Generates structured Concept Cards, selectable Architecture Diagrams, interactive
Simulators, and continuous Course Project Milestones grounded in the lesson topic,
course title, chapter context, and extracted source text.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class InteractiveLearningBuilder:
    """Builds interactive concept cards, architecture diagrams, simulators & project steps."""

    @classmethod
    def build(
        cls,
        topic_title: str,
        chapter_title: str,
        course_title: str,
        lesson_content: str,
        source_text: str,
        subtopics: Optional[List[str]] = None,
        chapter_order: int = 0,
        domain: str = "general",
    ) -> Dict[str, Any]:
        sub_list = subtopics or []
        concept_cards = cls._build_concept_cards(topic_title, chapter_title, lesson_content, source_text, sub_list)
        architecture_diagram = cls._build_architecture_diagram(topic_title, chapter_title, domain)
        simulator = cls._build_simulator(topic_title, chapter_title, domain)
        project_step = cls._build_project_step(topic_title, chapter_title, course_title, chapter_order, domain)
        matching_exercise = cls._build_matching_exercise(topic_title, chapter_title, concept_cards, domain)
        return {
            "concept_cards": concept_cards,
            "matching_exercise": matching_exercise,
            "architecture_diagram": architecture_diagram,
            "simulator": simulator,
            "project_step": project_step,
        }

    @classmethod
    def _build_matching_exercise(
        cls,
        topic_title: str,
        chapter_title: str,
        concept_cards: List[Dict[str, Any]],
        domain: str,
    ) -> Dict[str, Any]:
        pairs: List[Dict[str, str]] = []
        seen_terms: set[str] = set()
        for idx, card in enumerate(concept_cards):
            term = str(card.get("term") or "").strip()
            desc = str(card.get("what_it_is") or "").strip()
            if term and desc and term.lower() not in seen_terms:
                seen_terms.add(term.lower())
                pairs.append({
                    "id": f"pair_{idx + 1}",
                    "term": term,
                    "description": desc,
                })
            if len(pairs) >= 4:
                break

        fallback_bank = [
            ("HTTP Request-Response", "Client sends an HTTP request to a URL and waits for a status-coded response."),
            ("Message Queue", "Distributes each background task to a single competing worker from a pool."),
            ("Stateless Endpoint", "Processes each request independently without relying on hidden server session state."),
            ("Pydantic Schema", "Validates incoming JSON payloads and enforces Python type contracts at runtime."),
        ] if domain == "computer_science" else [
            (f"{topic_title} Core Principle", f"Defines the foundational rule governing {topic_title}."),
            ("Input Contract", "Specifies the required inputs and preconditions before execution."),
            ("Processing Mechanism", f"Transforms inputs into verified outputs within {chapter_title}."),
            ("Failure Boundary", "Captures edge cases and invalid states before they propagate."),
        ]

        for term, desc in fallback_bank:
            if len(pairs) >= 4:
                break
            if term.lower() not in seen_terms:
                seen_terms.add(term.lower())
                pairs.append({
                    "id": f"pair_{len(pairs) + 1}",
                    "term": term,
                    "description": desc,
                })

        return {
            "title": f"Concept Matching: {topic_title}",
            "instructions": "Match each concept on the left with its accurate technical description on the right.",
            "pairs": pairs,
        }

    @classmethod
    def _build_concept_cards(
        cls,
        topic_title: str,
        chapter_title: str,
        lesson_content: str,
        source_text: str,
        subtopics: List[str],
    ) -> List[Dict[str, Any]]:
        low = f"{topic_title} {chapter_title} {' '.join(subtopics)}".lower()
        cards: List[Dict[str, Any]] = []

        # Extract genuine bold/definition pairs from lesson content + source first
        extracted_defs = cls._extract_bold_definitions(lesson_content)

        # Enrich with structured domain-accurate conceptual comparisons when topic discusses APIs / Web / Concurrency / Layers
        if any(k in low for k in ("service", "api", "rpc", "messaging", "kinds of api")):
            cards.extend([
                {
                    "term": "Library API vs Service API",
                    "what_it_is": "Library APIs are local function/method calls compiled or imported in-process, whereas Service APIs exchange structured messages over a network boundary.",
                    "why_it_exists": "Teams decouple frontend UIs from backend business/database systems so each layer scales and deploys independently.",
                    "how_it_works": "A client sends an explicit request contract over HTTP, RPC, or messaging middleware; the service processes it and returns serialized data.",
                    "example": "Calling `math.sqrt(16)` is a library call; requesting `GET /creatures/yeti` over HTTP is a service API call.",
                    "difference": "Library calls share memory space and throw language exceptions; service calls cross network boundaries using URLs, verbs, and status codes.",
                    "quick_check": {
                        "question": "Which communication pattern passes messages where multiple workers compete so only ONE worker processes each task?",
                        "options": ["Publish-Subscribe", "Message Queue", "In-Process Library Call", "HTML Rendering"],
                        "correct_answer": "Message Queue",
                        "explanation": "A Queue delivers each message to one subscriber from a pool, whereas Publish-Subscribe broadcasts to matching subscribers.",
                    },
                },
                {
                    "term": "Request-Response vs Pub-Sub vs Queues",
                    "what_it_is": "Three messaging styles used alongside or inside modern web services.",
                    "why_it_exists": "Slow background work (sending emails, image processing) should not block user-facing HTTP responses.",
                    "how_it_works": "Request-Response is 1:1 (browser -> server); Pub-Sub broadcasts events by topic; Queues dispatch each job to one available worker.",
                    "example": "HTTP is Request-Response; sending a signup welcome email can run asynchronously through a worker queue.",
                    "difference": "Pub-Sub fans out to all interested listeners; Queues distribute load across workers.",
                },
            ])
        if any(k in low for k in ("http", "rest", "crud", "endpoint", "route")):
            cards.extend([
                {
                    "term": "RESTful Design Principles",
                    "what_it_is": "An architectural style over HTTP emphasizing stateless, cacheable, resource-based endpoints.",
                    "why_it_exists": "Stateless HTTP endpoints simplify horizontal scaling and caching across clients (browsers, mobile apps, services).",
                    "how_it_works": "Each resource URL (like `/creatures`) is paired with standard HTTP methods (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`).",
                    "example": "`GET /creatures/bigfoot` retrieves a resource; `POST /creatures` creates a new one.",
                    "difference": "Stateless means each HTTP request carries all context the server needs instead of relying on hidden server session state.",
                    "quick_check": {
                        "question": "Which HTTP method partially updates an existing resource rather than replacing the entire resource?",
                        "options": ["POST", "PUT", "PATCH", "GET"],
                        "correct_answer": "PATCH",
                        "explanation": "`PUT` replaces a resource completely, while `PATCH` applies a partial update.",
                    },
                },
                {
                    "term": "HTTP Status Code Families",
                    "what_it_is": "Standard 3-digit response codes categorizing request outcomes.",
                    "why_it_exists": "Clients can programmatically distinguish success, redirects, client input mistakes, and server crashes without scraping prose.",
                    "how_it_works": "2xx signals success (`200`, `201`), 3xx redirection, 4xx client error (`404`, `422`), and 5xx server failure.",
                    "example": "Returning `404 Not Found` when `/creatures/unknown` does not exist lets frontends display a clean fallback.",
                    "difference": "4xx indicates the client sent bad data or requested a missing path; 5xx indicates the backend crashed.",
                },
            ])
        if any(k in low for k in ("json", "graphql", "data format")):
            cards.append({
                "term": "JSON vs JSON:API vs GraphQL",
                "what_it_is": "Data representation and query conventions used in modern APIs.",
                "why_it_exists": "Applications need lightweight, language-neutral serialization for nested lists and objects instead of verbose XML.",
                "how_it_works": "JSON encodes objects/arrays cleanly; JSON:API standardizes pagination/error envelopes; GraphQL lets clients query exact nested fields in one request.",
                "example": "Rest APIs often use JSON payloads, while GraphQL solves over-fetching/under-fetching across complex graphs.",
                "difference": "REST routes resources across URLs; GraphQL exposes a query schema typically at a single endpoint.",
                "quick_check": {
                    "question": "Which problem was GraphQL specifically designed by Meta to solve compared to fixed REST endpoints?",
                    "options": ["Browser CSS styling", "Flexible client-specified nested queries", "SQL table locking", "Local Python function imports"],
                    "correct_answer": "Flexible client-specified nested queries",
                    "explanation": "GraphQL lets clients request exact fields rather than receiving fixed REST response shapes.",
                },
            })
        if any(k in low for k in ("async", "concurren", "starlette", "event loop", "throughput", "latency")):
            cards.append({
                "term": "Latency, Throughput & Async I/O",
                "what_it_is": "Latency is upfront wait time per request; throughput is bytes or requests handled per second.",
                "why_it_exists": "Waiting idly on slow network or database I/O wastes server capacity.",
                "how_it_works": "Asynchronous `async/await` yields control back to an event loop during I/O waits so other requests progress concurrently.",
                "example": "In FastAPI, `async def` handles concurrent network/DB awaits cleanly without blocking worker threads.",
                "difference": "Async concurrency excels at I/O-bound waiting, whereas heavy CPU-bound loops block the event loop and need worker processes.",
                "quick_check": {
                    "question": "What happens if you run a heavy synchronous CPU computation directly inside an async FastAPI event loop handler?",
                    "options": ["It automatically runs on GPU", "It blocks other concurrent async requests on that event loop", "It makes HTTP status codes 201", "It turns JSON into XML"],
                    "correct_answer": "It blocks other concurrent async requests on that event loop",
                    "explanation": "A single-threaded event loop relies on cooperative `await` yields; CPU-heavy synchronous blocks stall all concurrent coroutines.",
                },
            })
        if any(k in low for k in ("layer", "service layer", "data layer", "web layer")):
            cards.append({
                "term": "Web, Service & Data Layers",
                "what_it_is": "Separation of an application into Web (HTTP handling), Service (business logic), and Data (persistence) tiers.",
                "why_it_exists": "Information hiding lets you swap databases or change routes without rewriting business rules.",
                "how_it_works": "Web layer parses HTTP & calls Service functions; Service calls Data repository functions returning clean Models.",
                "example": "FastAPI routers handle status codes and Pydantic validation, delegating queries to `service/` and `data/` modules.",
                "difference": "Bypassing the Service layer directly from Web handlers couples HTTP routes to SQL storage details.",
                "quick_check": {
                    "question": "Why should Web route handlers avoid running raw database queries directly?",
                    "options": ["It violates layer separation and scatters business rules", "Python forbids SQL inside functions", "HTTP does not support GET requests", "JSON requires 3 databases"],
                    "correct_answer": "It violates layer separation and scatters business rules",
                    "explanation": "Keeping HTTP routing, business logic, and database access separate simplifies testing and maintenance.",
                },
            })

        # Add extracted definitions from the current lesson markdown for universal domain coverage
        existing_terms = {c["term"].lower() for c in cards}
        for term, desc in extracted_defs:
            if term.lower() in existing_terms or len(cards) >= 5:
                continue
            existing_terms.add(term.lower())
            cards.append({
                "term": term,
                "what_it_is": desc,
                "why_it_exists": f"Core building block in {topic_title} ({chapter_title}).",
                "how_it_works": desc,
                "example": f"Applied inside the Worked Example and Practice sections of {topic_title}.",
                "difference": f"Distinguished from adjacent concepts within {chapter_title} by explicit contract and scope.",
            })

        return cards[:5]

    @staticmethod
    def _extract_bold_definitions(lesson_content: str) -> List[tuple[str, str]]:
        pairs: List[tuple[str, str]] = []
        for line in lesson_content.splitlines():
            m = re.match(r"^\s*(?:[-*]|\d+\.)?\s*\*\*([A-Za-z][A-Za-z0-9\s\-:/()]{2,42})\*\*\s*[:\-–]\s*(.+)$", line.strip())
            if m:
                term = m.group(1).strip()
                desc = m.group(2).strip()
                if len(desc) >= 20 and not any(x in term.lower() for x in ("mistake", "incorrect", "correct", "question")):
                    pairs.append((term, desc))
        return pairs[:6]

    @staticmethod
    def _build_architecture_diagram(topic_title: str, chapter_title: str, domain: str) -> Optional[Dict[str, Any]]:
        low = f"{topic_title} {chapter_title}".lower()
        if any(k in low for k in ("layer", "web layer", "service layer", "data layer")):
            return {
                "title": "Layered Web Service Architecture",
                "subtitle": "Click any component to inspect its contract, inputs, processing, and outputs.",
                "nodes": [
                    {
                        "id": "client",
                        "label": "Frontend / Client",
                        "role": "User interface sending HTTP requests",
                        "input": "User interactions (clicks, forms)",
                        "process": "Formats URL, method, query params, and JSON payload",
                        "output": "HTTP request -> Web Layer",
                        "connects_to": ["Web Layer"],
                    },
                    {
                        "id": "web",
                        "label": "Web Layer (FastAPI Router)",
                        "role": "HTTP transport & validation boundary",
                        "input": "Raw HTTP request + headers/body",
                        "process": "Parses path/query/body via Pydantic and injects dependencies",
                        "output": "Validated Python model -> Service Layer; returns JSON + status code",
                        "connects_to": ["Frontend / Client", "Service Layer"],
                    },
                    {
                        "id": "service",
                        "label": "Service Layer (Business Logic)",
                        "role": "Domain rules & orchestration",
                        "input": "Validated domain models / parameters",
                        "process": "Executes domain workflows without HTTP or SQL coupling",
                        "output": "Domain result -> Web Layer; persistence calls -> Data Layer",
                        "connects_to": ["Web Layer", "Data Layer"],
                    },
                    {
                        "id": "data",
                        "label": "Data Layer (Repository / DB)",
                        "role": "Persistence & query abstraction",
                        "input": "Entity lookup or write commands",
                        "process": "Executes SQLite/SQL/NoSQL operations cleanly",
                        "output": "Stored record -> Service Layer",
                        "connects_to": ["Service Layer"],
                    },
                ],
            }
        if any(k in low for k in ("http", "rest", "service", "api", "json", "fastapi")):
            return {
                "title": "HTTP Request -> Response Lifecycle",
                "subtitle": "Inspect how a FastAPI/REST client-server request flows step by step.",
                "nodes": [
                    {
                        "id": "req",
                        "label": "Client Request",
                        "role": "Initiates operation via HTTP verb & URL",
                        "input": "Verb (GET/POST/...) + Path + Query/JSON Body",
                        "process": "Serializes payload to JSON over TCP/HTTP",
                        "output": "Structured HTTP request message",
                        "connects_to": ["API Router"],
                    },
                    {
                        "id": "router",
                        "label": "API Route & Validation",
                        "role": "Matches URL pattern & checks contract",
                        "input": "HTTP headers, path params, JSON payload",
                        "process": "Validates types/constraints; returns 422 on schema mismatch",
                        "output": "Typed Python arguments",
                        "connects_to": ["Client Request", "Service Handler"],
                    },
                    {
                        "id": "handler",
                        "label": "Service / Endpoint Logic",
                        "role": "Performs requested domain operation",
                        "input": "Validated arguments",
                        "process": "Reads/writes data or computes response payload",
                        "output": "Structured result object",
                        "connects_to": ["API Route & Validation", "HTTP Response"],
                    },
                    {
                        "id": "resp",
                        "label": "HTTP JSON Response",
                        "role": "Returns outcome with standard status code",
                        "input": "Result data or error signal",
                        "process": "Attaches Content-Type: application/json & status (200/201/404)",
                        "output": "JSON payload -> Client",
                        "connects_to": ["Client Request"],
                    },
                ],
            }
        if any(k in low for k in ("async", "concurren", "starlette")):
            return {
                "title": "Async Event Loop Execution Flow",
                "subtitle": "Compare how async I/O yields vs CPU blocking.",
                "nodes": [
                    {
                        "id": "incoming",
                        "label": "Concurrent Requests",
                        "role": "Multiple clients connecting simultaneously",
                        "input": "HTTP connections A, B, C",
                        "process": "Queued cleanly onto ASGI server (Uvicorn/Starlette)",
                        "output": "Coroutines dispatched to Event Loop",
                        "connects_to": ["Event Loop"],
                    },
                    {
                        "id": "loop",
                        "label": "ASGI Event Loop",
                        "role": "Schedules coroutines between await points",
                        "input": "Pending coroutines",
                        "process": "Switches instantly to Request B when Request A awaits I/O",
                        "output": "High throughput with minimal wait idle time",
                        "connects_to": ["Concurrent Requests", "Non-Blocking I/O"],
                    },
                    {
                        "id": "io",
                        "label": "Non-Blocking I/O (DB / HTTP)",
                        "role": "Network/disk waits handled asynchronously",
                        "input": "Async query / external API call",
                        "process": "Resumes coroutine once bytes arrive",
                        "output": "Completed data returned to Event Loop",
                        "connects_to": ["ASGI Event Loop"],
                    },
                ],
            }
        if domain == "computer_science":
            return {
                "title": f"{topic_title} Execution Pipeline",
                "subtitle": "Select each stage to trace inputs, transformations, and outputs.",
                "nodes": [
                    {"id": "in", "label": "Input & Contract", "role": f"Structured input entering {topic_title}", "input": "Arguments / Request", "process": "Type & boundary validation", "output": "Sanitized input", "connects_to": ["Core Processing"]},
                    {"id": "proc", "label": "Core Processing", "role": f"Primary logic of {topic_title}", "input": "Validated state", "process": "Executes core transformation / rule", "output": "Intermediate result", "connects_to": ["Input & Contract", "Output"]},
                    {"id": "out", "label": "Structured Output", "role": "Result returned to caller", "input": "Processed state", "process": "Formats response / return value", "output": "Predictable contract", "connects_to": ["Core Processing"]},
                ],
            }
        return None

    @staticmethod
    def _build_simulator(topic_title: str, chapter_title: str, domain: str) -> Optional[Dict[str, Any]]:
        low = f"{topic_title} {chapter_title}".lower()
        if any(k in low for k in ("services and apis", "kinds of api", "rpc", "messaging")):
            return {
                "type": "api_communication",
                "title": "API & Messaging Communication Simulator",
                "description": "Compare Library Function Calls, RPC, Request-Response (HTTP), Publish-Subscribe, and Message Queues in a simulated environment.",
            }
        if any(k in low for k in ("layer", "web layer", "service layer", "data layer")):
            return {
                "type": "layered_architecture",
                "title": "Layered Architecture Request Tracer",
                "description": "Step through how Web, Service, and Data layers collaborate cleanly without layer violations.",
            }
        if any(k in low for k in ("http", "rest", "service", "api", "json", "fastapi", "endpoint", "route")):
            return {
                "type": "http_request",
                "title": "Interactive HTTP & REST Request Simulator",
                "description": "Experiment with GET, POST, PUT, PATCH, DELETE requests against a sample Creature endpoint and inspect live request/response behavior.",
                "default_method": "GET",
                "default_endpoint": "/creatures",
            }
        if any(k in low for k in ("async", "concurren", "starlette")):
            return {
                "type": "concurrency_trace",
                "title": "Synchronous vs Asynchronous Throughput Simulator",
                "description": "Compare total completion latency when 3 I/O requests run sequentially vs concurrently on an async event loop.",
            }
        return None

    @staticmethod
    def _build_project_step(
        topic_title: str,
        chapter_title: str,
        course_title: str,
        chapter_order: int,
        domain: str,
    ) -> Optional[Dict[str, Any]]:
        is_fastapi_course = "fastapi" in f"{course_title} {chapter_title}".lower()
        if not is_fastapi_course and domain != "computer_science":
            return None

        ch_low = f"{chapter_title} {topic_title}".lower()
        if "modern web" in ch_low or "services" in ch_low or "rest" in ch_low:
            return {
                "project_name": "Mini Creature Management API",
                "step_number": 1,
                "milestone_title": "Step 1: Design Creature API Endpoints & Resource Contract",
                "learning_objective": "Map CRUD operations onto explicit RESTful HTTP methods, resource URLs, and status codes.",
                "deliverable": "Define REST endpoints for creatures (`/creatures`, `/creatures/{name}`) with HTTP verbs (`GET`, `POST`, `PATCH`, `DELETE`) and expected status codes.",
                "requirements": [
                    "Define `ENDPOINTS` mapping `list_creatures`, `get_creature`, `create_creature`, and `delete_creature`.",
                    "Use HTTP 201 for `create_creature` (`POST`) and HTTP 200 for `GET` / `DELETE`.",
                ],
                "starter_code": (
                    "# Design contract for our Mini Creature Management API\n"
                    "ENDPOINTS = {\n"
                    "    'list_creatures': ('GET', '/creatures', 200),\n"
                    "    'get_creature': ('GET', '/creatures/{name}', 200),\n"
                    "    'create_creature': ('POST', '/creatures', 201),\n"
                    "    'delete_creature': ('DELETE', '/creatures/{name}', 200),\n"
                    "}\n"
                    "print('Configured endpoints:', len(ENDPOINTS))\n"
                ),
                "expected_output": "Configured endpoints: 4",
                "test_cases": [
                    {"description": "ENDPOINTS defines all 4 CRUD routes", "assert_code": "assert len(ENDPOINTS) == 4"},
                    {"description": "create_creature uses POST and HTTP 201", "assert_code": "assert ENDPOINTS['create_creature'] == ('POST', '/creatures', 201)"},
                ],
                "hints": [
                    "Each entry in ENDPOINTS should be a 3-tuple: (method, path, status_code).",
                    "POST requests that create a new resource conventionally return 201 Created.",
                ],
                "explanation": "Separating resource URLs from HTTP verbs lets clients and servers agree on a predictable REST contract before writing route handlers.",
            }
        if "modern python" in ch_low or "type hint" in ch_low:
            return {
                "project_name": "Mini Creature Management API",
                "step_number": 2,
                "milestone_title": "Step 2: Add Typed Creature Dataclass / Type Hints",
                "learning_objective": "Apply Python type annotations (`str`, `Optional[str]`, `dict`) to make API data contracts explicit.",
                "deliverable": "Annotate Creature helper functions with Python type hints (`str`, `Optional[str]`) before adding Pydantic validation.",
                "requirements": [
                    "Accept `name: str`, `country: str`, and optional `aka: Optional[str] = None`.",
                    "Return a dictionary containing `'name'`, `'country'`, and `'aka'` keys.",
                ],
                "starter_code": (
                    "from typing import Optional\n\n"
                    "def format_creature(name: str, country: str, aka: Optional[str] = None) -> dict:\n"
                    "    return {'name': name, 'country': country, 'aka': aka}\n\n"
                    "print(format_creature('Yeti', 'CN', 'Abominable Snowman'))\n"
                ),
                "expected_output": "{'name': 'Yeti', 'country': 'CN', 'aka': 'Abominable Snowman'}",
                "test_cases": [
                    {"description": "format_creature returns expected dict with optional aka", "assert_code": "assert format_creature('Bigfoot', 'US') == {'name': 'Bigfoot', 'country': 'US', 'aka': None}"},
                    {"description": "format_creature preserves explicit aka", "assert_code": "assert format_creature('Yeti', 'CN', 'Snowman')['aka'] == 'Snowman'"},
                ],
                "hints": [
                    "Use `Optional[str] = None` so callers can omit `aka`.",
                ],
                "explanation": "FastAPI builds its OpenAPI schema and request validation directly from Python type annotations.",
            }
        if "fastapi tour" in ch_low or "application" in ch_low:
            return {
                "project_name": "Mini Creature Management API",
                "step_number": 3,
                "milestone_title": "Step 3: Initialize FastAPI App & First Endpoint",
                "learning_objective": "Define a FastAPI application instance and bind a GET route handler returning JSON.",
                "deliverable": "Create `FastAPI()` instance and expose `/creatures` returning JSON.",
                "requirements": [
                    "Instantiate `app = FastAPI(title='Creature Management API')`.",
                    "Decorate `list_creatures()` with `@app.get('/creatures')`.",
                ],
                "starter_code": (
                    "from fastapi import FastAPI\n\n"
                    "app = FastAPI(title='Creature Management API')\n\n"
                    "@app.get('/creatures')\n"
                    "def list_creatures():\n"
                    "    return [{'name': 'Yeti', 'country': 'CN'}]\n"
                ),
                "expected_output": "[{'name': 'Yeti', 'country': 'CN'}]",
                "test_cases": [],
                "hints": [
                    "FastAPI automatically serializes returned Python lists and dicts to JSON.",
                ],
                "explanation": "FastAPI inspects the `@app.get('/creatures')` decorator and converts the returned Python list into an HTTP JSON response.",
            }
        if "async" in ch_low or "concurren" in ch_low:
            return {
                "project_name": "Mini Creature Management API",
                "step_number": 4,
                "milestone_title": "Step 4: Convert Slow Sighting Check to `async def`",
                "learning_objective": "Use `async def` and `await asyncio.sleep(...)` to avoid blocking the event loop on I/O.",
                "deliverable": "Use `async def` and non-blocking `await asyncio.sleep(...)` for I/O sighting lookups.",
                "requirements": [
                    "Define `async def fetch_sighting(name: str) -> dict`.",
                    "Yield control with `await asyncio.sleep(0.01)` and return `{'name': name, 'verified': True}`.",
                ],
                "starter_code": (
                    "import asyncio\n\n"
                    "async def fetch_sighting(name: str) -> dict:\n"
                    "    await asyncio.sleep(0.01)\n"
                    "    return {'name': name, 'verified': True}\n\n"
                    "print(asyncio.run(fetch_sighting('Yeti')))\n"
                ),
                "expected_output": "{'name': 'Yeti', 'verified': True}",
                "test_cases": [
                    {"description": "fetch_sighting is a coroutine returning verified dict", "assert_code": "import asyncio; res = asyncio.run(fetch_sighting('Nessie')); assert res == {'name': 'Nessie', 'verified': True}"},
                ],
                "hints": [
                    "Never call `time.sleep()` inside an `async def` handler; use `await asyncio.sleep()` instead.",
                ],
                "explanation": "Cooperative multitasking lets the FastAPI event loop serve other requests while waiting on slow I/O.",
            }
        if "pydantic" in ch_low or "model" in ch_low:
            return {
                "project_name": "Mini Creature Management API",
                "step_number": 5,
                "milestone_title": "Step 5: Validate Creature Requests with Pydantic",
                "learning_objective": "Enforce structured field validation and defaults using Pydantic `BaseModel`.",
                "deliverable": "Define a strict `Creature(BaseModel)` schema validating required strings.",
                "requirements": [
                    "Inherit from `BaseModel` and declare `name`, `country`, `area`, `description`, and `aka: str = ''`.",
                ],
                "starter_code": (
                    "from pydantic import BaseModel\n\n"
                    "class Creature(BaseModel):\n"
                    "    name: str\n"
                    "    country: str\n"
                    "    area: str\n"
                    "    description: str\n"
                    "    aka: str = ''\n"
                ),
                "expected_output": "Creature(name='Yeti', country='CN', area='Himalayas', description='...', aka='')",
                "test_cases": [],
                "hints": [
                    "Providing `aka: str = ''` makes `aka` optional with an empty string default.",
                ],
                "explanation": "Pydantic validates incoming JSON fields at runtime and returns HTTP 422 automatically when required fields are missing or invalid.",
            }
        if "web layer" in ch_low or "service layer" in ch_low or "data layer" in ch_low or "layer" in ch_low:
            return {
                "project_name": "Mini Creature Management API",
                "step_number": chapter_order + 1,
                "milestone_title": f"Step {chapter_order + 1}: Modularize {topic_title}",
                "learning_objective": f"Enforce clean separation of concerns between web, service, and data layers for {topic_title}.",
                "deliverable": f"Keep HTTP routing in `web/`, business rules in `service/`, and storage queries in `data/` cleanly separated for {topic_title}.",
                "requirements": [
                    "Route `web_get_creature(name, service)` through `service.get_one(name)` without touching storage directly.",
                ],
                "starter_code": (
                    "# Clean layer call flow: web -> service -> data\n"
                    "class StubService:\n"
                    "    def get_one(self, name: str) -> dict:\n"
                    "        return {'name': name, 'source': 'service'}\n\n"
                    "def web_get_creature(name: str, service):\n"
                    "    return service.get_one(name)\n\n"
                    "print(web_get_creature('Yeti', StubService()))\n"
                ),
                "expected_output": "{'name': 'Yeti', 'source': 'service'}",
                "test_cases": [
                    {"description": "web_get_creature delegates to service.get_one", "assert_code": "assert web_get_creature('Bigfoot', StubService())['name'] == 'Bigfoot'"},
                ],
                "hints": [
                    "Injecting the service dependency makes unit testing the web layer trivial with a stub.",
                ],
                "explanation": "Layered architecture prevents database code from leaking into HTTP route handlers.",
            }
        return {
            "project_name": "Mini Creature Management API" if is_fastapi_course else f"{course_title} Capstone",
            "step_number": chapter_order + 1,
            "milestone_title": f"Apply {topic_title}",
            "learning_objective": f"Integrate {topic_title} cleanly into your modular application architecture.",
            "deliverable": f"Integrate concepts from {topic_title} into your modular application architecture.",
            "requirements": [
                f"Verify how {topic_title} interacts with upstream and downstream components.",
            ],
            "starter_code": None,
            "expected_output": None,
            "test_cases": [],
            "hints": [],
            "explanation": f"Applying {topic_title} consistently keeps your codebase maintainable as it grows.",
        }
