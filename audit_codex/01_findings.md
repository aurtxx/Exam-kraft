# Findings

### [ID] CX-001
- Title: Unauthenticated WebSocket can modify attempt telemetry
- Severity: Critical
- Category: C
- Status: Confirmed
- Location: backend/apps/engine/consumers.py:16-39,49-68,76-109 (9ffb3b3); backend/config/asgi.py:7-19
- Evidence: The consumer accepts before any user check and both database helpers use the URL attempt ID alone. The write helper persists an event and increments the switch counter.
- Why it matters: Anyone with an attempt ID can contaminate another student's proctoring record. HTTP heartbeat uses that counter to signal termination.
- Fix direction: Require an authenticated attempt owner or explicitly authorized operator before group join and enforce the same policy for every message.
- Confidence: High
- How to verify: Compare the connection and message paths against the ownership checks in HTTP heartbeat.

### [ID] CX-002
- Title: Student-readable authoring endpoints return answer keys
- Severity: Critical
- Category: B
- Status: Confirmed
- Location: backend/apps/question_bank/views.py:102-153,309-327; backend/apps/question_bank/serializers.py:44-51,103-139; backend/apps/accounts/permissions.py:51-67
- Evidence: Safe methods are open to authenticated tenant members including students. The question list and detail use QuestionSerializer with key and option correctness fields.
- Why it matters: Students in the same organization can see the grading key before or during the exam.
- Fix direction: Restrict authoring reads to authorized staff and define a separate candidate projection.
- Confidence: High
- How to verify: Review the effective GET roles and serialized fields together.

### [ID] CX-003
- Title: Attempt launch omits exam status and assignment checks
- Severity: High
- Category: B
- Status: Confirmed
- Location: backend/apps/engine/views.py:154-226; backend/apps/examinations/views.py:30-41,169-216
- Evidence: Start requires authentication and checks window bounds, then creates an attempt. It never compares the user with candidate assignments or checks published status. The same-tenant exam list includes drafts.
- Why it matters: An unassigned student can start a visible draft with an open or absent window.
- Fix direction: Require candidate role, tenant, enrollment and eligible lifecycle state in the launch transaction.
- Confidence: High
- How to verify: Trace start from exam lookup to creation alongside the assignment and list querysets.

### [ID] CX-004
- Title: Concurrent starts can create multiple attempts per candidate
- Severity: High
- Category: A
- Status: Confirmed
- Location: backend/apps/engine/views.py:192-226; backend/apps/engine/models.py:45-74; backend/apps/engine/migrations/0001_initial.py
- Evidence: Start checks for an existing row and then inserts separately. The only unique token is generated for each new row.
- Why it matters: Overlapping requests can create two clocks and result rows for the same student, weakening retake and ranking rules.
- Fix direction: Define attempt identity in the database and return the winning row on concurrent start.
- Confidence: High
- How to verify: Check the existence and insert sequence against model and migration uniqueness.

### [ID] CX-005
- Title: Autosave and proctoring can write after the submission lock
- Severity: High
- Category: A
- Status: Confirmed
- Location: backend/apps/engine/views.py:291-391,422-459,494-529
- Evidence: Submit locks the attempt row. Autosave checks a separately read status before writing the response. Proctoring saves status from its own previously loaded attempt.
- Why it matters: A concurrent save can change the answer set after finalization. A stale proctoring request can overwrite a completed status.
- Fix direction: Serialize all attempt mutations using one parent-row lock and enforce terminal transitions in that transaction.
- Confidence: High
- How to verify: Compare participating locks and each update_fields list.

### [ID] CX-006
- Title: Disconnected attempts can indefinitely prevent result publication
- Severity: High
- Category: A
- Status: Confirmed
- Location: backend/apps/engine/views.py:263-276,319-328; backend/apps/analytics/views.py:286-300; backend/config/celery.py; docker-compose.yml:75-81
- Evidence: The observed expiry transitions run on candidate traffic. Publication rejects any in-progress same-tenant attempt, even after its deadline. No scheduled expiry task is wired.
- Why it matters: A student losing power near the deadline can leave the entire cohort unable to receive published results.
- Fix direction: Finalize expired rows independently and reconcile expiration inside publication.
- Confidence: High
- How to verify: Trace expiry callers, Celery discovery and the publication predicate.

### [ID] CX-007
- Title: Attempt report bypasses result publication
- Severity: High
- Category: B
- Status: Confirmed
- Location: backend/apps/analytics/views.py:35-49,179-218,237-249,286-300
- Evidence: Student result lists require is_published. Attempt report checks submission and hide_results, evaluates on demand, and applies a separate answer policy.
- Why it matters: A student can receive scores before faculty release. Immediate reveal can disclose the key while other students are still sitting the same exam.
- Fix direction: Apply shared publication and exam closure rules to every candidate-facing result representation.
- Confidence: High
- How to verify: Compare the result list filters, report guards and publication transaction.

### [ID] CX-008
- Title: Cached offline responses can be discarded at final submission
- Severity: High
- Category: F
- Status: Confirmed
- Location: frontend/src/pages/student/ExamCBTPage.tsx:91-111,274-315,381-399; backend/apps/analytics/services.py:143-155
- Evidence: Recovery copies cached responses only when the server has no entry. Failed saves stay local. Final submit sends the reason and clears the cache after success.
- Why it matters: A candidate can see a locally saved response that never reaches the grader, or recover an older answer over a newer edit.
- Fix direction: Replay and acknowledge pending changes before reporting successful finalization and clearing the queue.
- Confidence: High
- How to verify: Trace an offline edit of an already saved answer through reload and final submit.

### [ID] CX-009
- Title: Deleting users or exams cascades into assessment records
- Severity: High
- Category: D
- Status: Confirmed
- Location: backend/apps/accounts/views.py:373-380; backend/apps/examinations/views.py:145-158; backend/apps/engine/models.py:49-57,90-101; backend/apps/analytics/models.py:6-25
- Evidence: Both detail endpoints support deletion. Attempt foreign keys cascade on user or exam deletion, and results and responses cascade from attempts.
- Why it matters: Routine roster or exam cleanup can erase grades and dispute evidence.
- Fix direction: Use explicit retention rules, archival and protected references for completed assessments.
- Confidence: High
- How to verify: Follow Django's cascade graph from both delete views.

### [ID] CX-010
- Title: Default E2E runs validate the mock, while default pytest excludes backend suites
- Severity: High
- Category: H
- Status: Confirmed
- Location: pytest.ini:1-12; tests/conftest.py:12-39; run_e2e_tests.sh:89-113; tests/tier2_boundaries/test_b9_concurrency_boundaries.py:12-26
- Evidence: Default collection targets tests/. Without BASE_URL, the fixture sends all calls to MockTransport. Parallel launch checks therefore default to the contract handler rather than Django and PostgreSQL.
- Why it matters: A green run can coexist with duplicate attempt creation in production.
- Fix direction: Run explicit backend and disposable PostgreSQL integration suites as release gates and label mock-only results.
- Confidence: High
- How to verify: Inspect collection paths and transport selection.

### [ID] CX-011
- Title: Pending subjective and code questions can receive published zero scores
- Severity: High
- Category: A
- Status: Confirmed
- Location: backend/apps/analytics/services.py:38-43,145-179; backend/apps/analytics/views.py:286-300; research/student_exam_ui_spec.md:144-149
- Evidence: Subjective and coding questions return PENDING and zero. Their maximum marks still count, and publication sets is_published for the cohort without checking pending reviews.
- Why it matters: A candidate can fail an exam whose manually graded or coding responses were never evaluated.
- Fix direction: Require complete grading or exclude unsupported question types from publishable assessments.
- Confidence: High
- How to verify: Trace PENDING through the maximum-score calculation and publication guard.

### [ID] CX-012
- Title: Published exam can retain a valid status with an invalid or changed schedule
- Severity: Medium
- Category: A
- Status: Confirmed
- Location: backend/apps/examinations/views.py:73-88,145-158,240-253; backend/apps/examinations/serializers.py:37-83
- Evidence: Create and publish perform window checks. Generic update locks the row but the serializer only prevents replacement of a published paper; it does not validate the effective combined windows.
- Why it matters: A schedule edit can strand later candidates or split deadlines between existing and new attempts.
- Fix direction: Validate merged edits and freeze timing fields at an explicit lifecycle boundary.
- Confidence: High
- How to verify: Compare the create, publish and partial-update paths and serializer fields.

### [ID] CX-013
- Title: Delivery exposes numeric acceptance bounds and uses fixed order
- Severity: Medium
- Category: B
- Status: Confirmed
- Location: backend/apps/engine/serializers.py:22-44; backend/apps/engine/views.py:41-76; backend/apps/analytics/services.py:45-65
- Evidence: The delivery projection excludes explicit option correctness but includes numerical_min and numerical_max. Grading uses those bounds. Delivery orders exam links, paper questions and options deterministically.
- Why it matters: Candidates can infer accepted numeric answers, and common ordering makes answer sharing easier.
- Fix direction: Keep grading parameters server-side and apply a persisted candidate permutation where exam policy requires it.
- Confidence: High
- How to verify: Compare delivery fields and sort orders with numeric grading.

### [ID] CX-014
- Title: Response endpoint bypasses exam membership and typed validation
- Severity: Medium
- Category: E
- Status: Confirmed
- Location: backend/apps/engine/views.py:331-391; backend/apps/engine/models.py:98-115; backend/apps/engine/serializers.py:47-67
- Evidence: Question lookup is global by UUID or first matching number. Raw selections and coerced time are written without running the response serializer or checking the attempt roster.
- Why it matters: Foreign responses can distort recovery counts. Invalid types or oversized values can produce inconsistent persistence or server errors depending on the database.
- Fix direction: Resolve questions from the attempt roster and validate answer shape, length and time before writing.
- Confidence: High
- How to verify: Compare lookup scope and write fields with question inventory, schema and grader input.

### [ID] CX-015
- Title: Login has no application-level throttling
- Severity: Medium
- Category: C
- Status: Confirmed
- Location: backend/apps/accounts/views.py:33-65; backend/config/settings.py:178-190; nginx/nginx.conf:12-48
- Evidence: Login is AllowAny. The view, REST defaults and checked-in reverse proxy configure no login throttle.
- Why it matters: Deployment without upstream limits permits sustained password guessing and expensive authentication traffic.
- Fix direction: Apply per-account and per-source limits and monitor failed logins.
- Confidence: High
- How to verify: Review throttle classes, REST defaults and gateway configuration.

### [ID] CX-016
- Title: Bulk CSV import reads the full upload into application memory
- Severity: Medium
- Category: C
- Status: Confirmed
- Location: backend/apps/accounts/views.py:387-416; nginx/nginx.conf:12-14
- Evidence: The tenant-admin import accepts multipart and reads the whole file before decoding. The local gateway allows up to 100 MB per request.
- Why it matters: Concurrent large imports can consume backend memory and interrupt exam traffic.
- Fix direction: Bound file size and row count before parsing and isolate bulk import work.
- Confidence: High
- How to verify: Compare the upload read path, parser choices and proxy limit.

### [ID] CX-017
- Title: Access and refresh credentials persist in browser storage
- Severity: Medium
- Category: C
- Status: Confirmed
- Location: frontend/src/context/AuthContext.tsx:65-101; frontend/src/services/api.ts:44-49,86-119
- Evidence: Both bearer credentials are written to localStorage and read from it during refresh.
- Why it matters: Script execution in the origin or access to a shared browser profile exposes reusable credentials.
- Fix direction: Limit refresh credential exposure using a browser session design with server-side revocation.
- Confidence: High
- How to verify: Review login, refresh and logout storage operations.

### [ID] CX-018
- Title: Candidate launch scales database round trips with question count
- Severity: Medium
- Category: D
- Status: Confirmed
- Location: backend/apps/engine/views.py:41-76,89-97; backend/apps/engine/serializers.py:42-44
- Evidence: The section path walks relations without prefetching. Every question serializer fetches sorted options separately.
- Why it matters: A synchronized exam start turns each candidate's paper delivery into many database calls.
- Fix direction: Load the complete ordered delivery graph in a bounded query plan.
- Confidence: High
- How to verify: Follow ORM evaluation and option serialization per question.

### [ID] CX-019
- Title: Local nginx location headers override shared proxy headers
- Severity: Medium
- Category: G
- Status: Confirmed
- Location: nginx/nginx.conf:16-47; docker-compose.yml:93-105
- Evidence: The working-tree server defines Host and forwarded headers at server level, while every proxy location defines its own proxy_set_header. nginx inherits the parent set only if no such directives exist at the child level.
- Why it matters: Backend requests can arrive with upstream host defaults and missing scheme and client-IP headers, affecting tenant resolution and HTTPS behavior.
- Fix direction: Declare the full required header set in each proxied location or share one include.
- Confidence: High
- How to verify: Compare the local location blocks with main and inspect effective headers on a disposable stack.

### [ID] CX-020
- Title: Gateway exposes plaintext HTTP by default
- Severity: Medium
- Category: G
- Status: Confirmed
- Location: nginx/nginx.conf:12-20; docker-compose.yml:92-105; backend/config/settings.py:15-20
- Evidence: The published gateway uses a plain HTTP listener and has no TLS termination or redirect in the reviewed files.
- Why it matters: Direct users can send credentials or answer data in plaintext unless deployment adds a trusted upstream terminator.
- Fix direction: Require HTTPS at the public edge and define a trusted forwarded-header boundary.
- Confidence: High
- How to verify: Check the published port, listener and secure-cookie environment switch.

### [ID] CX-021
- Title: Public health endpoint returns dependency exception text
- Severity: Medium
- Category: J
- Status: Confirmed
- Location: backend/config/urls.py:5-9; backend/apps/core/views.py:24-63
- Evidence: Probe exceptions are interpolated into a public JSON errors field.
- Why it matters: During an outage a caller may learn internal hosts or database authentication context while operators lack a structured correlation ID in that response.
- Fix direction: Publish coarse status and send sanitized diagnostics to an operator-only structured sink.
- Confidence: High
- How to verify: Review the exception-to-response path for both dependency failures.

### [ID] CX-022
- Title: Attempt lifecycle rules are duplicated across five handlers and two transports
- Severity: Medium
- Category: K
- Status: Confirmed
- Location: backend/apps/engine/views.py:229-537; backend/apps/engine/consumers.py:49-109
- Evidence: HTTP heartbeat, save, submit and proctoring each implement distinct status rules. WebSocket event processing implements separate validation and persistence behavior.
- Why it matters: Policy fixes can leave another path with stale semantics, as the two proctoring paths already differ in finalization behavior.
- Fix direction: Centralize ownership, expiration and state transitions behind one transactional service.
- Confidence: High
- How to verify: Compare event and expiry paths and their different writes.

### [ID] CX-023
- Title: Zero server time appears as one hour on recovery
- Severity: Low
- Category: A
- Status: Confirmed
- Location: frontend/src/pages/student/ExamCBTPage.tsx:91-94,163-201; backend/apps/engine/views.py:26-33,470-491
- Evidence: The UI uses remaining_seconds OR 3600, replacing zero. It later uses heartbeat to reconcile.
- Why it matters: An already expired attempt can briefly show generous remaining time and accept futile interaction.
- Fix direction: Preserve zero as a valid time and initialize the expired UI immediately.
- Confidence: High
- How to verify: Compare the backend zero clamp and UI fallback expression.

### [ID] CX-024
- Title: Finish confirmation omits accessible dialog semantics
- Severity: Low
- Category: F
- Status: Confirmed
- Location: frontend/src/components/FinishConfirmationModal.tsx:86-110,169-190
- Evidence: The overlay renders controls without a dialog role, modal state or a focus-management path.
- Why it matters: Keyboard and screen reader users may continue interacting with the underlying exam while the submission confirmation is open.
- Fix direction: Use an accessible dialog with labelled controls and focus restoration.
- Confidence: High
- How to verify: Inspect the rendered semantics and keyboard focus path.

### [ID] CX-025
- Title: Async evaluation and proctoring claims exceed shipped behavior
- Severity: Low
- Category: I
- Status: Confirmed
- Location: management/architecture_decisions.md:124-159; README.md:62; backend/apps/analytics/views.py:194-197,286-300; frontend/src/pages/student/ExamCBTPage.tsx:210-231,743
- Evidence: The ADR describes asynchronous grading and retryable recovery. Evaluation calls execute inline. The exam UI labels tab visibility events as AI proctoring. README identifies Gunicorn although the backend image invokes Daphne.
- Why it matters: Operators can expect isolation from grading latency and candidates can infer monitoring capabilities that are absent in the inspected flow.
- Fix direction: Bring the docs and UI copy into line with runtime behavior and verify promised capabilities before advertising them.
- Confidence: High
- How to verify: Compare claims with the request handlers, UI event listeners and Dockerfile command.

### [ID] CX-026
- Title: Recovery and release controls are absent from tracked deployment
- Severity: Low
- Category: J
- Status: Confirmed
- Location: docker-compose.yml:17-43,110-112; README.md:44-76; repository tree at 9ffb3b3
- Evidence: PostgreSQL and Redis have persistent volumes. No backup/restore procedure, CI workflow, env example or license file appears in the tracked tree.
- Why it matters: Volume persistence alone leaves data recovery unproven and ordinary code changes can ship without integration gates.
- Fix direction: Document recovery and configuration and track release checks, ownership and licensing.
- Confidence: High
- How to verify: Inspect tracked files and require a restore rehearsal with representative data.

### [ID] CX-027
- Title: Local deployment diverges from GitHub main
- Severity: Info
- Category: G
- Status: Confirmed
- Location: docker-compose.yml:15,54-81,103-105; nginx/nginx.conf:6-48; main 9ffb3b3
- Evidence: Both tips match, but local changes replace readiness URLs, alter worker topology and add a WebSocket proxy, forwarding changes and a larger upload limit.
- Why it matters: Operators reproducing from GitHub get different behavior than this checkout.
- Fix direction: Review the two working-tree diffs before choosing a deployment revision.
- Confidence: High
- How to verify: Compare git diff against HEAD and check GitHub main's advertised ref.

### [ID] CX-028
- Title: Historical test credentials and development defaults are tracked
- Severity: Info
- Category: C
- Status: Confirmed
- Location: tests/conftest.py:42-97 (3bb0eba); backend/config/settings.py:8-15; docker-compose.yml:3-23 (ba184b4)
- Evidence: Fixture passwords [masked] and the development signing fallback [masked] are tracked. Compose takes its signing and database credentials from environment variables. The history signature scan returned no matching private-key or provider-token file names.
- Why it matters: Using fixture credentials or debug defaults in a real environment would expose accounts or trust boundaries. Production reuse is unverified.
- Fix direction: Keep fixture identities isolated and make all non-local launches require explicit secrets and debug-off configuration.
- Confidence: High
- How to verify: Check environment provenance and deployment configuration without exposing values.
