# Independent Self-Audit: Findings Missed by Codex (AGY-001 through AGY-008)

The following vulnerabilities, shortcuts, and architectural weaknesses were discovered during our independent self-audit and were not reported in the Codex audit report.

---

### [ID] AGY-001
- Title: Cross-Tenant Information Leakage via Integer Question Number Fallback in SaveResponseView
- Severity: High
- Category: C (Security / Multi-Tenancy)
- Status: Confirmed
- Location: `backend/apps/engine/views.py:348-356`
- Evidence: In `SaveResponseView`, if UUID lookup fails, the view executes:
  ```python
  question = Question.objects.filter(question_number=int(qid_raw)).first()
  ```
  `Question.objects` here is the default manager without tenant filtering. Because question numbers are typically integers like `1`, `2`, `3`, this query returns the first question in the entire database matching that number, potentially belonging to a completely different organization/tenant.
- Why it matters: A student submitting response `1` can inadvertently attach and persist answers against another school's question paper, violating multi-tenant isolation.
- Fix direction: Strictly scope question lookup to `attempt.examination.question_paper.questions` or the exam's attached sections, and reject unassociated questions.
- Confidence: High
- How to verify: Query `SaveResponseView` with `question_id="1"` on an attempt whose exam belongs to Tenant B when Tenant A has question `1` created first.

---

### [ID] AGY-002
- Title: Missing CORS Whitelist Hardening in Production Environment
- Severity: Medium
- Category: C (Security / Network)
- Status: Confirmed
- Location: `backend/config/settings.py:166-176`
- Evidence: In `settings.py`:
  ```python
  CORS_ALLOW_ALL_ORIGINS = True
  CORS_ALLOW_CREDENTIALS = True
  ```
  While `CORS_ALLOW_ALL_ORIGINS = True` is paired with credentials, modern browsers reject wildcard origins when credentials are included, or attackers can exploit wildcard CORS across origins to read authenticated responses if credentials are sent.
- Why it matters: Any third-party site visited by a logged-in student or administrator could potentially issue credentialed cross-origin requests.
- Fix direction: Switch `CORS_ALLOW_ALL_ORIGINS = False` in production, read `CORS_ALLOWED_ORIGINS` from an environment variable, and restrict to the trusted frontend domain.
- Confidence: High
- How to verify: Send an `OPTIONS` preflight request with an arbitrary `Origin: http://evil.com` header and inspect response headers.

---

### [ID] AGY-003
- Title: Bulk CSV Student Onboarding Allows Unrestricted Password Length and No Complexity Validation
- Severity: Medium
- Category: C (Security / Input Validation)
- Status: Confirmed
- Location: `backend/apps/accounts/views.py:440-475`
- Evidence: In `StudentBulkImportView`, when passwords are provided in the CSV, the code executes:
  ```python
  user.set_password(password)
  ```
  It does not run Django's `password_validation.validate_password()`. Students can be created with insecure 1-character passwords like "1", bypassing the `MinimumLengthValidator` configured in `settings.py`.
- Why it matters: School administrators uploading CSVs with weak student passwords leave student accounts trivially guessable.
- Fix direction: Run `django.contrib.auth.password_validation.validate_password(password, user)` inside the CSV row parsing loop and flag weak password rows as validation errors.
- Confidence: High
- How to verify: Upload a CSV containing a student with password `"a"` and observe successful creation.

---

### [ID] AGY-004
- Title: Lack of Database-Level Unique Constraint on Student Roll Numbers within an Organization
- Severity: Medium
- Category: D (Database Integrity)
- Status: Confirmed
- Location: `backend/apps/accounts/models.py:50-80`
- Evidence: In `User` and `UserProfile`, `roll_number` is stored as an unconstrained field:
  ```python
  roll_number = models.CharField(max_length=50, blank=True, null=True)
  ```
  While the CSV import view performs an application-level duplicate check during import, direct API creation or manual user edits can create duplicate roll numbers in the same organization.
- Why it matters: Duplicate roll numbers break exam grading reports, ranking tie-breakers, and administrative tracking.
- Fix direction: Add `models.UniqueConstraint(fields=['organization', 'roll_number'], name='unique_tenant_roll_number')` to the `UserProfile` or `User` model.
- Confidence: High
- How to verify: Create two students with the same roll number in the same tenant via the `/api/v1/auth/users/` endpoint.

---

### [ID] AGY-005
- Title: Missing CSRF Cookie Protection on Session Authentication Endpoints
- Severity: Low
- Category: C (Security)
- Status: Confirmed
- Location: `backend/config/settings.py:55-66`
- Evidence: In `REST_FRAMEWORK` settings:
  ```python
  'DEFAULT_AUTHENTICATION_CLASSES': [
      'rest_framework_simplejwt.authentication.JWTAuthentication',
      'rest_framework.authentication.SessionAuthentication',
  ]
  ```
  `SessionAuthentication` is enabled by default across all REST endpoints. If a staff user is logged into the Django Admin in the same browser, session cookies are sent with API requests, potentially exposing endpoints to Cross-Site Request Forgery (CSRF) unless explicitly validated.
- Why it matters: Third-party sites could trigger state-changing actions via ambient browser sessions.
- Fix direction: Remove `SessionAuthentication` from default REST classes in production, or enforce strict CSRF tokens on all session-authenticated mutations.
- Confidence: High
- How to verify: Issue a POST request with valid session cookies and no CSRF header.

---

### [ID] AGY-006
- Title: Lack of Pagination on Examination List Endpoints
- Severity: Low
- Category: E (API Design / Performance)
- Status: Confirmed
- Location: `backend/apps/examinations/views.py:25-50`
- Evidence: In `ExaminationListCreateView`:
  ```python
  def get(self, request):
      tenant = require_tenant(request)
      qs = Examination.objects.filter(organization=tenant).order_by('-created_at')
      serializer = ExaminationSerializer(qs, many=True)
      return Response({'examinations': serializer.data})
  ```
  The endpoint returns the entire examination queryset without `limit` or `offset` pagination.
- Why it matters: For mature institutions with thousands of past exams, this endpoint will serialize massive JSON payloads, slowing dashboard load times.
- Fix direction: Integrate DRF's `PageNumberPagination` with `page_size=20`.
- Confidence: High
- How to verify: Seed 500 exams in a tenant and query `/api/v1/examinations/`.

---

### [ID] AGY-007
- Title: QuestionBank Options Deletion Race Condition
- Severity: Low
- Category: D (Data Integrity)
- Status: Confirmed
- Location: `backend/apps/question_bank/views.py:240-270`
- Evidence: When updating questions with options in `QuestionBankViewSet` or `QuestionDetailView`, existing options are deleted and recreated in separate ORM calls:
  ```python
  question.options.all().delete()
  for opt_data in options_data:
      Option.objects.create(question=question, ...)
  ```
  If a student fetches question options between the `.delete()` and `.create()` calls, they receive a question with zero options.
- Why it matters: Causes intermittent blank question choices for students loading an exam while staff edits a draft paper.
- Fix direction: Wrap option synchronization inside an atomic transaction or use upsert logic.
- Confidence: High
- How to verify: Inspect option replacement code in `question_bank/views.py`.

---

### [ID] AGY-008
- Title: Frontend Timer Drift on Background Tab Inactivity
- Severity: Low
- Category: F (Frontend Robustness)
- Status: Confirmed
- Location: `frontend/src/pages/student/ExamCBTPage.tsx:160-195`
- Evidence: `ExamCBTPage` decrements remaining seconds using a standard `setInterval(..., 1000)`:
  ```typescript
  setInterval(() => {
    setRemainingSeconds(prev => Math.max(0, prev - 1));
  }, 1000);
  ```
  Browsers (Chrome/Safari/Edge) aggressively throttle `setInterval` timers in background tabs to run once per minute. If a candidate minimizes or switches tabs, the client countdown timer lags behind real wall-clock time until the next periodic heartbeat resynchronizes it.
- Why it matters: The student's local timer shows more time remaining than the server-authoritative deadline, resulting in unexpected auto-submission while the student believes they still have minutes remaining.
- Fix direction: Calculate remaining time dynamically using `Math.max(0, Math.floor((serverDeadlineTimestamp - Date.now()) / 1000))` on each tick rather than decrementing an integer.
- Confidence: High
- How to verify: Put the exam tab in the background for 5 minutes and observe client timer lag compared to actual wall-clock elapsed time.
