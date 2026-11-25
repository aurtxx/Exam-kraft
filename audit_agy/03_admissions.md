# Admissions: What We Got Wrong and Where We Cut Corners

As the original builder of the reconstructed **Exam-Kraft** platform, here is an unsparing, candid assessment of shortcuts, architectural assumptions, and compromises made during the multi-agent development sprints:

---

## 1. Concurrency and Race Conditions
- **What We Cut Corners On**: In our rush to verify the NTA 5-state palette and exam flows, we implemented pessimistic row-locking (`select_for_update()`) in `SubmitAttemptView`, but failed to apply that same lock to `SaveResponseView` or `ProctoringEventView`.
- **Related Findings**: `CX-004`, `CX-005`, `CX-022`.
- **The Reality**: We falsely assumed that because students generally take tests sequentially, overlapping asynchronous HTTP requests from the same user would not collide. In reality, browser background autosaves, manual clicks, and proctoring events routinely interleave. Omitting row locks in `SaveResponseView` created a genuine window where post-submission writes could corrupt finalized exams.

## 2. Security Boundaries & Authorization Scoping
- **What We Cut Corners On**: We used DRF's convenient generic permissions (`IsOrgAdminOrReadOnly`) on the question bank views (`QuestionListCreateView`, `QuestionDetailView`), forgetting that "read-only" allows all authenticated students in the organization to read full question objects with answer keys and correct options.
- **Related Findings**: `CX-001`, `CX-002`, `CX-003`, `CX-014`, `AGY-001`.
- **The Reality**: We conflated "tenant membership" with "authorized staff". Because students and faculty share the same tenant, any view with `IsOrgAdminOrReadOnly` inadvertently leaked secret examination keys. In the WebSocket consumer (`consumers.py`), we accepted connections before authenticating the user, leaving proctoring metrics open to spoofing.

## 3. Test Fixtures vs. Live Infrastructure
- **What We Cut Corners On**: To make the 104-case requirement test suite run in under 1 second without needing a live PostgreSQL server or Docker daemon, we routed the default E2E tests through an in-process HTTP mock transport (`tests/mock_server/contract_app.py`).
- **Related Findings**: `CX-010`.
- **The Reality**: While this verified contract payload schemas, it created an illusion of concurrency safety. The mock handler used in-memory Python locks, hiding the fact that `apps.engine.views` lacked database unique constraints on concurrent attempt initialization.

## 4. Assessment Lifecycle and Evaluation Completeness
- **What We Cut Corners On**: We implemented grading logic in `backend/apps/analytics/services.py` that handles MCQs and numerical questions, but when encountering `SUBJECTIVE` or `CODING` questions, it simply returned `Outcome.PENDING, ZERO`. We then allowed `PublishResultsView` to publish cohorts with unreviewed questions.
- **Related Findings**: `CX-006`, `CX-007`, `CX-011`.
- **The Reality**: In production, publishing an exam with pending subjective answers would give students an instant 0 on their essays and code submissions without giving faculty an opportunity to grade them. Furthermore, we allowed early finishers to view scores and answer keys via `AttemptReportView` while peers were still sitting the active exam.

## 5. Offline Data Replay and Re-synchronization
- **What We Cut Corners On**: We added `localStorage` caching to `ExamCBTPage.tsx` to handle network disconnects, but upon clicking "Confirm Final Submission", we cleared `localStorage` immediately without verifying that all locally buffered offline answers had successfully synced to the backend.
- **Related Findings**: `CX-008`, `AGY-008`.
- **The Reality**: If a student answered questions while disconnected, their offline answers existed only in the browser cache. If they reconnected and submitted, the submission went through, but un-synced answers were wiped from the browser and marked as unattempted on the server.

## 6. Infrastructure & Deployment Hardening
- **What We Cut Corners On**: We provided a working `docker-compose.yml` and `nginx.conf`, but relied on default Nginx location blocks that broke proxy header inheritance (`X-Forwarded-Proto`, client IP), exposed unthrottled login endpoints, and did not include automated database backup scripts or environment templates.
- **Related Findings**: `CX-015`, `CX-016`, `CX-019`, `CX-020`, `CX-026`, `AGY-002`.
- **The Reality**: The deployment files were configured for local and test convenience rather than enterprise-grade production hardening.
