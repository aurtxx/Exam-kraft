# Summary & Judicial Reconciliation Report

## 1. Verdict Counts Across All Codex Findings (CX-001 through CX-028)

| Verdict Type | Count | Percentage |
|---|---:|---:|
| **VALID** | 22 | 78.6% |
| **VALID-ADJUSTED** | 3 | 10.7% |
| **BY DESIGN - RISKY** | 2 | 7.1% |
| **ALREADY HANDLED** | 1 | 3.6% |
| **PARTIALLY VALID** | 0 | 0.0% |
| **INVALID** | 0 | 0.0% |
| **CANNOT VERIFY** | 0 | 0.0% |
| **Total Codex Findings Reviewed** | **28** | **100.0%** |

*Note: In addition, 8 new self-audit findings (`AGY-001` through `AGY-008`) were identified and documented in `02_missed_by_codex.md`.*

---

## 2. Top 10 Most Dangerous Findings (Consolidated Ranking)

1. **CX-002 (Critical)**: `backend/apps/question_bank/views.py` — Student-readable authoring endpoints return complete answer keys and correct options to any authenticated student.
2. **CX-001 (Critical)**: `backend/apps/engine/consumers.py` — Unauthenticated WebSocket accepts arbitrary callers and increments attempt tab-switch violation counters, creating a remote Denial of Service vector.
3. **AGY-001 (High)**: `backend/apps/engine/views.py` — Global question integer lookup in `SaveResponseView` causes cross-tenant response pollution when UUID resolution is bypassed.
4. **CX-003 (High)**: `backend/apps/engine/views.py` — Attempt launch omits status checks (allows taking unreleased draft exams) and candidate cohort assignment checks.
5. **CX-004 (High)**: `backend/apps/engine/views.py` & `models.py` — Missing database-level uniqueness constraints permit concurrent attempt launches to create duplicate sessions and clocks for the same student.
6. **CX-005 (High)**: `backend/apps/engine/views.py` — `SaveResponseView` and `ProctoringEventView` do not share the submission row lock, allowing post-submission answer mutations.
7. **CX-007 (High)**: `backend/apps/analytics/views.py` — `AttemptReportView` bypasses publication requirements, evaluating and leaking answer keys to early submitters while peers are still writing the exam.
8. **CX-008 (High)**: `frontend/src/pages/student/ExamCBTPage.tsx` — Local offline answer buffer is cleared on final submission without replaying or verifying unacknowledged server saves.
9. **CX-011 (High)**: `backend/apps/analytics/services.py` — Unreviewed subjective and coding questions receive published 0 marks without faculty review.
10. **CX-010 (High)**: `pytest.ini` & `tests/conftest.py` — Default E2E test runs target in-process mock memory handlers, masking PostgreSQL transaction and concurrency behaviors.

---

## 3. Findings With Significant Differences Between Agy and Codex

1. **CX-006 (High -> Medium)**: Disconnected attempts blocking publication is an operational workflow blocker that can be cleared by automated reconciliation, rather than an unrecoverable high-severity platform failure.
2. **CX-009 (High -> Medium)**: Cascade deletion is standard Django ORM foreign-key behavior restricted to authenticated Organization Admins, representing an administrative retention gap rather than an unprivileged data breach.
3. **CX-017 (Medium -> Low / BY DESIGN - RISKY)**: Storing JWT tokens in `localStorage` is an intentional architectural pattern for standalone SPAs, though HttpOnly cookies are preferable for enhanced security.
4. **CX-020 (Medium -> Low / BY DESIGN - RISKY)**: Defaulting to plain HTTP in base Compose configuration was intended to satisfy explicit local/air-gapped school LAN requirements, with TLS termination delegated to reverse proxy ingress.
5. **CX-025 (Low -> Info)**: Discrepancy between Celery asynchronous evaluation in ADR-005 and synchronous execution in views is an architectural documentation divergence that does not cause functional errors.
6. **CX-027 (Info -> ALREADY HANDLED)**: Local working tree modifications observed by Codex in `docker-compose.yml` and `nginx.conf` have already been committed and pushed to GitHub main (`9ffb3b3` / `37e1781`).

---

## 4. Proposed Fix Order with Dependencies

```
[Phase 1: Critical Security & Cheat Prevention]
  Step 1: Fix CX-002 — Lock QuestionBank endpoints to IsOrgAdmin | IsFaculty.
  Step 2: Fix CX-001 — Authenticate WebSocket connections and verify attempt ownership.
  Step 3: Fix AGY-001 — Scope question lookups strictly to the attempt's examination paper.
  Step 4: Fix CX-007 — Enforce is_published and exam closure checks on AttemptReportView.
  Step 5: Fix CX-013 — Strip numerical_min and numerical_max from delivery payloads.

[Phase 2: Exam Integrity & Concurrency Hardening]
  Step 6: Fix CX-003 — Require exam.status == PUBLISHED and verify candidate batch/center assignments in StartAttemptView.
  Step 7: Fix CX-004 — Enforce unique attempt constraint per user/exam in database.
  Step 8: Fix CX-005 — Add select_for_update() row lock inside SaveResponseView.
  Step 9: Fix CX-014 — Validate question response types against question schemas.
  Step 10: Fix CX-008 — Replay and verify un-synced localStorage answers before clearing cache on final submit.

[Phase 3: Lifecycle, Evaluation & Grading Fixes]
  Step 11: Fix CX-011 — Block publishing exams with PENDING subjective/code question outcomes.
  Step 12: Fix CX-006 — Reconcile expired attempts automatically during publication and add Celery beat sweeper.
  Step 13: Fix CX-012 — Freeze start/end windows and duration once exam status is PUBLISHED.
  Step 14: Fix CX-009 — Change on_delete to PROTECT on ExaminationAttempt foreign keys.

[Phase 4: Gateway, Network & Deployment Hardening]
  Step 15: Fix CX-019 — Declare explicit proxy headers across all Nginx location blocks.
  Step 16: Fix CX-015 & AGY-002 — Add DRF login rate throttling and restrict CORS origins.
  Step 17: Fix CX-021 — Sanitize public health check exception messages.
  Step 18: Fix CX-018 — Add prefetch_related on question delivery to eliminate N+1 queries.
  Step 19: Fix CX-023 — Change payload.remaining_seconds || 3600 to ?? 3600.
  Step 20: Fix CX-024 — Add ARIA dialog semantics and focus trapping to FinishConfirmationModal.
  Step 21: Fix CX-010 — Update test runner to include live Django database suites.
  Step 22: Fix CX-026 — Add database backup/restore scripts and .env.example.
```

---

## 5. Needs User Permission to Verify (Dynamic Checks List)

The following dynamic verification commands were left unexecuted per Hard Rule 3 and require explicit user authorization:

| Category | Exact Command | What It Proves |
|---|---|---|
| **E2E Concurrency** | `python backend/manage.py test tests.test_b9_concurrency_boundaries` | Verifies whether parallel attempt starts produce duplicate attempt rows on live SQLite/PostgreSQL. |
| **N+1 Query Multiplication** | `python backend/manage.py test apps.engine.tests.test_engine --verbosity=2` | Measures exact SQL query count during `build_attempt_payload` execution. |
| **Nginx Proxy Headers** | `docker compose exec -T nginx nginx -T` | Confirms whether child `proxy_set_header` directives drop parent `X-Forwarded-Proto` and `X-Real-IP`. |
| **Live Database E2E** | `BASE_URL=http://127.0.0.1:8000 bash ./run_e2e_tests.sh --all` | Runs the 104-case contract suite against live Daphne/Django rather than in-process mock transport. |
| **Container Smoke Check** | `docker compose up -d && curl -i http://localhost/api/v1/health/` | Confirms PostgreSQL, Redis, and Django ASGI container orchestration and health response format. |
