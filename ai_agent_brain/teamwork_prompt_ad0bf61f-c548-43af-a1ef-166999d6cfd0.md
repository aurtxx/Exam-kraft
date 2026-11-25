Implement approved audit fixes for "Exam-kraft" across batches based on independent review of Codex and internal audits, prioritizing preservation of working behavior, correctness, and polish. Run one batch at a time, starting with Batch 0 (Preflight), producing the required report and stopping after each batch.

Working directory: /Users/aurtx/teamwork_projects/ezexam_reconstruction
Integrity mode: development

Audit inputs (read-only, never edit): audit_codex/ and audit_agy/
Output folder: audit_fix/

## Requirements

### R1. Permissions & Guardrails
- Work on a new git branch: fix/audit-batch-<N> (from the current branch). One commit per finding: "fix(CX-0xx): <summary>". Never push, never force, never rewrite history, never amend earlier commits.
- Edit project files ONLY within the current batch's scope. If a fix needs a file outside scope, STOP and ask.
- Existing migrations are immutable. Schema changes = new migration files only.
- Do not delete or rename existing files without asking. Do not upgrade or add dependencies without asking. Do not touch audit_codex/ or audit_agy/.
- Permitted test/linter runs: python backend/manage.py test, pytest, npm build/test. Ask before running docker, docker compose, or anything that writes outside the repo or touches non-disposable data.
- Never print secret values.
- Run ONE batch at a time. After each batch, write the batch report and STOP. Do not start the next batch until the user says "proceed to Batch N".

### R2. Per-Finding Protocol (Mandatory for Every Finding)
1. RE-VERIFY: re-read the current code. Do not trust either report or memory. If the issue no longer reproduces, record NOT REPRODUCED with evidence and skip it.
2. TEST FIRST where feasible: write a failing regression test that proves the flaw, then fix, then show it passes. Concurrency tests must be marked skip-unless-PostgreSQL with an explicit skip reason, because SQLite does not enforce row locks, and a skipped test must never be reported as passed.
3. MINIMAL CHANGE: smallest change that fixes the flaw. No drive-by refactors, no renames, no formatting churn in untouched code.
4. After each fix run the relevant tests plus the full backend suite (python backend/manage.py test) and report pass/fail counts.
5. If a fix would change user-visible behavior or API response shape, stop and ask first, and list the frontend callers affected.

### R3. Batch 0 - Preflight (READ-ONLY, No Code Edits)
- Resolve CX-027: run git status --porcelain, git diff --stat HEAD, git log --oneline -10, git log origin/main..HEAD. State precisely whether docker-compose.yml and nginx/nginx.conf in the working tree match committed main. Settle Codex vs Agy with command output.
- Run the baseline: python backend/manage.py test. Record pass/fail counts.
- Answer by grep/reading, with file:line evidence:
  a) Does the frontend use the WebSocket (ExamAttemptConsumer) at all?
  b) What identifier does the frontend send in save_response: UUID or question_number?
  c) Which frontend pages call QuestionListCreateView/QuestionDetailView or question-paper endpoints? Does any student page depend on them?
  d) Who calls AttemptReportView (attempts/{id}/report/) in the frontend, and what does the finish/result flow expect?
  e) Does the frontend read numerical_min/numerical_max from delivery?
  f) Does ExaminationAttempt / Examination support retakes (attempt number, max_attempts, retake fields)? What does the research/ folder say?
  g) Is there any existing admin endpoint to bulk-expire in-progress attempts?
  h) List every serializer in the repo that outputs is_correct, key, explanation, or numerical bounds, and which roles can reach each.
- Re-verify the exact code claimed in CX-014 / AGY-001 (global Question.objects lookup by number). Quote the real lines.
- Output: audit_fix/batch0_preflight.md. End with proposed defaults for decisions D1-D5 and wait for the user.

### R4. Subsequent Batches (Batches 1 to 6) & Decisions Baseline
- Batch 1 - Answer-key and result exposure: question_bank views/serializers/permissions, engine serializers, analytics/views.py (AttemptReportView only), engine consumers/asgi/routing, nginx ws block (only if removing), tests. (CX-002, CX-007, CX-013 part 1, CX-001).
- Batch 2 - Attempt integrity core: backend/apps/engine/* (views, models, serializers, new services.py, new migration), examinations (read-only use), tests. Create engine/services.py (lock_attempt, expire_if_due, save_response, record_proctoring_event, submit_attempt). (CX-003, CX-004, CX-005, CX-014 + AGY-001, CX-022).
- Batch 3 - Lifecycle and data retention: analytics (services, views), examinations (views, serializers), engine/accounts models for on_delete, question_bank option update, tests, new migrations. (CX-006, CX-011, CX-012, CX-009, AGY-007).
- Batch 4 - Frontend: frontend/src only (ExamCBTPage, studentExamApi, FinishConfirmationModal). (CX-008, CX-023 + AGY-008, CX-024, CX-025 UI part).
- Batch 5 - Gateway and operations: nginx/nginx.conf, frontend/nginx.conf, docker-compose.yml, backend/config/settings.py, accounts views, core health view, engine launch query, new docs. (CX-019 before CX-015, CX-015, AGY-002 / AGY-005, CX-016, CX-021, CX-018, CX-028, CX-020, CX-026, D5).
- Batch 6 - Tests and docs: CX-010, CX-025 (docs part), AGY-003, AGY-004.
- Deferred Backlog (do not implement, keep in report): CX-017, AGY-006, CX-013 part 2, manual grading UI for subjective/code answers.
- Decisions baseline: D1 (WS removal if unused), D2 (Pending subjective/coding blocks publication), D3 (AttemptReportView requires is_published and closed exam window for students), D4 (Partial unique constraint on active attempts), D5 (LICENSE: ask user).

### R5. Batch Report Deliverable
- Create audit_fix/batch<N>_report.md after each batch, then STOP.
- Report format: Per finding table (ID | status | commit hash | files changed | tests added | test result | behavior or API change | residual risk), full-suite pass/fail counts before and after, migrations added, changes outside scope, questions for user.
- Print only the report's path and the one-line status table in the terminal.

## Verification Resources
- In-repo test suites: python backend/manage.py test, pytest, npm build/test.
- Concurrency tests must be marked skip-unless-PostgreSQL with an explicit skip reason, as no external PostgreSQL instance is provided.

## Acceptance Criteria

### Batch 0 (Preflight) Acceptance Criteria
- [ ] Working tree status and git diff for docker-compose.yml and nginx/nginx.conf evaluated against committed main to resolve CX-027
- [ ] Baseline test pass/fail counts from python backend/manage.py test recorded
- [ ] All 8 preflight questions (a through h) answered with file:line citations
- [ ] Code for CX-014 / AGY-001 verified and quoted with exact file:line locations
- [ ] audit_fix/batch0_preflight.md generated containing findings, citations, and proposed defaults for D1-D5
- [ ] No repository code files edited or modified during Batch 0
- [ ] Execution stops after Batch 0 report is written, awaiting user instruction before proceeding to Batch 1