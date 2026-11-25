# Exam-Kraft

> **Pre-launch · Pre-build · Open-Source · Non-Commercial**  
> A full-stack Computer-Based Test (CBT) platform for Indian competitive exam coaching institutes (JEE / NEET / NTA pattern).

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack](#2-tech-stack)
3. [Current Status](#3-current-status)
4. [Architecture](#4-architecture)
5. [Features — Implemented](#5-features--implemented)
6. [Features — In Progress / Partial](#6-features--in-progress--partial)
7. [Known Issues & Bugs](#7-known-issues--bugs)
8. [Audit & Security Findings](#8-audit--security-findings)
9. [Completed Audit Batches](#9-completed-audit-batches)
10. [Pending Audit Batches](#10-pending-audit-batches)
11. [Getting Started (Dev)](#11-getting-started-dev)
12. [Demo Credentials](#12-demo-credentials)
13. [Project Structure](#13-project-structure)
14. [API Reference Overview](#14-api-reference-overview)
15. [Rebranding Notes](#15-rebranding-notes)
16. [Contributing](#16-contributing)
17. [License](#17-license)

---

## 1. Project Overview

**Exam-Kraft** is a self-hosted, multi-tenant examination management platform built for Indian coaching institutes running JEE, NEET, and NTA-pattern competitive exams. It provides:

- A **staff portal** for creating question banks, designing exams, assigning student batches, proctoring, publishing results, and viewing analytics.
- A **student CBT engine** matching the NTA/JEE interface: section tabs, question palette, timer, proctoring telemetry, offline caching, and auto-submit.
- A **multi-tenant backend** (Django REST) with organisation-scoped data isolation, JWT auth, attempt integrity locks, and a results evaluation pipeline.

This project was reconstructed clean-room as an open-source alternative. It is in **active pre-launch development** — not yet production-ready.

> **Non-commercial**: Exam-Kraft is released for educational and self-hosting use only. Commercial redistribution or SaaS resale is not permitted under the project licence.

---

## 2. Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.14 · Django 5.x · Django REST Framework |
| Auth | SimpleJWT (access + refresh tokens) |
| Task queue | Celery + Redis |
| DB (dev) | SQLite 3 |
| DB (prod recommended) | PostgreSQL 16+ |
| Cache / broker | Redis 7 |
| Frontend | React 18 · TypeScript · Vite 5 |
| Styling | Tailwind CSS v3 |
| Math rendering | KaTeX |
| Icons | Lucide React |
| Routing | React Router v6 |
| HTTP client | Axios |
| Reverse proxy | Nginx |
| Containerisation | Docker Compose |
| Testing (backend) | Django test runner · pytest |
| Testing (frontend) | Vitest (unit), Zen browser swarm (integration) |

---

## 3. Current Status

| Area | Status | Notes |
|------|--------|-------|
| Backend codebase | ✅ Complete | M1–M5 milestones done |
| Frontend codebase | ✅ Complete | All pages implemented |
| Auth & login | ✅ Working | Role-aware redirect, CSRF fixed |
| Staff portal | ✅ Working | All CRUD pages functional |
| Student CBT engine | ✅ Working | All 8 question types supported |
| Math rendering (KaTeX) | ✅ Fixed | Replaces broken custom parser |
| NTA numerical input | ✅ Fixed | Full keyboard + on-screen numpad |
| Offline sync | ✅ Fixed | Queue flush on reconnect + beforeunload |
| Timer drift | ✅ Fixed | Server-authoritative anchor on reconnect |
| Modal focus trap | ✅ Fixed | ARIA dialog, Escape key, focus restore |
| Answer-key exposure | ✅ Fixed | Delivery serializer strips correctness |
| Attempt integrity | ✅ Fixed | Row locks, unique active-attempt constraint |
| Proctoring | ✅ Fixed | Rate-capped event ingestion, attempt status gate |
| Report routing | ✅ Fixed | Uses attemptId not examId |
| Branding | ✅ Fixed | All "EZExam" strings → "Exam-Kraft" |
| Backend Batch 3 (Lifecycle) | ⏳ Pending | Awaiting user approval |
| Backend Batch 5 (Gateway) | ⏳ Pending | Security hardening pass |
| Backend Batch 6 (Tests/Docs) | ⏳ Pending | Final polish |
| PostgreSQL production | ⏳ Pending | Dev uses SQLite (see known issues) |
| PNG/Excel question upload | ❌ Unsupported | JSON authoring works; binary upload pending |
| Virtual calculator | ❌ Not built | Feature-request filed (HB-002) |
| Manual grading UI | ❌ Deferred | SUBJECTIVE grading is staff-side only via admin |
| HttpOnly refresh cookie | ❌ Deferred | JWT stored in localStorage for now |

---

## 4. Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Nginx Reverse Proxy               │
│           / → Vite (React SPA)                      │
│           /api/v1/ → Django (DRF)                   │
└───────────────┬─────────────────┬───────────────────┘
                │                 │
        ┌───────▼──────┐  ┌───────▼──────────┐
        │ React (Vite) │  │  Django REST API  │
        │  TypeScript  │  │  (Gunicorn/ASGI)  │
        │  Tailwind    │  │  Multi-tenant     │
        │  KaTeX       │  │  JWT Auth         │
        └──────────────┘  └────┬──────────────┘
                               │
                 ┌─────────────┼──────────────┐
                 │             │              │
          ┌──────▼───┐  ┌──────▼──┐   ┌──────▼──┐
          │ SQLite/  │  │  Redis  │   │  Celery  │
          │ Postgres │  │  Cache  │   │  Worker  │
          └──────────┘  └─────────┘   └──────────┘
```

**Multi-tenancy**: Every `Organisation` is data-isolated. All models carry a FK to `Organisation`. Auth middleware injects `request.tenant` from the JWT claim.

**Attempt engine** (`apps/engine`): Centralised `services.py` handles all CBT lifecycle — start, save-response, heartbeat, proctoring-event, submit — with row-level locking and a partial unique constraint preventing duplicate active attempts.

---

## 5. Features — Implemented

### Staff Portal
- **Question Bank**: Create banks, add MCQ (single/multi), Numerical, Single-Digit, True/False, One-Word, Subjective questions. LaTeX math in question text and options (KaTeX rendered).
- **Exam Builder**: Two-step creation wizard (paper + settings). Configure duration, proctoring, shuffle, section-skip, practice mode, window-switch limit, camera, PC-only.
- **Candidate Assignment**: Assign exams to batches and exam centres in a drawer panel.
- **Publish Exam**: One-click publish with confirmation. Validates question paper is locked.
- **Publish Results**: Staff manually triggers result publication per exam after window close.
- **Analytics Dashboard**: Cohort ranking table, percentile distribution, section-wise accuracy, score distribution histogram.
- **Student Management**: Bulk CSV import, enrolment to batches/centres, roll number assignment.
- **Batch & Centre Management**: Full CRUD with stream classification (JEE_MAIN, JEE_ADVANCED, NEET, OTHER).
- **Faculty Management**: Add faculty users, assign departments and subjects.
- **Notices**: Targeted announcements to batches/centres with time windows.

### Student CBT Engine
- **NTA-compliant interface**: Top header bar (timer, proctoring status, fullscreen, submit), section tab strip, question palette sidebar.
- **8 question types**:
  - `MCQ_SINGLE` — single correct option with radio-style pill
  - `MCQ_MULTI` — multiple correct options with checkbox-style pill
  - `NUMERICAL` — VirtualNumpad (on-screen + hardware keyboard)
  - `SINGLE_DIGIT` — numpad constrained to 0–9 single character
  - `TRUE_FALSE` — two pill buttons (True / False)
  - `ONE_WORD` — text input (single line, maxLength 100)
  - `SUBJECTIVE` — textarea (5 rows, resizable)
  - `CODING` — text area placeholder (manual grading path)
- **Question palette**: Colour-coded by status (Not Visited, Unanswered, Answered, Marked for Review, Answered + Marked).
- **Timer**: Server-authoritative countdown anchored via `performance.now()`. Syncs on every heartbeat (20s). Recovers from background tab throttling.
- **Offline mode**: Responses queued in `localStorage`. Flushed on `online` reconnect event and `beforeunload`.
- **Proctoring**: Window-blur / tab-switch detection → telemetry event POST. Auto-submit at configurable switch limit.
- **Heartbeat**: 20s interval syncs remaining time and checks termination flag.
- **Auto-submit**: Fires on timer expiry (`remaining_seconds === 0` checked both client and server via heartbeat `is_terminated`).
- **Submission flow**: Finish modal (with ARIA focus trap, Escape to close, focus restoration) → flushed pending queue → submit API → redirect to finish page.
- **Result report**: Candidate scorecard (score, percentile, rank, section accuracy) + question-by-question review (filtered by section / outcome).

### Auth & Security (Implemented Fixes)
- JWT access + refresh token (SimpleJWT)
- Role-aware login redirect: `STUDENT` → `/student`, staff → `/staff/exams`
- `LoginView` with `authentication_classes = []` to prevent CSRF cross-port issues in dev
- `CSRF_TRUSTED_ORIGINS` includes dev frontend ports
- Question-paper detail endpoint returns `403` for student role (CX-002 ✅)
- Delivery serializer strips `numerical_min`, `numerical_max`, `is_correct`, answer keys (CX-013 ✅)
- Attempt report gated behind result publication and exam window closure (CX-007 ✅)
- Partial unique constraint on active attempts (CX-004 ✅)
- Row-level locking on submit to prevent double-submission (CX-005 ✅)
- Proctoring event ingestion rate-capped, attempt-status gated (CX-003 ✅)
- Question lookup scoped to exam paper roster (CX-014 ✅)
- WebSocket consumer removed (unused, CX-001 ✅)

---

## 6. Features — In Progress / Partial

| Feature | Status | Detail |
|---------|--------|--------|
| PostgreSQL support | Partial | Code is PG-compatible; dev runs SQLite. 5 concurrency tests skipped (`@skipUnlessDB('postgresql')`) |
| Question image upload | Partial | `image_url` field exists; binary upload endpoint not implemented — use external URL |
| Exam result publication lifecycle | Partial | Batch 3 pending (CX-006 `finalize()` call, CX-011 subjective pending status, CX-012 date validation) |
| Delete protection | Partial | Batch 3 pending (CX-009 — block delete on live exams) |
| Virtual calculator | Not started | Feature-request (HB-002) — toggle panel, draggable, NTA numerical questions only |
| Login rate limiting | Not started | Batch 5 (CX-015 — `django-ratelimit`, 5 attempts/60s per IP) |
| HttpOnly refresh cookie | Deferred | Currently in `localStorage`; HttpOnly migration is Batch 7 |
| Question shuffling | Deferred | Shuffle flag exists on exam model; delivery randomisation not implemented (CX-013 part 2) |
| Pagination (exam list) | Deferred | Staff exam list loads all; pagination skipped for MVP |
| Manual grading UI | Deferred | SUBJECTIVE grading only via Django admin |
| SVG logo (Exam-Kraft crown) | Not started | "EK" text badge used as placeholder |

---

## 7. Known Issues & Bugs

### RESOLVED (this session)
| Bug ID | File | Description | Fix commit |
|--------|------|-------------|-----------|
| BUG-01 / BUG-09 | `ExamCBTPage.tsx` | ONE_WORD, SUBJECTIVE, TRUE_FALSE, SINGLE_DIGIT types unanswerable; response payload mismatch | `50e7641` |
| BUG-02 / BUG-08 | `VirtualNumpad.tsx` | Numerical input was display-only div; keyboard input ignored | `50e7641` |
| BUG-03 | `MathRenderer.tsx` | Custom AST tokeniser failed on `\sin`, `\cos`, `\sum` etc. — rendered literal backslashes | `50e7641` |
| BUG-04 | `ExamResultReportPage.tsx`, `App.tsx` | Report route passed `examId` to `attemptId` API → 404 | `6365f07` |
| BUG-05 | `ExaminationsPage.tsx` | Button labels contained raw `(#modal-id)` DOM fragments | `6365f07` |
| BUG-06 | `ExaminationsPage.tsx` | Exam cards overflowed at ~1100px viewport | `6365f07` |
| BUG-07 | Multiple files | "EZExam" / "EZ" branding not updated after rebrand | `6365f07` |
| CX-008 | `ExamCBTPage.tsx` | Offline queue not flushed on reconnect or beforeunload | `a4bb086` |
| CX-023 / AGY-008 | `examClock.ts` | Timer drift on background tab throttle / reconnect | `a4bb086` |
| CX-024 | `FinishConfirmationModal.tsx` | No focus trap; Escape key not handled; focus not restored on close | `a4bb086` |

### OPEN — Awaiting Batch 3 Approval
| Issue ID | Component | Description |
|----------|-----------|-------------|
| CX-006 | `examinations/views.py` | `PublishResultsView` does not call `finalize()` — scores can recalculate after publication |
| CX-011 | `engine/services.py` | Subjective questions return `EVALUATED` status immediately instead of `D2 PENDING_MANUAL_REVIEW` |
| CX-012 | `examinations/models.py` | No validation that `start_window < end_window`; past start dates are accepted |
| CX-009 | `question_bank/views.py` | Live or evaluated exams can be deleted (data loss risk) |
| AGY-007 | `question_bank/views.py` | Option replacement on question edit is non-atomic (partial update window) |

### OPEN — Batch 5 (Gateway / Security)
| Issue ID | Component | Description |
|----------|-----------|-------------|
| CX-019 | `nginx/nginx.conf` | `X-Forwarded-For` injection not stripped; `X-Real-IP` not set |
| CX-015 | `accounts/views.py` | No login rate limiting (brute-force possible) |
| AGY-002 | `config/settings.py` | CORS may allow wildcard in some configurations |
| AGY-005 | `config/settings.py` | Missing `SECURE_BROWSER_XSS_FILTER`, `X_FRAME_OPTIONS = 'DENY'` |
| CX-016 | CSV import | No file size cap (500KB recommended); no password complexity validation |
| CX-021 | `core/views.py` | Health endpoint leaks internal hostnames / exception strings |
| CX-018 | `engine/services.py` | Delivery query has N+1 on sections (`select_related` missing) |
| CX-028 | `config/settings.py` | No assertion that `SECRET_KEY` is not a default/insecure value on startup |
| CX-027 | `docker-compose.yml`, `nginx/nginx.conf` | Committed with uncommitted working-tree diffs — now resolved |

### OPEN — Codex Zen Audit Findings (new, `audit_swarm/`)
| ID | Severity | Description |
|----|----------|-------------|
| Swarm-01 | High | SQLite `OperationalError: database is locked` under concurrent load — 87 HTTP 500s during 10-student simultaneous exam. **Fix: switch to PostgreSQL in production.** |
| Swarm-02 | Low | Delivery payload includes MCQ option display label field named `key` — fails CHECK-08 literal field rule (no answer content leaked, only the field name) |

---

## 8. Audit & Security Findings

Three separate audits were run against this codebase:

| Audit | Agent | Findings | Location |
|-------|-------|----------|----------|
| Codex Static Audit | Codex CLI | 28 CX-xxx findings | `audit_codex/` |
| AGY Internal Review | Antigravity | 8 AGY-xxx findings | `audit_agy/` |
| Zen Browser Swarm | Codex Zen (10 student agents + 3 teacher agents + 1 admin) | CHECK-01–08 (7 PASS, 1 FAIL), 2 new findings | `audit_swarm/` |

All findings are tracked in `audit_codex/01_findings.md`, `audit_agy/01_finding_verdicts.md`, and `audit_swarm/06_final_report.md`.

---

## 9. Completed Audit Batches

### Batch 0 — Preflight (Complete)
Environment validation, dependency audit, test runner setup, seed data verification.  
Report: `audit_fix/batch0_report.md`

### Batch 1 — Answer-Key & Result Exposure (Complete)
| Finding | Fix |
|---------|-----|
| CX-001 | Removed unused WebSocket consumer and routing |
| CX-002 | Restricted question-bank authoring reads to staff role |
| CX-007 | Gated attempt report behind result publication + closed window |
| CX-013 | Removed `numerical_min`, `numerical_max` from delivery serializer |

Tests after Batch 1: **83/83 passing**  
Report: `audit_fix/batch1_report.md`

### Batch 2 — Attempt Integrity (Complete)
| Finding | Fix |
|---------|-----|
| CX-004 | Partial unique constraint on active attempts + migration `0002` |
| CX-022 | Centralised attempt lifecycle, locking, and deadline calculation in `engine/services.py` |
| CX-005 | Row-level locking on submit; prevented post-submission state overwrites |
| CX-014 | Scoped question lookup to exam paper/section roster |
| CX-003 | Proctoring event validation, attempt-status gate, ingestion rate cap |

Tests after Batch 2: **108 passing, 5 skipped (PostgreSQL-conditional), 0 failed**  
Report: `audit_fix/batch2_report.md`

### Batch 4 — Frontend (Complete)
| Finding / Bug | Fix |
|--------------|-----|
| BUG-01 / BUG-09 | All 8 CBT question types rendered and saved correctly |
| BUG-02 / BUG-08 | VirtualNumpad keyboard-accessible, full-width focusable input |
| BUG-03 | KaTeX math rendering (`$$...$$` display, `$...$` inline) |
| BUG-04 | ExamResultReportPage route uses `attemptId` from `submitResult` |
| BUG-05 | Raw `(#modal-id)` fragments removed from button labels |
| BUG-06 | Card overflow fixed at ~1100px with responsive grid |
| BUG-07 | Complete rebrand from "EZExam" / "EZ" to "Exam-Kraft" |
| CX-008 | Offline response queue flushed on `online` event and `beforeunload` |
| CX-023 / AGY-008 | Timer countdown anchored with `performance.now()`; syncs on reconnect and heartbeat |
| CX-024 | `FinishConfirmationModal`: ARIA dialog, keyboard focus trap (`useFocusTrap`), Escape handling, focus restoration |

Tests after Batch 4: `npm run typecheck` (0 TS errors), `npm run build` (0 errors), Django `108 passed, 0 failed`, pytest `104 passed`  

---

## 10. Pending Audit Batches

### Batch 3 — Lifecycle & Data Retention (Awaiting User Approval)
> Say **"proceed to Batch 3"** to start

- `CX-006` — `PublishResultsView.finalize()` guard
- `CX-011` — Subjective `D2 PENDING_MANUAL_REVIEW` status
- `CX-012` — `start_window < end_window` validation
- `CX-009` — Delete protection on live/evaluated exams
- `AGY-007` — Atomic option replacement

### Batch 5 — Gateway & Security
- `CX-019` — Nginx proxy headers
- `CX-015` — Login rate limiting (`django-ratelimit`)
- `AGY-002 / AGY-005` — CORS and security headers
- `CX-016` — CSV import size cap + password validation
- `CX-021` — Health endpoint sanitisation
- `CX-018` — `select_related` N+1 fix on delivery query
- `CX-028` — `SECRET_KEY` default assertion on startup
- `CX-020` — Add `LICENSE` file
- `CX-026` — Add `.env.example` with all required vars documented

### Batch 6 — Tests & Docs
- `CX-010` — Concurrency integration test (PostgreSQL)
- `AGY-003` — CSV import password validation test
- `AGY-004` — `UniqueConstraint` on `roll_number` per batch per org
- Inline docstrings for `start_attempt` / `submit_attempt` in `services.py`
- Backend rebranding: seed data, email templates, `config/settings.py`

---

## 11. Getting Started (Dev)

### Prerequisites
- Python 3.12+
- Node.js 20+
- Redis (for Celery)

### Backend Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # edit SECRET_KEY and DB settings
python manage.py migrate
python manage.py seed_demo_data  # loads demo org, users, exams
python manage.py runserver 0.0.0.0:8000
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

### With Docker Compose
```bash
docker compose up -d
# Backend: http://localhost/api/v1/
# Frontend: http://localhost/
```

> **Note**: The Docker Compose stack uses Nginx as the reverse proxy. For local dev without Docker, run backend on `:8000` and frontend on `:5173` — the Vite proxy config forwards `/api/v1/` to Django automatically.

### Running Tests
```bash
# Backend
cd backend
.venv/bin/python manage.py test apps --verbosity=1
.venv/bin/pytest tests/ -v

# Frontend
cd frontend
npm run typecheck
npm run build
```

---

## 12. Demo Credentials

> **Dev only** — Change all passwords before any production deployment.

| Role | Username / Email | Password |
|------|-----------------|----------|
| Django Superuser | `admin` | `admin123` |
| Staff OrgAdmin | `orgadmin@ezexam.local` | `admin123` |
| Student | `candidate110@ezexam.local` | `student123` |

### Useful Exam IDs (seeded)
| Exam | UUID |
|------|------|
| Published exam (use for student testing) | `ef502f0f-9e3f-4e63-9c79-ad6c67590883` |
| Evaluated exam (results viewable) | `19a43480-2fb5-4ec2-ac93-6cd610230d5e` |

---

## 13. Project Structure

```
exam-kraft/
├── backend/
│   ├── apps/
│   │   ├── accounts/       # User auth, JWT, profile, CSV import
│   │   ├── analytics/      # Scorecard, cohort ranking, batch analytics
│   │   ├── core/           # Health endpoint, base views
│   │   ├── engine/         # CBT attempt lifecycle (start/save/submit/heartbeat/proctoring)
│   │   ├── examinations/   # Exam CRUD, publish, candidate assignment
│   │   ├── notices/        # Targeted announcements
│   │   ├── organizations/  # Orgs, batches, centres, enrollments
│   │   └── question_bank/  # Questions, options, papers (banks)
│   ├── config/
│   │   ├── settings.py
│   │   └── urls.py
│   └── tests/              # Integration and model tests
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── layout/     # Shell, Sidebar, Header, ProtectedRoutes, ProfileDropdown
│   │   │   ├── FinishConfirmationModal.tsx
│   │   │   ├── MathRenderer.tsx  (KaTeX)
│   │   │   ├── QuestionPalette.tsx
│   │   │   └── VirtualNumpad.tsx
│   │   ├── context/        # AuthContext (JWT + user state)
│   │   ├── hooks/          # useFocusTrap.ts
│   │   ├── pages/
│   │   │   ├── staff/      # ExaminationsPage, QuestionBankPage, StudentsPage, BatchesPage, …
│   │   │   └── student/    # CandidatePortal, ExamLobbyPage, ExamCBTPage, ExamFinishPage, ExamResultReportPage
│   │   ├── services/       # api.ts, studentExamApi.ts, analyticsApi.ts
│   │   ├── types/          # index.ts (all TypeScript types)
│   │   └── utils/          # examClock.ts, offlineResponseQueue.ts
│   └── tests/              # Vitest unit tests (batch4_phase_c.test.ts)
│
├── nginx/
│   └── nginx.conf
├── docker-compose.yml
├── audit_codex/            # Codex static audit findings (28 findings)
├── audit_agy/              # AGY internal review (8 findings)
├── audit_fix/              # Fix reports per batch
└── audit_swarm/            # Zen browser swarm test run (10 student + 3 teacher + 1 admin agents)
```

---

## 14. API Reference Overview

Base URL: `http://localhost:8000/api/v1/`

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/login/` | Login → returns `access`, `refresh`, `user` |
| `POST` | `/auth/token/refresh/` | Refresh access token |
| `GET` | `/auth/me/` | Current user profile |
| `POST` | `/auth/logout/` | Blacklist refresh token |

### Staff — Exams
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/examinations/` | List / create exams |
| `GET/PATCH/DELETE` | `/examinations/:id/` | Retrieve / update / delete exam |
| `POST` | `/examinations/:id/publish/` | Publish exam |
| `POST` | `/examinations/:id/assign/` | Assign batches + centres |
| `POST` | `/examinations/:id/publish_results/` | Publish results |

### Staff — Question Banks
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/question-papers/` | List / create banks |
| `GET/POST` | `/question-papers/:id/questions/` | List / add questions |
| `PATCH/DELETE` | `/question-papers/:id/questions/:qid/` | Edit / remove question |

### Student — CBT Engine
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/student/examinations/` | List assigned exams |
| `POST` | `/student/attempts/start/` | Start or resume attempt |
| `POST` | `/student/attempts/:id/responses/` | Save a response |
| `POST` | `/student/attempts/:id/heartbeat/` | Sync timer, check termination |
| `POST` | `/student/attempts/:id/submit/` | Final submit |
| `POST` | `/student/attempts/:id/proctoring_event/` | Log tab switch / blur |

### Analytics
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/analytics/attempts/:id/report/` | Candidate result report |
| `GET` | `/analytics/examinations/:id/batch/` | Cohort analytics (staff) |
| `GET` | `/analytics/results/:id/scorecard.csv` | Download scorecard CSV |

### Infrastructure
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health/` | Service health (DB + Redis liveness) |

---

## 15. Rebranding Notes

This project was originally reconstructed from an internal platform called "EZExam". It has been fully rebranded to **Exam-Kraft** as a distinct open-source project to avoid any trademark or branding conflict.

**Rebrand scope (complete)**:
- `frontend/index.html` title → `Exam-Kraft`
- `Login.tsx` logo badge and title → "EK" / "Exam-Kraft Portal"
- `ExamCBTPage.tsx` toolbar badge → "EK"
- `Header.tsx`, `Sidebar.tsx`, `Shell.tsx` → "Exam-Kraft"
- `NotFound.tsx`, `BatchAnalyticsPage.tsx`, `QuestionBankPage.tsx`, `ExamLobbyPage.tsx` → "Exam-Kraft"
- `frontend/package.json` (`exam-kraft-frontend`), `backend/config/celery.py` (`exam_kraft`), `backend/apps/organizations/middleware.py`, and `seed_demo_data.py` display strings → "Exam-Kraft"

**Logo**: The final logo will be a 3-pronged crown / trident "E" atop a flared "K" pedestal (SVG, to be designed). Currently using a text badge "EK" as a placeholder.

---

## 16. Contributing

This project is in active pre-launch development. Contributions are welcome for:

- Bug fixes listed in `audit_codex/`, `audit_agy/`, or `audit_swarm/`
- Pending Batch 3, 5, 6 audit items (see section 10)
- PostgreSQL production setup and migration guide
- PNG/Excel question import support
- Virtual calculator component
- Logo and UI design

Please open an issue before submitting a PR. Follow the existing commit message convention: `fix(scope): description` / `feat(scope): description` / `chore(scope): description`.

---

## 17. License

**Non-Commercial Open-Source** — Exact license TBD (Batch 6).

This software is provided for educational and self-hosting use. You may not:
- Resell or white-label this platform commercially
- Use this codebase to operate a paid SaaS examination service

You may:
- Self-host for your coaching institute at no charge
- Fork and modify under the same non-commercial terms
- Contribute upstream via pull requests

> `LICENSE` file will be added in Batch 6 (final release preparation).

---

## 18. Resources Used Map & AI Agent Brain (`ai_agent_brain/`)

All multi-agent coordination artifacts, prompts, audit reports, and browser evidence are preserved in the repository:

| Resource / Directory | Purpose |
|----------------------|---------|
| `ai_agent_brain/MASTER_TEAM_BRIEF.md` | Master project brief, bug inventory, and batch roadmap |
| `ai_agent_brain/teamwork_prompt_*.md` | Teamwork orchestrator delegation prompts |
| `ai_agent_brain/browser_evidence/` | Visual QA screenshots from browser subagents |
| `audit_codex/` | Immutable Codex CLI security & architecture audit |
| `audit_agy/` | Immutable Antigravity verification verdicts |
| `audit_browser/` | Hydrogen Browser QA findings (`HB-001.md` – `HB-005.md`) |
| `audit_fix/` | Batch 0, 1, 2, and integration fix reports |
| `audit_swarm/` | Zen browser swarm run logs and check results |
| `scripts/sentinel_auto_resume.sh` | Sentinel daemon for subagent liveness |

### Branch Map
- `main`: Baseline clean-room reconstruction (`9ffb3b3`)
- `raw-broken-branch`: Active integration branch with Batch 0, 1, 2, 4 fixes, full rebranding, README, and `ai_agent_brain/`
- `backup/safety-backup`: Safety backup snapshot of `raw-broken-branch`

---

*Last updated: 2026-11-25 — Batch 4 (Frontend) & Rebranding complete. Batch 3 (Backend Lifecycle) pending user approval.*
