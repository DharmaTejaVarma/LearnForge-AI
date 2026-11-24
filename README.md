# LearnForge AI 🚀

**LearnForge AI** is an intelligent, personalized, local-first learning platform that transforms uploaded educational documents (PDF and DOCX) into structured courses, interactive chapter lessons, active-recall flashcard decks, adaptive quizzes, and an interactive 1-on-1 Socratic AI Tutor.

---

## 🏛️ System Architecture Principles

1. **Local-First Storage**:
   - **Primary Database**: Local SQLite (`backend/learnforge.db`) with Foreign Key constraints (`PRAGMA foreign_keys = ON;`) and Write-Ahead Logging (`PRAGMA journal_mode = WAL;`) enabled for high-concurrency read/write transactions.
   - **File Storage**: Local filesystem (`backend/uploads/`) with strict UUID-based namespacing, MIME-type validation, and path-traversal prevention.
   - **Vector Database**: Persistent local ChromaDB (`backend/chroma_data/`) storing dense text embeddings and per-user/document metadata.
   - *Strict constraint: Zero external database SaaS, no PostgreSQL, and no hosted vector databases.*

2. **Hybrid AI Architecture**:
   - **Local AI**: [Ollama](https://ollama.ai) running local **Qwen** models (`qwen2.5:7b` / `qwen2.5:3b`) for routine tasks (summaries, flashcards, basic MCQs).
   - **Cloud AI**: **OpenAI API** (`gpt-4o-mini` / `gpt-4o`) for advanced reasoning, in-depth lesson generation, and nuanced Socratic tutoring.
   - **Embeddings**: Local dense vector embeddings via **Sentence Transformers** (`sentence-transformers/all-MiniLM-L6-v2`).
   - **Model Router**: Centralized intelligent model router managing fallback, latency tracking, and task-based routing rules.

3. **Multi-Agent Orchestration**:
   - Built with **LangGraph** & **LangChain** following a Supervisor pattern with specialized worker agents (Document Understanding, Content Structuring, Lesson Generation, Question Generation, Flashcard, Assessment, and Tutor).

---

## 📁 Repository Structure

```
LearnForge AI/
│
├── frontend/                     # React + TypeScript + Vite Client Application
│   ├── public/                   # Static assets
│   ├── src/
│   │   ├── assets/               # Images, SVGs, icons
│   │   ├── components/           # Reusable UI component library
│   │   │   ├── common/           # Buttons, inputs, modal dialogs, loaders
│   │   │   ├── layout/           # Navbar, sidebar, containers
│   │   │   ├── dashboard/        # Metrics, statistics, recent activities
│   │   │   ├── courses/          # Course cards, outline viewer
│   │   │   ├── lessons/          # Lesson reader, markdown display
│   │   │   ├── tutor/            # AI tutor chat UI with source drawer
│   │   │   ├── flashcards/       # 3D Flip cards, review deck
│   │   │   └── quizzes/          # Quiz taker, timer, question review
│   │   ├── pages/                # High-level route views
│   │   ├── hooks/                # Custom React hooks (useAuth, etc.)
│   │   ├── services/             # Axios API client services
│   │   ├── context/              # Global React contexts (AuthContext)
│   │   ├── types/                # TypeScript interfaces
│   │   ├── utils/                # Helper utilities and formatters
│   │   ├── routes/               # App routing configuration
│   │   ├── App.tsx               # Main application component
│   │   └── main.tsx              # Application entry point
│   ├── .env.example              # Frontend environment template
│   └── package.json              # Frontend npm dependencies
│
├── backend/                      # FastAPI Python Application
│   ├── app/
│   │   ├── api/
│   │   │   ├── dependencies/     # Dependency injection (Auth, DB session)
│   │   │   └── v1/               # Versioned REST API endpoints
│   │   │       ├── auth.py       # Authentication & JWT tokens
│   │   │       ├── users.py      # User profile management
│   │   │       ├── documents.py  # File upload & ingestion endpoints
│   │   │       ├── courses.py    # Course generation & outlines
│   │   │       ├── lessons.py    # Lesson generation & content
│   │   │       ├── tutor.py      # AI Tutor chat & citations
│   │   │       ├── flashcards.py # Flashcard deck generation
│   │   │       ├── questions.py  # Question bank endpoints
│   │   │       ├── quizzes.py    # Quiz creation & grading
│   │   │       ├── progress.py   # Student learning telemetry & reports
│   │   │       └── health.py     # System health check
│   │   │
│   │   ├── core/                 # Core configs, security & exceptions
│   │   │   ├── config.py         # Pydantic BaseSettings
│   │   │   ├── security.py       # Password hashing & JWT helpers
│   │   │   ├── logging.py        # Structured application logging
│   │   │   └── exceptions.py     # Custom API error handlers
│   │   │
│   │   ├── db/                   # Database configuration & models
│   │   │   ├── database.py       # SQLAlchemy async engine (aiosqlite)
│   │   │   ├── base.py           # Declarative base metadata
│   │   │   └── models/           # ORM entity tables
│   │   │
│   │   ├── schemas/              # Pydantic request/response schemas
│   │   ├── repositories/         # Database access layer pattern
│   │   ├── services/             # Core business logic services
│   │   │
│   │   ├── ai/                   # AI, RAG & Multi-Agent orchestration
│   │   │   ├── models/           # Model router, local & cloud clients
│   │   │   ├── embeddings/       # Sentence Transformers embedding service
│   │   │   ├── rag/              # PyMuPDF/docx loaders, chunkers, ChromaDB
│   │   │   ├── agents/           # Specialized LangGraph agents
│   │   │   ├── graphs/           # StateGraph workflow definitions
│   │   │   └── prompts/          # Structured system prompts
│   │   │
│   │   ├── tasks/                # Background async tasks
│   │   ├── utils/                # Helper functions & utilities
│   │   └── main.py               # FastAPI entry point
│   │
│   ├── migrations/               # Alembic database migrations
│   ├── tests/                    # Pytest test suite (100% passing)
│   ├── uploads/                  # Local storage for uploaded documents
│   ├── chroma_data/              # Local ChromaDB persistent storage
│   ├── backups/                  # Online SQLite backup snapshots
│   ├── backup_db.py              # SQLite online backup & restore tool
│   ├── verify_env.py             # Phase 0 Environment verification script
│   ├── requirements.txt          # Pinned Python dependencies
│   ├── .env.example              # Backend environment template
│   └── .env                      # Active backend environment
│
├── docker/
│   └── Dockerfile.backend        # Backend containerization
│
├── docker-compose.yml            # Local container orchestration
├── .gitignore                    # Git exclusions
├── README.md                     # Project documentation
└── IMPLEMENTATION_PLAN.md        # Master phase-by-phase implementation checklist
```

---

## ⚡ Quick Start (Run Both Servers in 1 Command!)

You can start **both** the FastAPI Backend and the Vite Frontend simultaneously with any of these single commands from the project root:

```powershell
# Option 1: Native Python Runner (Recommended)
python run_servers.py

# Option 2: npm script
npm run dev

# Option 3: PowerShell script
.\start.ps1

# Option 4: Windows double-click
start.bat
```

- **Frontend App**: `http://localhost:5173`
- **FastAPI API Root**: `http://localhost:8000`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`
- **System Health**: `http://localhost:8000/health`
- Press `Ctrl + C` in your terminal to shut down both servers cleanly.

---

### Manual Setup (Run Individually)

#### 1. Prerequisites
- **Python**: 3.11+ (tested on Python 3.11.6)
- **Node.js**: v18+ (tested on Node.js v22.17.0) & npm
- **Ollama**: (Optional for local AI) [Download Ollama](https://ollama.ai)

#### 2. Backend Setup
```powershell
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Linux / macOS:
# source venv/bin/activate

# Install pinned dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start FastAPI server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

FastAPI interactive Swagger documentation is available at:
`http://localhost:8000/docs`

### 3. Frontend Setup
```powershell
# In a new terminal, navigate to frontend
cd frontend

# Install npm packages
npm install

# Start Vite development server
npm run dev
```
The web application opens at `http://localhost:5173`.

---

## 🧪 Automated Testing & Verification

LearnForge AI includes comprehensive automated tests covering all modules:
- Authentication & JWT token security
- Document lifecycle & PyMuPDF / python-docx extraction
- SQLite PRAGMAs (WAL mode, Foreign Keys)
- RAG pipeline: text normalization, recursive chunking, ChromaDB indexing, semantic retrieval, and source citation extraction
- Multi-agent learning tools: AI Tutor, Flashcards, Questions, Quizzes, Progress calculation
- Security: Path-traversal sanitization, disallowed filetype rejection, and strict cross-user data isolation
- SQLite online backup & integrity verification

### Run Full Pytest Suite:
```powershell
cd backend
.\venv\Scripts\pytest.exe -v
```
*(All 13 integration and unit tests pass with 100% success rate)*

---

## 💾 Local SQLite Backup & Restore

To take a consistent online backup of the SQLite database:
```powershell
cd backend
python backup_db.py --action backup
```
This utility:
1. Executes `PRAGMA wal_checkpoint(TRUNCATE);` to flush WAL pages into the database file.
2. Performs an atomic online backup via Python's native `sqlite3.Connection.backup()`.
3. Validates the backup integrity using `PRAGMA quick_check;` and `PRAGMA foreign_key_check;`.

To restore from a backup:
```powershell
python backup_db.py --action restore --source backups/learnforge_backup_YYYYMMDD_HHMMSS.db
```

---

## 🤖 Hybrid AI Configuration

Configure the models in `backend/.env`:
```ini
# Hybrid AI Settings
LOCAL_MODEL=qwen2.5:7b
CLOUD_MODEL=gpt-4o-mini
OLLAMA_BASE_URL=http://localhost:11434
OPENAI_API_KEY=your_openai_api_key_here
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

1. **Local Ollama Model**:
   ```powershell
   ollama pull qwen2.5:7b
   ```
2. **Model Routing Rules**:
   - `summary`, `flashcard`, `mcq_routine`: Routed to Local Qwen model.
   - `lesson_generation`, `complex_reasoning`, `socratic_tutor`: Routed to Cloud OpenAI model.
   - Automatic fallback: If local Ollama is offline or unavailable, requests automatically fall back gracefully to Cloud OpenAI if an API key is configured.

---

## 🌐 API Endpoint Catalog

| Endpoint | Method | Description |
|---|---|---|
| `/health` | `GET` | System health check (DB connectivity, SQLite pragmas, status) |
| `/api/v1/auth/register` | `POST` | User registration with bcrypt password hashing |
| `/api/v1/auth/login` | `POST` | User authentication returning JWT bearer token |
| `/api/v1/users/me` | `GET` | Current authenticated user profile |
| `/api/v1/documents/upload` | `POST` | Secure document upload (PDF/DOCX), text extraction & RAG indexing |
| `/api/v1/documents` | `GET` | List user's uploaded documents |
| `/api/v1/documents/{id}` | `DELETE` | Delete document from filesystem and purge ChromaDB vectors |
| `/api/v1/courses/generate` | `POST` | AI-generated structured course from document context |
| `/api/v1/courses` | `GET` | List user's generated courses |
| `/api/v1/courses/{id}` | `GET` | Get detailed course structure (chapters, topics, lessons) |
| `/api/v1/lessons/{id}` | `GET` | Read formatted lesson content with key concepts & takeaways |
| `/api/v1/tutor/chat` | `POST` | 1-on-1 Socratic AI Tutor with RAG citations and page numbers |
| `/api/v1/flashcards/generate` | `POST` | Generate active recall flashcards for course or lesson |
| `/api/v1/flashcards/course/{id}` | `GET` | List flashcards for course |
| `/api/v1/flashcards/{id}/review` | `POST` | Mark flashcard reviewed/mastered |
| `/api/v1/questions/generate` | `POST` | Generate practice questions (MCQ, conceptual, descriptive) |
| `/api/v1/quizzes/generate` | `POST` | Generate an adaptive assessment quiz |
| `/api/v1/quizzes/{id}/submit` | `POST` | Submit quiz answers for automated grading and feedback |
| `/api/v1/progress/summary` | `GET` | Get learning analytics, course completion %, and mastery |
| `/api/v1/progress/report/export` | `GET` | Download personalized learning summary report |

---

## 🛡️ Security & Privacy Notice
- All user files are stored exclusively on the local filesystem (`backend/uploads/`).
- Primary relational data is stored exclusively in local SQLite (`backend/learnforge.db`).
- Embeddings are computed locally using Sentence Transformers and stored in local ChromaDB (`backend/chroma_data/`).
- External network requests occur only when cloud LLM features are explicitly called using your configured `OPENAI_API_KEY`.
