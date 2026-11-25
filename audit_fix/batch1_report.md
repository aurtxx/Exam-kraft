# Batch 1 Audit Fix Report — Answer-Key and Result Exposure

**Branch:** `fix/audit-batch-1` (branched from `main` at `9ffb3b3`)  
**Date:** 2026-11-24  
**Scope:** `CX-002`, `CX-007`, `CX-013` (Part 1), `CX-001`  

---

## Per-Finding Summary

| ID | status | commit hash | files changed | tests added | test result | behavior or API change | residual risk |
|---|---|---|---|---|---|---|---|
| CX-002 | FIXED | `d72b627` | `backend/apps/question_bank/views.py`, `backend/tests/test_rbac.py` | 3 (`QuestionBankAccessControlTestCase`: `test_student_denied_read_on_question_bank_and_question_endpoints`, `test_staff_can_read_question_bank_and_questions_with_keys`, `test_outsider_faculty_denied_on_other_tenant_question_bank`) | PASS (`78 passed / 0 failed / 0 errors`) | `STUDENT` users now receive `403 Forbidden` on `GET`/authoring endpoints under `/api/v1/question-papers/`, `/api/v1/question-banks/`, and `/api/v1/questions/`; `FACULTY` gains authoring read/write access alongside `ORG_ADMIN` and `SUPERADMIN`. No student frontend callers exist. | None for student access. Note: `FACULTY` now has write permissions in addition to read permissions on `question_bank` views via `IsOrgAdminOrFaculty`. |
| CX-007 | FIXED | `bffeaee` | `backend/apps/analytics/views.py`, `backend/apps/analytics/test_analytics.py` | 2 added (`test_cx007_attempt_report_requires_published_result_and_closed_window_for_students`, `test_cx007_staff_retains_attempt_report_access_when_unpublished`); 2 legacy tests updated for D3 (`test_answer_reveal_policies`, `test_direct_api_endpoints_evaluate_results_and_report`) | PASS (`10/10` in `apps.analytics`; `80 passed / 0 failed / 0 errors` full suite) | Student requests to `AttemptReportView` (`/api/v1/attempts/{id}/report/`, `/api/v1/attempts/{id}/results/`, `/api/v1/student/attempts/{id}/report/`, `/api/v1/analytics/attempts/{id}/report/`) now return `403 Forbidden` (`code/error: RESULTS_NOT_PUBLISHED`) unless `Result` exists with `is_published=True` AND the exam window is closed (`end_window <= now` or `status in ('CLOSED', 'EVALUATED')`). Students no longer trigger on-demand `evaluate_examination()`. Same-org `ORG_ADMIN`/`FACULTY`/`is_staff` and `SUPERADMIN` retain on-demand access. | `PublishResultsView` does not automatically mutate `exam.status`, so exams with `end_window=None` and `status='PUBLISHED'` continue to block student `AttemptReportView` access until `exam.status` becomes `CLOSED`/`EVALUATED` or `end_window` elapses. Mock server / tier4 scenarios (`CX-010`) remain deferred to Batch 6. |
| CX-013 (Part 1) | FIXED | `34804c9` | `backend/apps/engine/serializers.py`, `backend/apps/engine/tests/test_engine.py` | 1 added (`test_delivery_payload_excludes_numerical_bounds_on_start_and_resume`) + assertions added to `test_attempt_start_and_payload_delivery` | PASS (`10/10` in `apps.engine`; `81 passed / 0 failed / 0 errors` full suite) | Removed `'numerical_min'` and `'numerical_max'` from `DeliveryQuestionSerializer.Meta.fields` in start and resume payloads. Frontend CBT components do not read these fields, and grading reads directly from the `Question` ORM model. | CX-013 Part 2 (question/option shuffling) remains in Deferred Backlog per R4. |
| CX-001 | FIXED | `fc5cd6c` | `backend/config/asgi.py`, `backend/apps/engine/routing.py`, `backend/apps/engine/consumers.py`, `backend/apps/engine/tests/test_engine.py` | 2 (`WebSocketRemovalTestCase`: `test_asgi_application_is_http_only_and_rejects_websocket_scope`, `test_websocket_routing_and_consumer_removed`) | PASS (`12/12` in `apps.engine`; `83 passed / 0 failed / 0 errors` full suite; `104 passed` in `.venv/bin/pytest`) | `config.asgi.application` is now HTTP-only (`django_asgi_app`), `websocket_urlpatterns = []`, and `ExamAttemptConsumer` is removed (replaced with tombstone comment). WebSocket connections are rejected. Frontend uses HTTP polling/endpoints only. | `channels` and `daphne` dependencies remain in `backend/requirements.txt` and `backend/config/settings.py` (Batch 5 scope). Tombstone files `consumers.py` and `routing.py` kept in-place per R1 no-delete rule. |

---

## Full-Suite Pass/Fail Counts

- **Before Batch 1 (baseline on `fix/audit-batch-1` at `9ffb3b3`):**
  - `cd backend && .venv/bin/python manage.py test`: **75 passed / 0 failed / 0 errors**
  - `.venv/bin/pytest`: **104 passed / 0 failed**
- **After Batch 1 (at `fc5cd6c`):**
  - `cd backend && .venv/bin/python manage.py test`: **83 passed / 0 failed / 0 errors** (+8 new regression tests)
  - `.venv/bin/pytest`: **104 passed / 0 failed**

---

## Migrations Added

None.

---

## Changes Outside Scope

None committed.

*Working-tree note (CX-027 / Batch 5 hygiene):* Unstaged `docker-compose.yml` and `nginx/nginx.conf` from pre-existing CX-027 remain **unstaged and uncommitted** for Batch 5. Per Batch 1 instructions, the `/ws/` proxy block and `map $http_upgrade $connection_upgrade` lines (lines 6–9 and 32–42) were stripped from working-tree `nginx/nginx.conf` without staging `nginx/nginx.conf` in any Batch 1 commit.

---

## Questions for User

1. **Tombstone files (`CX-001`):** Per R1 ("Do not delete or rename existing files without asking"), `backend/apps/engine/consumers.py` and `backend/apps/engine/routing.py` were emptied to tombstone stubs rather than deleted. Would you like to delete those two files (or keep them until Batch 5 cleanup)?
2. **Proceed confirmation:** Please review `audit_fix/batch1_report.md` and confirm `"proceed to Batch 2"` when ready.
