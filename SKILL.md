# SAT Exam System — Skill Reference

## Architecture

```
fastapi backend (Python, async)     react frontend (TypeScript)
         │                                  │
    /api/v1/*   ← proxy →   vite dev server (:5173)
         │
    sqlite (dev) / postgresql (prod)
```

## Quick Start

```bash
# Terminal 1 — Backend
cd /Users/yang/pdf-parser/sat-exam
source .venv/bin/activate
export DATABASE_URL="sqlite+aiosqlite:///./sat_exam.db"
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2 — Frontend
cd /Users/yang/pdf-parser/sat-exam/frontend
npm run dev
```

- Backend: http://localhost:8000 → redirects to /api/docs (Swagger)
- Frontend: http://localhost:5173 → React SPA
- Admin login: `admin@sat-exam.com` / `admin123`
- Student login: `student@test.com` / `test123`

Or use the one-shot script: `bash run.sh` (starts backend + seeds admin).

## Database

- **Dev**: SQLite at `sat_exam.db` (auto-created, no Docker needed)
- **Prod**: PostgreSQL via `docker-compose.yml` (`docker compose up -d db redis`)
- Schema: SQLAlchemy ORM with `Mapped[]` style, 18 tables
- Migrations: Alembic (`alembic.ini`), but SQLite dev uses auto-create via Base.metadata
- Schema changes for SQLite: run manual `ALTER TABLE` — e.g. `ALTER TABLE users ADD COLUMN grade VARCHAR`

## File Structure

```
sat-exam/
├── app/                    # FastAPI application
│   ├── main.py             # App factory, router mounting, CORS, static files
│   ├── config.py           # YAML + env var settings
│   ├── database.py         # AsyncSession factory
│   ├── dependencies.py     # Auth guards (get_current_user, require_role)
│   ├── models.py           # 18 SQLAlchemy ORM models (all in one file)
│   ├── auth/               # JWT auth, role management, user CRUD
│   │   ├── router.py       # /auth/login, /auth/refresh, /admin/users/*
│   │   ├── service.py      # Auth logic, user mgmt, status toggle, delete
│   │   ├── schemas.py      # Request/response models
│   │   └── utils.py        # JWT create/verify, bcrypt hashing
│   ├── upload/             # PDF upload + image upload
│   │   ├── router.py       # /uploads (PDF), /uploads/images (images)
│   │   ├── service.py      # File storage, dedup, parse job enqueue
│   │   └── schemas.py
│   ├── question/           # Question CRUD + versioning
│   │   ├── router.py       # /questions CRUD, /status, /bulk, /vocabulary
│   │   ├── service.py      # Versioning, publish guard, bulk ops, status workflow
│   │   └── schemas.py
│   ├── exam/               # Exam blueprints + runtime engine
│   │   ├── router.py       # /exams CRUD, /validate, /publish
│   │   ├── attempt_router.py # /exams/{id}/attempts, /attempts/{id}/*
│   │   ├── runtime.py      # Section-adaptive engine: materialize, route, grade, score
│   │   ├── service.py      # Pool validation, publish
│   │   └── schemas.py
│   ├── result/             # Result analysis
│   │   └── router.py       # /results/me/trends, /attempts/{id}/analysis
│   ├── practice/           # Practice plans + execution
│   │   ├── router.py       # /practice/plans, /tasks/*
│   │   └── service.py      # Plan generation, task execution
│   └── plan/               # (stub)
├── frontend/src/           # React SPA (Vite + TypeScript + Tailwind)
│   ├── App.tsx             # Router, ProtectedRoute, all routes
│   ├── api.ts              # Axios client, JWT interceptor, all endpoints
│   ├── AuthContext.tsx      # Login/logout state, token management
│   ├── types.ts            # TypeScript interfaces
│   ├── components/
│   │   ├── KatexRenderer.tsx  # Renders HTML with \(...\) LaTeX via KaTeX
│   │   └── FormulaEditor.tsx  # LaTeX modal: type, live preview, insert
│   └── pages/
│       ├── LoginPage.tsx     # Login form, redirect on success
│       ├── Layout.tsx        # Sidebar nav, role-based menu, logout
│       ├── admin/
│       │   ├── Dashboard.tsx
│       │   └── Users.tsx     # Create/edit/toggle/delete users, password confirm
│       ├── editor/
│       │   ├── Dashboard.tsx
│       │   ├── Questions.tsx  # Question list + filters + bulk actions + detail modal
│       │   ├── QuestionEditor.tsx # TipTap rich editor, formula modal, preview panel
│       │   └── Exams.tsx     # Exam list + publish
│       └── student/
│           ├── Dashboard.tsx
│           ├── Exams.tsx      # Available exams → Start
│           ├── ExamTake.tsx   # Question display, answer, timer, submit
│           ├── Results.tsx    # Score history
│           └── Practice.tsx   # Practice plans
├── scripts/                # CLI utilities
│   ├── import_questions.py  # OCR PDF → DB (uses parent project's ocr_parser.py)
│   ├── bulk_publish.py      # Tag + publish all drafts via DeepSeek LLM
│   ├── create_exam.py       # Create Digital SAT blueprint with selection rules
│   └── seed_skills.py       # Populate skill_vocabulary table
├── worker/                 # ARQ async worker (for parse jobs)
├── docker-compose.yml      # PostgreSQL + Redis
├── Dockerfile              # Backend container
├── run.sh                  # Quick-start with SQLite
├── config.yaml             # App settings
└── requirements.txt        # Python dependencies
```

## Key Pitfalls

### Async SQLAlchemy + lazy loading
Relationships MUST be eager-loaded with `selectinload()` in async mode. Accessing `exam.modules` or `module.selection_rules` without eager loading causes `MissingGreenlet` error.

**Fix**: All `get_*` functions in services use `select(Some).options(selectinload(...))`.

**All entity-dict helpers**: `_exam_to_dict()` in `exam/router.py` manually serializes relationships to avoid lazy-load.

### TipTap editor content sync
`useEditor({ content })` only reads content on mount. To react to prop changes, you MUST add a `useEffect`:

```ts
useEffect(() => {
  if (!editor) return;
  const currentHTML = editor.getHTML();
  if (content && content !== currentHTML) {
    editor.commands.setContent(content);
  }
}, [editor, content]);
```

### bcrypt version incompatibility
`passlib` + `bcrypt>=5` causes `(trapped) error reading bcrypt version`. The hash still works — this is cosmetic. Pin `bcrypt<5` for clean logs.

### Frontend API proxy
Vite dev server proxies `/api/*` to `localhost:8000`. The API client uses `baseURL: '/api/v1'`. Combined path: `/api/v1/auth/login` → proxied to `http://localhost:8000/api/v1/auth/login`.

### Pydantic schema types
- `options` field: stored as JSON list in DB, auto-parsed by SQLAlchemy to Python list
- Schema must use `Optional[list[ChoiceSchema]]`, NOT `Optional[dict]`
- `EmailStr` type requires `pip install pydantic[email]`

### Password reset
If admin password stops working, regenerate:

```bash
cd /Users/yang/pdf-parser/sat-exam
source .venv/bin/activate
export DATABASE_URL="sqlite+aiosqlite:///./sat_exam.db"
python3 -c "
import asyncio
from app.database import AsyncSessionLocal
from app.models import User
from app.auth.utils import hash_password
from sqlalchemy import select
async def fix():
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(User).where(User.email == 'admin@sat-exam.com'))
        admin = r.scalar_one_or_none()
        if admin:
            admin.password_hash = hash_password('admin123')
            await db.commit()
asyncio.run(fix())
print('done')
"
```

### GitHub push
Uses a GIT_ASKPASS helper script to avoid exposing the fine-grained PAT in command args. Token: `github_pat_11BH5CSGQ...`. Repo: `yangsonggt/sat-exam`.

## Question Status Workflow

```
draft → saved → reviewed → published
  ↑        ↑        ↑           ↓
  └────────┴────────┴──── archived
```

- Any state can transition to any other (no hard restrictions in backend)
- Publish guard: only `draft`/`saved`/`reviewed` can be published
- Status buttons appear in QuestionEditor for existing questions
- Colors: draft=gray, saved=blue, reviewed=yellow, published=green, archived=red

## Digital SAT Exam Structure

Each exam has 6 modules:
- Reading & Writing: Module 1 (base, 27Q, 32min) + Module 2 (easier/harder, 27Q, 32min)
- Math: Module 1 (base, 22Q, 35min) + Module 2 (easier/harder, 22Q, 35min)

M1 scored → routed to easier or harder M2 based on threshold (default: midpoint).
R&W fully completes before Math begins. All modules sequential.
