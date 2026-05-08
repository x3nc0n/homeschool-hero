# Homeschool Hero — MVP Architecture

**Author:** Egon (Lead)
**Date:** 2026-05-08
**Status:** Proposed

---

## 1. Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Backend** | Python 3.12 + FastAPI | Mature async framework, excellent for file handling and AI integration. Huge ecosystem. Easy for a non-developer to read/debug if needed. |
| **Frontend** | React 18 + Vite | Fast dev experience, massive community, easy to bundle as static assets. |
| **UI Library** | shadcn/ui (Tailwind CSS) | Pre-built accessible components, no runtime dependency, looks professional out of the box. |
| **Database** | PostgreSQL 16 | Rock-solid, excellent JSON support for flexible quiz schemas, great with SQLAlchemy. |
| **ORM** | SQLAlchemy 2.0 + Alembic | Type-safe models, mature migration tooling. |
| **File Storage** | Local filesystem (Docker volume) | Simplest for self-hosted MVP. Upload path: `/data/uploads/`. |
| **OCR** | Tesseract (pytesseract) | Free, open-source, runs locally. No API keys needed. |
| **AI Grading** | Ollama (local LLM) OR OpenAI API (optional) | Ollama keeps it self-hosted and free. OpenAI support as optional upgrade for better accuracy. |
| **Task Queue** | SQLAlchemy-based job table | No Redis/Celery complexity for MVP. Background worker polls a `grading_jobs` table. |
| **Auth** | Simple PIN/password per family | Single-family MVP. One admin password stored as bcrypt hash. No OAuth complexity. |
| **Containerization** | Docker Compose (3 services) | `app` (FastAPI + worker), `db` (Postgres), `ollama` (optional AI). |

### Why NOT these alternatives:
- **Django**: Heavier, more opinionated than needed. FastAPI's async is better for file uploads + AI calls.
- **SQLite**: Can't handle concurrent writes well (worker + web server). Postgres is worth the container.
- **Next.js**: Full-stack JS adds complexity. Separate API + SPA is cleaner for this use case.
- **Redis/Celery**: Overkill for MVP. A simple polling worker on a DB table is sufficient at this scale.

---

## 2. Project Structure

```
homeschool-hero/
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── docs/
│   └── architecture.md
├── backend/
│   ├── main.py                  # FastAPI app entrypoint
│   ├── config.py                # Settings (env vars)
│   ├── database.py              # DB engine + session
│   ├── models/                  # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── assignment.py
│   │   ├── submission.py
│   │   ├── grade.py
│   │   ├── quiz.py
│   │   ├── student.py
│   │   └── grading_job.py
│   ├── routers/                 # API route handlers
│   │   ├── __init__.py
│   │   ├── assignments.py
│   │   ├── submissions.py
│   │   ├── grades.py
│   │   ├── quizzes.py
│   │   ├── students.py
│   │   ├── grading.py
│   │   └── auth.py
│   ├── schemas/                 # Pydantic request/response models
│   │   └── ...
│   ├── services/                # Business logic
│   │   ├── ocr.py              # Tesseract integration
│   │   ├── ai_grader.py        # LLM grading logic
│   │   └── grading_worker.py   # Background job processor
│   ├── migrations/              # Alembic migrations
│   │   └── versions/
│   └── tests/
│       ├── conftest.py
│       ├── test_assignments.py
│       ├── test_submissions.py
│       ├── test_grading.py
│       └── ...
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── ui/             # shadcn components
│   │   │   ├── AssignmentList.tsx
│   │   │   ├── SubmissionUpload.tsx
│   │   │   ├── GradeBook.tsx
│   │   │   ├── QuizBuilder.tsx
│   │   │   ├── ReviewQueue.tsx
│   │   │   └── LoginForm.tsx
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Assignments.tsx
│   │   │   ├── Grades.tsx
│   │   │   ├── Quizzes.tsx
│   │   │   └── Review.tsx
│   │   ├── hooks/
│   │   ├── lib/
│   │   │   └── api.ts          # API client
│   │   └── types/
│   └── public/
└── data/                        # Docker volume mount point
    └── uploads/
```

---

## 3. Data Model

### Entities

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│   Student    │     │   Assignment     │     │    Subject   │
├──────────────┤     ├──────────────────┤     ├──────────────┤
│ id (PK)      │     │ id (PK)          │     │ id (PK)      │
│ name         │     │ title            │     │ name         │
│ created_at   │     │ subject_id (FK)  │     │ color        │
└──────────────┘     │ description      │     └──────────────┘
                     │ due_date         │
                     │ status           │  ← (pending, complete, graded)
                     │ created_at       │
                     └──────────────────┘

┌──────────────────────┐     ┌──────────────────┐
│     Submission       │     │      Grade       │
├──────────────────────┤     ├──────────────────┤
│ id (PK)              │     │ id (PK)          │
│ assignment_id (FK)   │     │ submission_id(FK)│
│ student_id (FK)      │     │ student_id (FK)  │
│ file_path            │     │ score            │
│ file_type            │     │ max_score        │
│ ocr_text             │     │ letter_grade     │
│ uploaded_at          │     │ notes            │
└──────────────────────┘     │ graded_by        │  ← ('human', 'ai', 'ai+human')
                             │ ai_confidence    │
                             │ created_at       │
                             └──────────────────┘

┌──────────────────────┐     ┌──────────────────┐
│       Quiz           │     │   QuizAttempt    │
├──────────────────────┤     ├──────────────────┤
│ id (PK)              │     │ id (PK)          │
│ title                │     │ quiz_id (FK)     │
│ subject_id (FK)      │     │ student_id (FK)  │
│ questions (JSONB)    │     │ answers (JSONB)  │
│ created_at           │     │ score            │
└──────────────────────┘     │ max_score        │
                             │ completed_at     │
                             └──────────────────┘

┌──────────────────────┐
│    GradingJob        │
├──────────────────────┤
│ id (PK)              │
│ submission_id (FK)   │
│ status               │  ← (queued, processing, needs_review, complete, failed)
│ ocr_result           │
│ ai_grade             │
│ ai_feedback          │
│ ai_confidence        │
│ error_message        │
│ created_at           │
│ completed_at         │
└──────────────────────┘
```

### Key Relationships
- A **Student** has many **Submissions** and **QuizAttempts**
- An **Assignment** belongs to a **Subject** and has many **Submissions**
- A **Submission** has one **Grade** and one **GradingJob**
- A **Quiz** belongs to a **Subject** and has many **QuizAttempts**
- **Quiz.questions** is JSONB: `[{type: "multiple_choice"|"short_answer"|"true_false", prompt: "...", options: [...], correct_answer: "..."}]`

---

## 4. Auto-Grading Pipeline

### Flow

```
Upload Photo/PDF
       │
       ▼
┌─────────────────┐
│  Store file to  │
│  /data/uploads/ │
│  Create record  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Create GradingJob│
│ status: queued  │
└────────┬────────┘
         │
         ▼  (Background worker picks up)
┌─────────────────┐
│   OCR Stage     │
│  (Tesseract)    │
│  Extract text   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   AI Grading    │
│  (Ollama/OpenAI)│
│  Compare to     │
│  answer key     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│  Confidence Check           │
│  confidence >= 0.8 → auto   │
│  confidence < 0.8  → review │
└────────┬────────────────────┘
         │
    ┌────┴────┐
    ▼         ▼
 Auto-      Human
 graded     Review
 (done)     Queue
```

### OCR Details
- **Tesseract** via `pytesseract` for text extraction
- Pre-processing: convert to grayscale, deskew, threshold (using Pillow)
- Store extracted text in `submission.ocr_text` for searchability

### AI Grading Details
- **Input to LLM:** Assignment description + answer key (if provided) + extracted OCR text
- **Prompt template:** Structured prompt asking for: score (0-100), confidence (0-1), feedback text
- **Model options:**
  - Default: Ollama with `llama3` or `mistral` (free, local)
  - Optional: OpenAI `gpt-4o-mini` (set `OPENAI_API_KEY` in .env)
- **Confidence threshold:** 0.8 — below this, the grade goes to the human review queue
- **Fallback:** If AI is unavailable, job stays in `needs_review` for manual grading

### Human Review Queue
- Parent sees AI-suggested grade + feedback + original image side-by-side
- Can approve, modify grade, or reject and re-grade manually
- All final grades record `graded_by` field for audit trail

---

## 5. MVP Scope

### ✅ IN for MVP

| Feature | Details |
|---------|---------|
| Student profiles | Add/edit students (children) |
| Subject management | Create subjects (Math, Science, etc.) |
| Assignment CRUD | Create assignments, set due dates, mark status |
| File upload | Upload PDF/photos of completed work |
| Manual grading | Enter grades directly |
| Grade book view | View all grades by student/subject, calculate averages |
| Quiz builder | Create multiple-choice and short-answer quizzes |
| Quiz taking | Student takes quiz (parent administers), auto-scored |
| OCR extraction | Extract text from uploaded work |
| AI grading | Auto-grade with confidence scoring |
| Review queue | Approve/modify AI grades |
| Simple auth | Single password/PIN for the family |
| Docker deployment | `docker compose up` and it works |
| Responsive UI | Works on tablet (common for homeschool parents) |

### ❌ OUT for MVP (Future)

| Feature | Why deferred |
|---------|-------------|
| Multi-family / multi-tenant | Adds auth complexity. Single family first. |
| Curriculum planning / calendar | Nice to have, not core grading flow. |
| Report cards / transcript generation | Can add once grade data exists. |
| Email notifications | No external service dependencies for MVP. |
| Student-facing portal | Students work on paper; parents manage everything. |
| Cloud storage (S3/GCS) | Local volumes are simpler for self-hosted. |
| Mobile app | Responsive web is sufficient for MVP. |
| Handwriting recognition training | Stock Tesseract is good enough to start. |
| Multiple AI model comparison | One model path is enough for MVP. |

---

## 6. Work Breakdown

Ordered by dependency. Each task should be a PR-sized chunk.

| # | Task | Agent | Depends On | Est. |
|---|------|-------|------------|------|
| 1 | Project scaffolding: Docker, docker-compose, Dockerfile, .env.example, directory structure | Ray | — | S |
| 2 | Database models + Alembic migrations (all entities) | Ray | 1 | M |
| 3 | Backend API: Students + Subjects CRUD | Ray | 2 | S |
| 4 | Backend API: Assignments CRUD + status management | Ray | 2 | S |
| 5 | Backend API: File upload + storage | Ray | 2 | M |
| 6 | Backend API: Grades CRUD + grade book queries | Ray | 2 | M |
| 7 | Backend API: Quiz CRUD + quiz attempt scoring | Ray | 2 | M |
| 8 | Auth middleware (PIN/password, bcrypt, session token) | Ray | 1 | S |
| 9 | Frontend scaffolding: Vite + React + shadcn/ui + routing | Venkman | — | S |
| 10 | Frontend: Login page | Venkman | 8, 9 | S |
| 11 | Frontend: Dashboard (summary view) | Venkman | 9 | M |
| 12 | Frontend: Student & Subject management pages | Venkman | 3, 9 | S |
| 13 | Frontend: Assignment list + create/edit | Venkman | 4, 9 | M |
| 14 | Frontend: File upload component (drag & drop, camera) | Venkman | 5, 9 | M |
| 15 | Frontend: Grade book view (table, averages, filters) | Venkman | 6, 9 | M |
| 16 | Frontend: Quiz builder + quiz-taking UI | Venkman | 7, 9 | L |
| 17 | OCR service: Tesseract integration + image preprocessing | Ray | 5 | M |
| 18 | AI grading service: Ollama/OpenAI integration + prompt engineering | Ray | 17 | L |
| 19 | Grading worker: Background job processor | Ray | 18 | M |
| 20 | Frontend: Human review queue (side-by-side view) | Venkman | 19, 9 | M |
| 21 | Backend tests: API endpoints (pytest) | Winston | 3-8 | M |
| 22 | Backend tests: Grading pipeline (mocked OCR + AI) | Winston | 17-19 | M |
| 23 | Frontend tests: Component tests (Vitest + Testing Library) | Winston | 10-16 | M |
| 24 | Integration tests: Upload → OCR → Grade → Review flow | Winston | 19, 20 | L |
| 25 | Docker polish: health checks, volume permissions, first-run setup | Ray | All | S |

**Size key:** S = small (< 1 day), M = medium (1-2 days), L = large (2-4 days)

---

## 7. Configuration & Environment

```env
# .env.example
POSTGRES_USER=homeschool
POSTGRES_PASSWORD=changeme
POSTGRES_DB=homeschool_hero
DATABASE_URL=postgresql://homeschool:changeme@db:5432/homeschool_hero

# Auth
FAMILY_PASSWORD=changeme

# AI Grading (optional — Ollama is default)
AI_PROVIDER=ollama          # or "openai"
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=llama3
OPENAI_API_KEY=             # only if AI_PROVIDER=openai

# Grading
CONFIDENCE_THRESHOLD=0.8
UPLOAD_DIR=/data/uploads
```

### Docker Compose Services

```yaml
services:
  app:        # FastAPI + background worker (single process with threading)
  db:         # PostgreSQL 16
  ollama:     # Ollama LLM server (optional, can be disabled)
```

---

## 8. Key Architecture Decisions

1. **Single container for app + worker** — The grading worker runs as a background thread in the FastAPI process. No separate container needed for MVP scale.

2. **JSONB for quiz questions** — Flexible schema for different question types without migration headaches.

3. **Confidence-based routing** — AI grades above 0.8 confidence auto-approve; below goes to human review. Threshold is configurable.

4. **Ollama as default AI** — Zero API cost, runs locally, no account signup. Parents can optionally plug in OpenAI for better accuracy.

5. **No separate file server** — Files served directly by FastAPI from the Docker volume. Simple, no nginx needed for MVP.

6. **Session-based auth** — HTTP-only cookie with a signed session token. No JWT complexity for a single-family app.

---

*This document is the source of truth for MVP implementation. All agents should reference it for scope and technical decisions.*
