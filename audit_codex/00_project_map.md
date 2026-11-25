# Exam-Kraft project map

## Audit baseline

Local HEAD and GitHub `refs/heads/main` both resolved to `9ffb3b3e42946d109f7873e5570409ac38b2b8cb`. The local clone is non-shallow. The tracked working tree differs in `docker-compose.yml` and `nginx/nginx.conf`. In particular, GitHub main does not forward the WebSocket route through nginx, while its backend defines the route and the working-tree gateway enables it. Ignored workspace entries include the Python environment, pytest cache and macOS metadata.

## Repository and runtime

| Directory or entry point | Responsibility |
|---|---|
| `frontend/src/main.tsx`, `App.tsx` | React/Vite/TypeScript SPA. Staff routes cover authoring, people, organizations, notices and analytics. Student routes cover lobby, CBT, finish and reports. |
| `frontend/src/context/AuthContext.tsx`, `services/api.ts`, `services/studentExamApi.ts` | Login and identity, Axios bearer and tenant headers, refresh, exam HTTP calls and browser answer cache. |
| `backend/manage.py`, `config/settings.py`, `config/urls.py`, `config/asgi.py` | Django/DRF management, environment configuration, versioned HTTP routing and Channels WebSocket dispatch through Daphne. |
| `backend/apps/` | Accounts, tenant organizations, question bank, exams, attempt engine, analytics, notices and operational probes. Django migrations sit beside the domain models. |
| `docker-compose.yml`, `nginx/nginx.conf`, `frontend/nginx.conf` | PostgreSQL and Redis, migration service, backend, Celery worker, frontend and gateway. Local Compose adds Celery beat. Gateway sends API/admin/probes/static traffic to Django and the other routes to frontend nginx for SPA fallback. |
| `backend/apps/{core,organizations}/management/commands/` | Django demo seeding commands for local and benchmark use. |
| `research/`, `management/architecture_decisions.md` | Design inputs and architecture decisions. |
| `tests/`, `backend/tests/`, `backend/apps/{engine,analytics}/` | Contract fixtures and scenarios, Django model/RBAC/isolation tests, attempt and analytics tests. |

## Identity and request lifecycle

Login validates credentials through the accounts serializer and returns Simple JWT access and refresh tokens. The React client retains tokens and identity in browser storage and attaches bearer and tenant headers. Django resolves tenant context from a valid JWT claim, tenant header, host, or authenticated session fallback. DRF authenticates JWT or session and applies each view's permission classes. Tenant-managed repositories and explicit organization filters then constrain most authoring queries. The attempt engine has separate permission and lookup paths. WebSocket dispatch wraps the consumer in Django session auth middleware, yet the consumer does not use that identity to authorize a connection or a write.

Exam start resolves the exam and checks its time window. It recovers the latest attempt or creates a row with the earlier of duration expiry and window close. Delivery includes sections, serialized questions, responses and palette counts. The client tracks its clock and syncs via heartbeat. Save upserts a response by attempt and question, and submit locks the attempt row while changing its status. Analytics grades finalized attempts and builds results, scorecards, question reviews, ranks and percentiles. Faculty publication flips a result flag after checking the session window and in-progress attempts. The separate attempt report can trigger grading on a GET.

## Data relationships

Organizations own users, centers, batches, question banks, notices and exams. User profiles and faculty profiles hold identity metadata, and student enrollments connect candidates to batches. A question bank contains sections and questions, with option rows attached to questions. An exam can reference a paper or use exam sections and links with per-question marks. Candidate assignments reference a student, batch or center. Each attempt links a user and exam and owns response and proctoring log rows. A one-to-one result leads to a scorecard, section scores and question reviews. PostgreSQL is used when configured, with SQLite fallback for local use. UTC and timezone-aware Django settings are enabled.

## Research and implementation cross-check

| Source | Implemented or divergent behavior |
|---|---|
| `research/database_design.md:11-49,363-443` | Shared tenant schema and much of the assessment model exist. Evaluation data lives in analytics. Candidate attempt uniqueness and ownership boundaries vary by code path. |
| `research/user_workflows.md:148-175,227-292` | Staff can assign and publish, and the server calculates a deadline. Candidate launch omits publication and assignment guards. Submission uses a lock that autosave and proctoring do not share. |
| `research/user_workflows.md:293-377` and `management/architecture_decisions.md:124-159` | Scoring and ranking exist. Grading is callable synchronously, and candidate reports differ from the documented staff-controlled release flow. Cached responses lack a reliable replay before finalization. |
| `research/student_exam_ui_spec.md:144-149,224-255` | CBT navigation, numeric inputs, palette and finish confirmation exist. Subjective and code grading stays pending. Visibility/blur events and browser persistence implement only part of the described resilience and proctoring. |
| `research/api_contracts.md`, `research/route_inventory.md`, `research/ui_component_spec.md` | Runtime URLs and serializers govern behavior. The mock contract and live URL tree are separate. Staff routes expose several dashboard aliases and authoring permissions differ from candidate data requirements. |
| `README.md:44-76` and `management/architecture_decisions.md:165-181` | Migration ordering, frontend fallback and HTTP health routing exist. README calls the server Gunicorn while the Dockerfile launches Daphne. Review the local gateway header inheritance before treating local probes as equivalent to main. |

## Checklist disposition

| Area | Evidence reviewed |
|---|---|
| A | Window validation, timeout grace, expiry triggers, scoring and lock boundaries. Candidate-supplied submission reason selects the automatic branch, while writes still face the grace cutoff. Server UTC settings were checked. |
| B | Attempts, assignment, retakes, deterministic delivery, answer serialization, proctoring, scoring and publication. Camera configuration appears in delivery, while the inspected CBT proctoring path tracks visibility and blur. |
| C | Login, refresh, logout, tenant permissions, engine and analytics object checks, Django password hashing, CORS/CSRF settings, shell-free upload parsing, dependency declarations and masked history checks. Browser storage and public health details are covered in the findings. |
| D | Models and initial attempt migration, response uniqueness, deletion relations, tenant filters, transaction boundaries and repeated relation access. |
| E | Versioned route map, response shape, list bounding and retries. Engine and question lists use custom envelopes while generic DRF views use their own errors. Student roster supports a page parameter, while exam and question list handlers serialize the selected queryset directly. |
| F | SPA routing, auth and refresh storage, CBT timer and error states, cached recovery, finish dialog and math rendering. MathRenderer renders text nodes. No raw HTML sink appeared in the inspected frontend source. |
| G | Compose services, internal data ports, gateway port, persistent volumes, healthchecks, restart policy, image commands, backend user, forwarded headers, body limits and timeouts. The backend uses an explicit non-root user. Frontend and proxy nginx images rely on their image defaults. |
| H | Default pytest collection, script exit handling, fixture transport, backend timer tests and a parallel-launch assertion. The parallel-launch assertion has substance against a live implementation, which the default fixture does not hit. |
| I | Compared documentation, routes, launch commands and grading behavior. ASGI catches all setup exceptions and falls back to HTTP, which can hide a WebSocket initialization failure. |
| J | Searched tracked configuration for release gates, env examples, license, recovery docs and application telemetry. Probes exist, but checked-in configuration did not establish error tracking or backup recovery. |
| K | App boundaries and attempt transitions. HTTP lifecycle rules concentrate in a 537-line views module and overlap with the consumer. |
