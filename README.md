# LearnForge AI

**LearnForge AI** is a local-first Adaptive Multi-Agent AI Learning Platform that transforms uploaded educational documents (`PDF`, `DOCX`, `TXT`, `PPTX`, `Markdown`) into structured courses, chapter-level lessons, SM-2 spaced-repetition flashcards, multi-format adaptive quizzes, a LangGraph-orchestrated Socratic AI Tutor, and real-time learning analytics.

---

## Architecture Overview

1. **Local-First Persistence**
   - **Relational Database**: Local SQLite (`backend/learnforge.db`) with `PRAGMA foreign_keys = ON` and `PRAGMA journal_mode = WAL`, managed via Alembic migrations.
   - **Document Storage**: Local filesystem (`backend/uploads/`) with UUID namespacing, extension filtering, magic-byte signature validation, and SHA-256 duplicate-upload protection.
   - **Vector Store**: Persistent local ChromaDB (`backend/chroma_data/`) indexed with `sentence-transformers/all-MiniLM-L6-v2` embeddings and strict per-user metadata filtering.

2. **LangGraph Multi-Agent Orchestration**
   - Built with compiled `langgraph.graph.StateGraph` and `MemorySaver` checkpoints in `backend/app/ai/graphs/learning_graph.py`:
     - `SupervisorAgent`: Validates inputs, routes workflows, inspects agent outputs, manages retries, and coordinates enrichment.
     - `DocumentAgent`: Classifies domains, detects content profiles (code/math/theory), and discovers chapter/section outlines.
     - `ContentAgent`: Builds grounded modular course outlines aligned strictly to document structure.
     - `LessonAgent`: Synthesizes structured Markdown lessons with `LessonQualityGate` checks.
     - `TutorAgent`: Handles intent classification, follow-up contextualization, RAG retrieval, and Socratic explanations.
     - `ResourceAgent`: Separates verified document page references from clearly labeled general study guidance.
     - `FlashcardAgent`: Produces deduplicated active-recall flashcards paired with SM-2 spaced-repetition scheduling.
     - `QuestionAgent` & `AssessmentAgent`: Support MCQ, True/False, and Short-Answer assessments and track weak concepts.
     - `AnalyticsAgent`: Computes real completion rates, SM-2 due queues, weekly activity, weak topics, and recommendations.

3. **Hybrid AI Model Routing**
   - `ModelRouter` routes tasks between **Local Ollama** (`LOCAL_MODEL=qwen2.5:3b` by default) and **OpenAI** (`CLOUD_MODEL=gpt-4o-mini`), probes cloud credentials/quota on startup, falls back cleanly to local Ollama on quota/auth errors, and tracks latency (`avg` / `p95`) and token estimates without exposing secrets.

---

## Quick Start (Local Development)

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- [Ollama](https://ollama.ai) (recommended model: `ollama pull qwen2.5:3b` or run `.\setup_ollama.ps1`)

### Run Both Servers
```powershell
python run_servers.py
```
- **Frontend UI**: `http://127.0.0.1:5173`
- **Backend API**: `http://127.0.0.1:8000`
- **Swagger Docs**: `http://127.0.0.1:8000/docs`
- **Health Telemetry**: `http://127.0.0.1:8000/health`

### Manual Setup

#### Backend
```powershell
cd backend
pip install -r requirements.txt
copy .env.example .env
python -m alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### Frontend
```powershell
cd frontend
npm install
npm run dev
```

#### Production Frontend Build
```powershell
cd frontend
npm run build
```

---

## Automated Testing

Run the backend pytest suite (unit, RAG evaluation, security/backup, multi-agent LangGraph, and API tests):
```powershell
cd backend
python -m pytest -v
```

Run frontend type-checking and production bundling:
```powershell
cd frontend
npx tsc --noEmit
npm run build
```

---

## Docker Deployment

Configure environment variables (`SECRET_KEY`, optional `OPENAI_API_KEY`, `LOCAL_MODEL=qwen2.5:3b`) and start both backend + nginx frontend:
```powershell
docker compose up --build
```
- Frontend served on `http://localhost:5173` (proxies `/api` and `/health` to `backend:8000`)
- Backend runs `alembic upgrade head` cleanly before launching Uvicorn without `--reload`.

---

## SQLite Online Backup & Restore
```powershell
cd backend
python backup_db.py --action backup
python backup_db.py --action restore --source backups/<snapshot>.db
```

---

## Key API Endpoints (`/api/v1`)
- `POST /auth/register`, `POST /auth/login`, `GET /users/me`, `PUT /users/me`
- `POST /documents/upload`, `GET /documents`, `GET /documents/{id}`, `POST /documents/{id}/reprocess`, `DELETE /documents/{id}`
- `POST /courses/generate`, `GET /courses`, `GET /courses/{id}`, `DELETE /courses/{id}`
- `GET /lessons/{id}`, `POST /lessons/{id}/toggle-complete`, `POST /lessons/{id}/regenerate`
- `POST /tutor/chat`, `GET /tutor/history`, `DELETE /tutor/history`, `GET /tutor/suggestions`
- `POST /flashcards/generate`, `GET /flashcards`, `POST /flashcards/{id}/review`, `DELETE /flashcards/{id}`
- `POST /quizzes/generate`, `GET /quizzes`, `GET /quizzes/{id}`, `POST /quizzes/{id}/submit`, `GET /quizzes/{id}/attempts`, `DELETE /quizzes/{id}`
- `GET /progress/stats`
- `GET /health`

---

## Production Checklist (Clean Machine)
1. Install Python 3.11+, Node.js 18+, and Ollama (`ollama pull qwen2.5:3b`).
2. Copy `backend/.env.example` to `backend/.env` and set:
   - `ENVIRONMENT=production`
   - `DEBUG=False`
   - `SECRET_KEY=<64-char-random-hex>` (startup fails if the dev secret is left in production)
   - `CORS_ORIGINS=["https://your-domain.com"]`
3. Run database migrations: `cd backend && python -m alembic upgrade head`.
4. Build the frontend: `cd frontend && npm ci && npm run build` (served automatically by FastAPI from `frontend/dist` or via Nginx/Docker).
5. Start the backend without reload: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000` (`/docs` and `/redoc` are disabled automatically in production).

---

## Known Limitations & Environment Notes
- On systems without a dedicated GPU, local Ollama inference latency scales with model parameter count (`qwen2.5:3b` is significantly faster on CPU than 7B/8B models).
- Scanned image-only PDFs require local Tesseract OCR language packs for PyMuPDF OCR extraction.
- In production deployments, always override `SECRET_KEY` and configure HTTPS behind a reverse proxy.
