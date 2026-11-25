# Review of Codex's Architectural Understanding

## 1. Overall Architectural Comprehension
The independent auditor (Codex) demonstrated an exceptionally thorough and nuanced understanding of the reconstructed **Exam-Kraft** codebase across all tiers:
- **Modular Monolith**: Correctly identified the division of responsibilities across `backend/apps/{accounts, organizations, question_bank, examinations, engine, analytics, notices, core}`.
- **Tenant Isolation**: Accurately mapped the dual-mechanism model: row-level `TenantManager` isolation in `apps/organizations` vs. direct `organization_id` foreign-key checks in `engine` and `analytics`.
- **NTA CBT Attempt Flow**: Accurately deconstructed the candidate exam attempt lifecycle (`/start/` -> `/heartbeat/` -> `/save_response/` -> `/submit/` -> `/resume/`).
- **Opaque-Box E2E vs. Django Tests**: Correctly caught the divergence between the in-process mock transport used by `pytest` (`tests/mock_server/contract_app.py`) and the live Django/PostgreSQL database implementation.

Codex did not hallucinate endpoints or misattribute components. Its structural tracing across asynchronous Daphne/Channels, Celery tasks, React/Vite state, and Docker/Nginx gateways is factually grounded in the tracked repository at commit `9ffb3b3` / `37e1781`.

---

## 2. Identified Nuances and Minor Misunderstandings

While Codex's technical analysis is accurate, the following context and nuances warrant clarification:

1. **Intended Isolation of the E2E Contract Suite (CX-010)**:
   - *Codex Finding*: Stated that `pytest` runs default to in-process mock validation without hitting Django/PostgreSQL.
   - *Context*: This dual-mode design was deliberate during Phase P0/P1 to establish a hermetic contract specification before backend databases were live. However, Codex is **100% right** that continuing to rely solely on mock transport in default CI pipelines creates a false sense of security regarding database concurrency and row locking.

2. **WebSocket Role in Exam-Kraft Architecture (CX-001, CX-022)**:
   - *Codex Finding*: Identified lack of authentication and duplicate state logic on the WebSocket consumer (`apps/engine/consumers.py`).
   - *Context*: The primary, authoritative student examination flow in `frontend/src/pages/student/ExamCBTPage.tsx` and `studentExamApi.ts` operates over **HTTP REST** (`POST /api/v1/engine/attempts/{id}/heartbeat/` and `POST /save_response/`). The WebSocket channel was added during M5 as an experimental real-time telemetric auxiliary. However, because `consumers.py` connects to the real `ExaminationAttempt` database model and updates `tab_switch_count`, Codex's security concern is fully valid: an exposed, unauthenticated consumer indeed opens a telemetry injection vector.

3. **In-Flight Working Tree vs. GitHub Main (CX-027)**:
   - *Codex Finding*: Noted working tree changes in `docker-compose.yml` and `nginx/nginx.conf`.
   - *Context*: These changes were authored during Milestone M5 hardening (ASGI Daphne service wiring, Celery beat, and health probe updates) and have since been committed (`ba184b4`, `37e1781`, `9ffb3b3`).

4. **Synchronous vs. Asynchronous Evaluation (CX-025)**:
   - *Codex Finding*: Noted ADR-005 promises Celery-backed asynchronous grading while `analytics/views.py` invokes `evaluate_examination(exam.pk)` synchronously.
   - *Context*: This is an accurate observation. Celery was configured in `config/celery.py` and `docker-compose.yml`, but the API views opted for synchronous in-thread evaluation to simplify immediate test verification. Codex accurately flagged this architecture divergence.

---

## 3. Summary Assessment of the Codex Audit
Codex's audit is rigorous, fact-based, and objective. It correctly identified critical security and concurrency vulnerabilities that could compromise exam integrity in high-stakes environments. The findings reflect the actual state of the code rather than assumptions.
