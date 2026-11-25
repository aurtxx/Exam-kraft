# Phase 2: Finding Verdicts (CX-001 through CX-028)

### CX-001
- Verdict: VALID
- Agy severity: Critical
- Agree with Codex severity? Yes (Critical)
- Evidence checked: `backend/apps/engine/consumers.py:16-39, 49-68, 76-109`; `backend/config/asgi.py:7-19`
- Reasoning: `ExamAttemptConsumer.connect()` extracts `attempt_id` from the URL route kwargs and immediately accepts the connection (`await self.accept()`) without authenticating the requesting user or verifying candidate ownership. Furthermore, `_log_proctoring_event` mutates `attempt.tab_switch_count += 1` directly on the database. Anyone with a known or guessed attempt UUID can connect and artificially inflate tab switch violations, triggering auto-submission or penalty locks on a candidate.
- What Codex got right: Consumer accepts without authentication and allows arbitrary callers to increment proctoring counters that affect attempt termination.
- What Codex got wrong or missed: Missed noting that the frontend currently relies on HTTP endpoints (`/proctoring_event/`) rather than the WebSocket for primary submissions, making this an exposed dormant vector.
- Fix direction: Wrap the WebSocket route in custom JWT authentication middleware, verify `scope['user'].id == attempt.user_id` before accepting connection, and reject unauthorized events.
- Effort estimate: S
- Fix risk: Low; frontend does not yet strictly require the WebSocket stream, but fixing prevents denial-of-service.

---

### CX-002
- Verdict: VALID
- Agy severity: Critical
- Agree with Codex severity? Yes (Critical)
- Evidence checked: `backend/apps/question_bank/views.py:102-153, 309-327`; `backend/apps/question_bank/serializers.py:44-51, 103-139`; `backend/apps/accounts/permissions.py:51-67`
- Reasoning: `QuestionListCreateView` and `QuestionDetailView` use `IsOrgAdminOrReadOnly`, which explicitly permits `SAFE_METHODS` (GET) for all authenticated tenant members, including users with role `STUDENT`. Because both views serialize questions using `QuestionSerializer`, which includes `key`, `explanation`, and `OptionSerializer` (containing `is_correct`), any student enrolled in the organization can query `/api/v1/question-papers/{id}/` or `/api/v1/questions/` and receive complete question keys and correct options.
- What Codex got right: Authoring endpoints allow read access to any tenant member and serialize the secret answer keys and correct options.
- What Codex got wrong or missed: None; the analysis is 100% accurate.
- Fix direction: Restrict `QuestionListCreateView` and `QuestionDetailView` to `IsOrgAdmin | IsFaculty` for all methods, and ensure student delivery uses exclusively `DeliveryQuestionSerializer` in `apps.engine`.
- Effort estimate: S
- Fix risk: Low; does not affect staff authoring and eliminates student cheat vectors.

---

### CX-003
- Verdict: VALID
- Agy severity: High
- Agree with Codex severity? Yes (High)
- Evidence checked: `backend/apps/engine/views.py:154-226`; `backend/apps/examinations/views.py:30-41, 169-216`
- Reasoning: `StartAttemptView.post()` only checks if the exam exists and whether `start_window` and `end_window` are valid. It never checks `exam.status == ExaminationStatus.PUBLISHED`, nor does it verify that `request.user` belongs to any assigned batch, group, or center. Consequently, any authenticated user can launch an exam in `DRAFT` status or take exams assigned to different cohorts.
- What Codex got right: Attempt start omits both status checks (draft vs published) and candidate eligibility/assignment checks.
- What Codex got wrong or missed: None.
- Fix direction: In `StartAttemptView`, require `exam.status == ExaminationStatus.PUBLISHED`, verify that `request.user` is in candidate assignments or assigned batches/centers, and check user tenant membership.
- Effort estimate: M
- Fix risk: Low; ensures only eligible students take active published exams.

---

### CX-004
- Verdict: VALID
- Agy severity: High
- Agree with Codex severity? Yes (High)
- Evidence checked: `backend/apps/engine/views.py:192-226`; `backend/apps/engine/models.py:45-74`; `backend/apps/engine/migrations/0001_initial.py`
- Reasoning: In `StartAttemptView`, checking for an existing attempt (`ExaminationAttempt.objects.filter(...)`) and creating a new attempt (`ExaminationAttempt.objects.create(...)`) are performed in separate non-atomic, non-locked statements. There is no `unique_together = ('user', 'examination')` constraint on `ExaminationAttempt`. Two concurrent launch requests from the same user can pass the filter check simultaneously and create duplicate attempt rows with different deadlines.
- What Codex got right: Concurrent start requests can bypass the application-level check and create multiple attempt rows due to missing database constraints.
- What Codex got wrong or missed: Did not mention that in practice, practice exams might allow retakes, but single-attempt formal exams require strict constraints.
- Fix direction: Add a database unique constraint (or partial unique constraint for in-progress attempts) or wrap the start sequence in an atomic transaction with a Redis/database lock or `get_or_create`.
- Effort estimate: S
- Fix risk: Low to Medium; need to ensure practice mode compatibility if multiple attempts are later allowed.

---

### CX-005
- Verdict: VALID
- Agy severity: High
- Agree with Codex severity? Yes (High)
- Evidence checked: `backend/apps/engine/views.py:291-391, 422-459, 494-529`
- Reasoning: In `SubmitAttemptView`, the attempt row is locked using `select_for_update()`, transitioning the status to `SUBMITTED`. However, `SaveResponseView` reads `attempt = ExaminationAttempt.objects.get(id=id)` without `select_for_update()`. A concurrent `save_response` request that read the attempt before the lock was acquired can proceed to write an `AttemptResponse` record even after the submission was finalized. Similarly, `ProctoringEventView` updates `tab_switch_count` and `status` without a row lock, potentially overwriting `SUBMITTED` back to `AUTO_SUBMITTED`.
- What Codex got right: Autosave and proctoring endpoints do not share the submission lock, enabling race conditions where answers or statuses are written post-submission.
- What Codex got wrong or missed: None.
- Fix direction: Use `select_for_update()` in `SaveResponseView` inside `transaction.atomic()`, or verify attempt status inside an atomic transaction when saving responses.
- Effort estimate: S
- Fix risk: Low; slightly increases lock contention during simultaneous saves, but completely prevents post-submit tampering.

---

### CX-006
- Verdict: VALID-ADJUSTED
- Agy severity: Medium
- Agree with Codex severity? No (Adjusted from High to Medium)
- Evidence checked: `backend/apps/engine/views.py:263-276, 319-328`; `backend/apps/analytics/views.py:286-300`; `backend/config/celery.py`; `docker-compose.yml:75-81`
- Reasoning: In `PublishResultsView`, the check `exam.attempts.filter(status=AttemptStatus.IN_PROGRESS).exists()` blocks publication if any attempt is still marked `IN_PROGRESS`. Because automatic deadline expiry is only triggered when a student actively sends a heartbeat or submit request, an abandoned or disconnected attempt whose deadline expired hours ago remains in `IN_PROGRESS` indefinitely, blocking publication. While this is a real operational issue, administrators can manually intervene or trigger bulk auto-submit, making it Medium rather than High severity.
- What Codex got right: Expired attempts left unclosed by inactive students block result publication because no background Celery sweeper is active.
- What Codex got wrong or missed: Overstated severity as High; it is an operational blocker that can be resolved by a periodic sweeper or by reconciling expired attempts on publication.
- Fix direction: In `PublishResultsView`, automatically transition any `IN_PROGRESS` attempt with `server_deadline < timezone.now()` to `AUTO_SUBMITTED` prior to publication check, and add a Celery beat sweeper task.
- Effort estimate: S
- Fix risk: Low; makes publication self-healing.

---

### CX-007
- Verdict: VALID
- Agy severity: High
- Agree with Codex severity? Yes (High)
- Evidence checked: `backend/apps/analytics/views.py:35-49, 179-218, 237-249, 286-300`
- Reasoning: While `StudentResultsView` requires `is_published=True`, `AttemptReportView` (`GET /api/v1/attempts/{id}/report/`) does not check `result.is_published`. Instead, it checks only whether the attempt is submitted and `exam.hide_results=False`, triggering `evaluate_examination()` on demand and returning the full score and question reviews. If `answer_reveal_policy == 'IMMEDIATELY'`, a candidate who submits early can inspect the exact answer key while peers are still taking the test.
- What Codex got right: Attempt report endpoint bypasses the `is_published` requirement and exposes scores and answer keys before official publication.
- What Codex got wrong or missed: None.
- Fix direction: Update `AttemptReportView` to require `result.is_published == True` for student callers, and forbid answer revelation while the exam window remains active.
- Effort estimate: S
- Fix risk: Low; aligns the report view with institutional exam integrity rules.

---

### CX-008
- Verdict: VALID
- Agy severity: High
- Agree with Codex severity? Yes (High)
- Evidence checked: `frontend/src/pages/student/ExamCBTPage.tsx:91-111, 274-315, 381-399`; `backend/apps/analytics/services.py:143-155`
- Reasoning: In `ExamCBTPage.tsx`, `handleFinalSubmit()` simply calls `studentExamApi.submitExam()` and immediately clears `localStorage` without verifying that all locally cached offline responses were acknowledged and synced to the backend. If an autosave HTTP request failed due to a transient connection blip, the candidate's last answer exists only in `localStorage` and is wiped upon submission, leaving it graded as unattempted or stale.
- What Codex got right: Failed local autosaves are not replayed or verified before final submit, leading to potential data loss upon cache clearance.
- What Codex got wrong or missed: None; accurately traced the offline cache lifecycle.
- Fix direction: Before executing final submission, iterate over locally cached responses, flush unacknowledged answers to the server, and only clear the cache upon confirmed server sync.
- Effort estimate: M
- Fix risk: Medium; must handle submission timeouts and offline finalization gracefully.

---

### CX-009
- Verdict: VALID-ADJUSTED
- Agy severity: Medium
- Agree with Codex severity? No (Adjusted from High to Medium)
- Evidence checked: `backend/apps/accounts/views.py:373-380`; `backend/apps/examinations/views.py:145-158`; `backend/apps/engine/models.py:49-57, 90-101`; `backend/apps/analytics/models.py:6-25`
- Reasoning: Foreign keys from `ExaminationAttempt` to `User` and `Examination` use `on_delete=models.CASCADE`. Deleting a user or examination cascades and permanently deletes attempts, responses, proctoring logs, and results. In standard educational software, assessment attempts must be preserved for audit and compliance. However, deleting users and exams is restricted to Organization Admins and Superadmins, so it is an administrative data retention flaw rather than an unprivileged attack vector.
- What Codex got right: Cascade deletion erases completed attempts and results when parent entities are deleted.
- What Codex got wrong or missed: Overstated severity as High; this is standard Django ORM default behavior that should be hardened to `PROTECT` or soft-deletion.
- Fix direction: Change `on_delete=models.CASCADE` to `on_delete=models.PROTECT` on `ExaminationAttempt.user` and `ExaminationAttempt.examination`, and implement soft-delete for user accounts.
- Effort estimate: S
- Fix risk: Low; prevents accidental loss of institutional assessment records.

---

### CX-010
- Verdict: VALID
- Agy severity: High
- Agree with Codex severity? Yes (High)
- Evidence checked: `pytest.ini:1-12`; `tests/conftest.py:12-39`; `run_e2e_tests.sh:89-113`; `tests/tier2_boundaries/test_b9_concurrency_boundaries.py:12-26`
- Reasoning: `pytest.ini` points exclusively to `testpaths = tests`. In `conftest.py`, when `BASE_URL` is omitted (the default), `httpx.MockTransport(ContractHandler)` routes all HTTP requests to in-memory Python dictionaries. As a result, running `pytest` or `./run_e2e_tests.sh` verifies mock handler logic rather than real PostgreSQL transactions, row-level locks, or Django ORM constraints.
- What Codex got right: Default test execution tests in-memory mock handlers rather than the real database and backend application.
- What Codex got wrong or missed: Missed that `python backend/manage.py test` does run 75 real Django backend tests against SQLite/PostgreSQL, but confirmed that the E2E suite defaults to mock.
- Fix direction: Update `run_e2e_tests.sh` to explicitly run `manage.py test` alongside E2E tests, and provide a flag requiring live server integration testing against Docker Compose.
- Effort estimate: S
- Fix risk: Low; improves test transparency.

---

### CX-011
- Verdict: VALID
- Agy severity: High
- Agree with Codex severity? Yes (High)
- Evidence checked: `backend/apps/analytics/services.py:38-43, 145-179`; `backend/apps/analytics/views.py:286-300`; `research/student_exam_ui_spec.md:144-149`
- Reasoning: In `grade_question()`, questions with type `SUBJECTIVE` or `CODING` return `Outcome.PENDING, ZERO, []`. During evaluation, `section.maximum_score += positive`, but `section.score` receives 0. `PublishResultsView` does not check for pending evaluations before publishing. Students who took exams with subjective questions receive a final published score of 0 on those questions without faculty having graded them.
- What Codex got right: Subjective and coding questions default to zero while counting towards maximum score, and publication publishes these incomplete scores.
- What Codex got wrong or missed: None.
- Fix direction: In `PublishResultsView`, verify that no `PENDING` question evaluations exist, or introduce a manual grading interface for faculty before allowing publication.
- Effort estimate: M
- Fix risk: Low; prevents publishing premature zero scores on manual questions.

---

### CX-012
- Verdict: VALID
- Agy severity: Medium
- Agree with Codex severity? Yes (Medium)
- Evidence checked: `backend/apps/examinations/views.py:73-88, 145-158, 240-253`; `backend/apps/examinations/serializers.py:37-83`
- Reasoning: `ExaminationDetailView` handles `PUT`/`PATCH` updates via standard `generics.RetrieveUpdateDestroyAPIView` and `ExaminationSerializer`. While `validate_question_paper_id` prevents changing question papers on a published exam, the serializer does not prevent updating `start_window` or `end_window` on published exams, nor does it re-validate `start_window < end_window` on partial updates. An admin can shift windows mid-exam, causing race conditions with active attempt deadlines.
- What Codex got right: Schedule fields can be edited on published exams without comprehensive combined window validation.
- What Codex got wrong or missed: None.
- Fix direction: Freeze `start_window`, `end_window`, and `duration_minutes` once an examination is `PUBLISHED`, and validate `start < end` across combined instance values.
- Effort estimate: S
- Fix risk: Low; protects active exam timing.

---

### CX-013
- Verdict: VALID
- Agy severity: Medium
- Agree with Codex severity? Yes (Medium)
- Evidence checked: `backend/apps/engine/serializers.py:22-44`; `backend/apps/engine/views.py:41-76`; `backend/apps/analytics/services.py:45-65`
- Reasoning: `DeliveryQuestionSerializer` excludes option correctness (`is_correct`), but includes `numerical_min` and `numerical_max`. A tech-savvy student inspecting the JSON response of `/api/v1/engine/attempts/start/` can view the exact acceptable numerical tolerance range for numerical questions. Additionally, question and option ordering is static and deterministic, ignoring `exam.shuffle_questions` and `exam.shuffle_options`.
- What Codex got right: Numeric bounds are exposed in client delivery payloads, and question shuffling flags are not implemented in the delivery projection.
- What Codex got wrong or missed: None.
- Fix direction: Strip `numerical_min` and `numerical_max` from `DeliveryQuestionSerializer`, and implement candidate-specific deterministic shuffling when `shuffle_questions` or `shuffle_options` is true.
- Effort estimate: S
- Fix risk: Low; prevents candidate cheating.

---

### CX-014
- Verdict: VALID
- Agy severity: Medium
- Agree with Codex severity? Yes (Medium)
- Evidence checked: `backend/apps/engine/views.py:331-391`; `backend/apps/engine/models.py:98-115`; `backend/apps/engine/serializers.py:47-67`
- Reasoning: In `SaveResponseView`, the question is resolved via `Question.objects.filter(...)` globally by UUID or `question_number` without verifying that the question actually belongs to the examination paper linked to the attempt. A candidate can submit answers for question IDs from other exams or question banks. Furthermore, `selected_options` and `numerical_value` are saved without schema validation against the question type.
- What Codex got right: Question lookup is global rather than scoped to the exam roster, and submitted data lacks type validation.
- What Codex got wrong or missed: None.
- Fix direction: Scope question lookup to `attempt.examination.question_paper.questions` (or exam section questions), and validate response payload types against `question.question_type`.
- Effort estimate: S
- Fix risk: Low; ensures response integrity.

---

### CX-015
- Verdict: VALID
- Agy severity: Medium
- Agree with Codex severity? Yes (Medium)
- Evidence checked: `backend/apps/accounts/views.py:33-65`; `backend/config/settings.py:178-190`; `nginx/nginx.conf:12-48`
- Reasoning: `LoginView` uses `permission_classes = [AllowAny]`. There is no DRF `throttle_classes` configured on the view, no `DEFAULT_THROTTLE_RATES` configured in `REST_FRAMEWORK` settings, and no `limit_req_zone` configured in `nginx/nginx.conf`. This leaves the authentication endpoint completely open to automated brute-force attacks and credential stuffing.
- What Codex got right: Login lacks application-level and proxy-level rate limiting.
- What Codex got wrong or missed: None.
- Fix direction: Configure `AnonRateThrottle` and `UserRateThrottle` in DRF settings, attach a specific `ScopedRateThrottle` (e.g. 5 requests/minute) to `LoginView`, and add `limit_req` in Nginx.
- Effort estimate: S
- Fix risk: Low; prevents brute-force abuse.

---

### CX-016
- Verdict: VALID
- Agy severity: Medium
- Agree with Codex severity? Yes (Medium)
- Evidence checked: `backend/apps/accounts/views.py:387-416`; `nginx/nginx.conf:12-14`
- Reasoning: In `StudentBulkImportView`, `content = uploaded.read()` loads the entire uploaded file into application memory at once. In `nginx/nginx.conf`, `client_max_body_size` is set to `100M`. An administrator uploading a massive 100MB CSV file will cause Python to allocate significant memory for the byte buffer and decoded strings, risking Out-Of-Memory (OOM) crashes in memory-constrained environments.
- What Codex got right: The full upload is read into memory synchronously and the proxy permits uploads up to 100MB.
- What Codex got wrong or missed: Bulk CSV imports are restricted to authenticated organization admins, limiting the threat to authorized operators.
- Fix direction: Stream the CSV line-by-line using `codecs.iterdecode(uploaded.chunks(), 'utf-8')` or limit the import file size to 5MB (plenty for 50,000 student rows).
- Effort estimate: S
- Fix risk: Low; enhances server memory stability.

---

### CX-017
- Verdict: BY DESIGN - RISKY
- Agy severity: Low
- Agree with Codex severity? No (Adjusted from Medium to Low)
- Evidence checked: `frontend/src/context/AuthContext.tsx:65-101`; `frontend/src/services/api.ts:44-49, 86-119`
- Reasoning: JWT `access_token` and `refresh_token` are stored in browser `localStorage`. This is a standard pattern for decoupled Single Page Applications (SPAs) communicating with REST APIs across domains, but it exposes tokens to theft if an XSS vulnerability exists. In educational assessment software, using HttpOnly, SameSite cookies for refresh tokens is a safer pattern, but `localStorage` is intentional for this initial standalone client architecture.
- What Codex got right: Tokens are persisted in `localStorage` rather than HttpOnly cookies.
- What Codex got wrong or missed: Codex treats this as a defect rather than a common architectural tradeoff in Vite/REST SPAs without dedicated backend-for-frontend (BFF) layers.
- Fix direction: Transition refresh token exchange to an HttpOnly cookie endpoint (`/api/v1/auth/cookie-refresh/`) and keep access tokens in-memory.
- Effort estimate: M
- Fix risk: Medium; requires coordinating CORS credentials and cookie handling across frontend and backend.

---

### CX-018
- Verdict: VALID
- Agy severity: Medium
- Agree with Codex severity? Yes (Medium)
- Evidence checked: `backend/apps/engine/views.py:41-76, 89-97`; `backend/apps/engine/serializers.py:42-44`
- Reasoning: In `build_attempt_payload()`, questions and sections are fetched without `prefetch_related('options')`. In `DeliveryQuestionSerializer`, `get_options()` calls `obj.options.all().order_by('order', 'option_key')` for every question individually. For a 100-question exam, this triggers 101 database queries (the classic N+1 problem). During a synchronized exam start where 100 students click "Start Exam" at 09:00, the database will be hit with over 10,000 queries simultaneously.
- What Codex got right: Question options are loaded individually per question without prefetching, generating severe N+1 query multiplication on exam start.
- What Codex got wrong or missed: None.
- Fix direction: In `build_attempt_payload()`, use `prefetch_related(Prefetch('options', queryset=Option.objects.order_by('order', 'option_key')))` when querying questions.
- Effort estimate: S
- Fix risk: Low; dramatically improves exam launch concurrency.

---

### CX-019
- Verdict: VALID
- Agy severity: Medium
- Agree with Codex severity? Yes (Medium)
- Evidence checked: `nginx/nginx.conf:16-47`; `docker-compose.yml:93-105`
- Reasoning: In `nginx/nginx.conf`, the `server` block defines `proxy_set_header X-Real-IP`, `X-Forwarded-For`, and `X-Forwarded-Proto`. However, location blocks like `location ~ ^/(api/|admin/...)` define their own `proxy_set_header Host $host;` and `proxy_set_header Connection "";`. In Nginx, if a `location` block defines any `proxy_set_header`, it completely overrides and ceases to inherit all parent-level `proxy_set_header` directives. Consequently, requests to the backend lose `X-Forwarded-Proto` and client IP headers.
- What Codex got right: Accurately identified standard Nginx inheritance behavior where child `proxy_set_header` drops parent proxy headers.
- What Codex got wrong or missed: None; this is a classic Nginx configuration trap.
- Fix direction: Move common proxy headers into an `include /etc/nginx/proxy_params;` file or declare the complete header set in each `location` block.
- Effort estimate: S
- Fix risk: Low; restores accurate client IP and scheme headers to Django.

---

### CX-020
- Verdict: BY DESIGN - RISKY
- Agy severity: Low
- Agree with Codex severity? No (Adjusted from Medium to Low)
- Evidence checked: `nginx/nginx.conf:12-20`; `docker-compose.yml:92-105`; `backend/config/settings.py:15-20`
- Reasoning: The base `docker-compose.yml` and `nginx/nginx.conf` expose port 80 over HTTP. For local development and self-hosted air-gapped school LAN environments (which was explicitly specified in requirement R5: *"The architecture must support deployment on an ordinary school computer or dedicated server without requiring paid cloud infrastructure"*), plain HTTP is the intended default. Production WAN deployment requires a reverse proxy (like Cloudflare, Traefik, or Let's Encrypt) to terminate TLS.
- What Codex got right: The tracked Compose configuration runs unencrypted HTTP by default.
- What Codex got wrong or missed: Missed that air-gapped local LAN deployment was an explicit project requirement where SSL certificates are often unavailable.
- Fix direction: Provide a `docker-compose.prod.yml` with certbot/TLS configuration and add clear WAN deployment documentation.
- Effort estimate: S
- Fix risk: Low.

---

### CX-021
- Verdict: VALID
- Agy severity: Medium
- Agree with Codex severity? Yes (Medium)
- Evidence checked: `backend/config/urls.py:5-9`; `backend/apps/core/views.py:24-63`
- Reasoning: In `backend/apps/core/views.py`, the `health_check()` view catches exceptions from database and Redis probes and appends `errors.append(f"Database error: {str(exc)}")` to the JSON response. If the database fails to connect, the exception string (which may include internal database hostnames, ports, and usernames) is returned in the HTTP response to unauthenticated callers.
- What Codex got right: Uncaught dependency exception strings leak internal environment details on public health endpoints.
- What Codex got wrong or missed: None.
- Fix direction: Log detailed exception traces to server logs and return generic error summaries (e.g., `{"database": "unavailable"}`) in the public JSON response.
- Effort estimate: S
- Fix risk: Low; eliminates information disclosure.

---

### CX-022
- Verdict: VALID
- Agy severity: Medium
- Agree with Codex severity? Yes (Medium)
- Evidence checked: `backend/apps/engine/views.py:229-537`; `backend/apps/engine/consumers.py:49-109`
- Reasoning: Attempt lifecycle rules (checking remaining time, incrementing tab switches, and updating statuses) are implemented separately across five HTTP views (`StartAttemptView`, `HeartbeatView`, `SaveResponseView`, `SubmitAttemptView`, `ProctoringEventView`) and duplicated inside `ExamAttemptConsumer.receive_json()`. In the consumer, a tab switch event increments `tab_switch_count` but never triggers auto-submit, whereas the HTTP proctoring view auto-submits when count exceeds `max_allowed`.
- What Codex got right: Attempt lifecycle logic and proctoring rules diverge between HTTP and WebSocket handlers due to code duplication.
- What Codex got wrong or missed: None.
- Fix direction: Refactor attempt state transitions, deadline checking, and proctoring event processing into a shared service module (e.g., `backend/apps/engine/services.py`).
- Effort estimate: M
- Fix risk: Low; guarantees consistent behavior across all transports.

---

### CX-023
- Verdict: VALID
- Agy severity: Low
- Agree with Codex severity? Yes (Low)
- Evidence checked: `frontend/src/pages/student/ExamCBTPage.tsx:91-94, 163-201`; `backend/apps/engine/views.py:26-33, 470-491`
- Reasoning: In `ExamCBTPage.tsx`, the timer initialization code reads `setRemainingSeconds(payload.remaining_seconds || 3600)`. In JavaScript, `0 || 3600` evaluates to `3600` because `0` is falsy. If a candidate resumes an attempt that has already expired (`remaining_seconds === 0`), the timer resets to 1 hour (3600 seconds) on the client until the next heartbeat arrives, causing visual confusion and allowing futile interactions.
- What Codex got right: JavaScript falsy fallback `payload.remaining_seconds || 3600` mistakenly treats `0` as missing and defaults to 1 hour.
- What Codex got wrong or missed: None.
- Fix direction: Replace with nullish coalescing: `setRemainingSeconds(payload.remaining_seconds ?? 3600)`.
- Effort estimate: S
- Fix risk: Low; simple 1-line bug fix.

---

### CX-024
- Verdict: VALID
- Agy severity: Low
- Agree with Codex severity? Yes (Low)
- Evidence checked: `frontend/src/components/FinishConfirmationModal.tsx:86-110, 169-190`
- Reasoning: `FinishConfirmationModal` renders a custom modal using plain `<div>` elements without `role="dialog"`, `aria-modal="true"`, or `aria-labelledby`. It lacks focus-trapping logic, meaning a keyboard user pressing Tab can navigate behind the modal and interact with question options on the underlying canvas while the confirmation overlay is displayed.
- What Codex got right: Modal lacks ARIA dialog semantics and keyboard focus trapping.
- What Codex got wrong or missed: None.
- Fix direction: Add `role="dialog"`, `aria-modal="true"`, `aria-labelledby`, and trap focus within the modal buttons.
- Effort estimate: S
- Fix risk: Low; improves accessibility.

---

### CX-025
- Verdict: VALID-ADJUSTED
- Agy severity: Info
- Agree with Codex severity? No (Adjusted from Low to Info)
- Evidence checked: `management/architecture_decisions.md:124-159`; `README.md:62`; `backend/apps/analytics/views.py:194-197, 286-300`; `frontend/src/pages/student/ExamCBTPage.tsx:210-231, 743`
- Reasoning: In ADR-005, asynchronous grading via Celery was specified, but in `backend/apps/analytics/views.py`, grading is executed synchronously inside `evaluate_examination(exam.pk)` for architectural simplicity during milestones M1-M4. In the UI, simple browser window blur events are labeled "AI Proctoring". These are documentation and marketing discrepancies rather than functional defects.
- What Codex got right: Code uses synchronous evaluation instead of Celery worker tasks, and copy calls basic window-blur detection "AI proctoring".
- What Codex got wrong or missed: Overstated significance; this is an internal ADR documentation gap that does not impair the functioning platform.
- Fix direction: Update `README.md` and ADR-005 to reflect synchronous grading as the default with Celery as optional scale mode, and adjust UI text to "Proctoring Telemetry".
- Effort estimate: S
- Fix risk: None.

---

### CX-026
- Verdict: VALID
- Agy severity: Low
- Agree with Codex severity? Yes (Low)
- Evidence checked: `docker-compose.yml:17-43, 110-112`; `README.md:44-76`; repository tree at `9ffb3b3`
- Reasoning: While `docker-compose.yml` mounts named volumes for Postgres and Redis data persistence, there are no backup scripts (`pg_dump` automation), disaster recovery runbooks, `.env.example` templates, or formal software license files tracked in the repository.
- What Codex got right: Repository lacks backup/restore automation scripts, environment templates, and license files.
- What Codex got wrong or missed: None.
- Fix direction: Add `.env.example`, `scripts/backup_db.sh`, `scripts/restore_db.sh`, and an open-source `LICENSE` file.
- Effort estimate: S
- Fix risk: Low.

---

### CX-027
- Verdict: ALREADY HANDLED
- Agy severity: None
- Agree with Codex severity? No (Already handled in commits `ba184b4` and `9ffb3b3`)
- Evidence checked: `docker-compose.yml`; `nginx/nginx.conf`; git commit log at `9ffb3b3` and `37e1781`
- Reasoning: Codex noted that the local working tree had unstaged modifications to `docker-compose.yml` and `nginx/nginx.conf` that differed from remote origin. Those changes were authored during Milestone M5 hardening and have since been committed and pushed to GitHub main branch.
- What Codex got right: At the moment of Codex's inspection, local files had uncommitted differences.
- What Codex got wrong or missed: Those changes were part of the active M5 hardening process and are now fully committed to `origin/main`.
- Fix direction: No action needed; working tree is clean.
- Effort estimate: S
- Fix risk: None.

---

### CX-028
- Verdict: VALID-ADJUSTED
- Agy severity: Info
- Agree with Codex severity? Yes (Info)
- Evidence checked: `tests/conftest.py:42-97`; `backend/config/settings.py:8-15`; `docker-compose.yml:3-23`
- Reasoning: Hardcoded fallback values like `SECRET_KEY = 'django-insecure-ezexam-dev-secret-key-m1-2026'` and test fixture passwords exist in the codebase. However, `settings.py` explicitly reads from `os.environ.get('SECRET_KEY')`, and `docker-compose.yml` uses mandatory interpolation `${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD}`. No real production secrets or private keys were leaked.
- What Codex got right: Development defaults and test credentials are tracked in source code.
- What Codex got wrong or missed: Correctly identified this as Info rather than a high vulnerability.
- Fix direction: Enforce a runtime error if `SECRET_KEY` is not provided when `DEBUG=False`.
- Effort estimate: S
- Fix risk: Low.
