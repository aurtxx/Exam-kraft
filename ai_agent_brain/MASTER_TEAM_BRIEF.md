# EXAM-KRAFT — MASTER PROJECT TEAM BRIEF
> Generated: 2026-11-25 | Coordinator: Antigravity (AGY)  
> Repo: `/Users/aurtx/teamwork_projects/ezexam_reconstruction`  
> GitHub: `https://github.com/aurtxx/Exam-kraft` (branch `fix/audit-batch-2` is HEAD)

---

## 1. PROJECT OVERVIEW

**Exam-Kraft** is a full-stack open-source CBT (Computer-Based Test) platform for Indian competitive exam coaching institutes (JEE/NEET/NTA patterns). It runs Django (REST) + React (Vite/TypeScript) + PostgreSQL/SQLite + Redis.

The codebase was reconstructed clean-room from scratch (M1–M5 complete) and is now undergoing a multi-batch security + correctness audit plus a full frontend-backend integration overhaul. **Almost every student-facing flow has at least one critical bug.** The examinations engine is 70% functional; the remaining 30% covers question-type handling, offline sync, timer drift, analytics display, and security hardening.

---

## 2. CURRENT STATE

### Services (live)
| Service | Location | Status |
|---------|----------|--------|
| Django backend | `localhost:8000` | ✅ RUNNING |
| Vite frontend | `localhost:5173` | ✅ RUNNING |
| SQLite (dev DB) | `backend/db.sqlite3` | ✅ CONNECTED |
| Redis | `:6379` | ✅ CONNECTED |

### Git State
- **HEAD branch**: `fix/audit-batch-2` (5 commits ahead of `main`)
- **26 modified working-tree files** (login fix, frontend improvements, examinations/accounts/engine patches)
- **origin/main** is at `9ffb3b3` — Batch 1 & 2 fixes are NOT yet pushed

### Demo Credentials
| Role | Username | Password |
|------|----------|----------|
| Superuser (Django admin) | `admin` | `admin123` |
| Staff OrgAdmin | `orgadmin@ezexam.local` | `admin123` |
| Student | `candidate110@ezexam.local` | `student123` |

### Known Published Exam ID
- `ef502f0f-9e3f-4e63-9c79-ad6c67590883` — use this for student testing

---

## 3. COMPLETED WORK

| Phase | Status | Branch/Commit |
|-------|--------|---------------|
| M1–M5 (full codebase build) | ✅ Done | `9ffb3b3` on `main` |
| Batch 0 (Preflight fixes) | ✅ Done | in working tree |
| Batch 1 (Answer-key exposure) | ✅ Done | `fix/audit-batch-1` |
| Batch 2 (Attempt integrity) | ✅ Done | `fix/audit-batch-2` |
| Codex browser integration pass | ✅ Done | working tree |
| Hydrogen browser QA (F-01–F-22) | ✅ Done | `audit_browser/` |

---

## 4. CRITICAL BUGS — MUST FIX NEXT (Batch 4: Frontend)

### BUG-01 · ONE_WORD question type completely broken [CRITICAL]
**File**: `frontend/src/pages/student/ExamCBTPage.tsx` lines 601–643  
**Problem**: The CBT engine only has two branches for question rendering: `NUMERICAL` (shows VirtualNumpad) and everything else (shows MCQ options). `ONE_WORD`, `SUBJECTIVE`, `SINGLE_DIGIT`, `TRUE_FALSE`, `CODING` all fall into "Single Correct Option" with zero options rendered → completely unanswerable.  
**Fix required**:
```tsx
// In ExamCBTPage.tsx, replace the input rendering block:
{currentQuestion.question_type === 'NUMERICAL' || currentQuestion.question_type === 'SINGLE_DIGIT' ? (
  <VirtualNumpad value={numericalValue} onChange={setNumericalValue} />
) : currentQuestion.question_type === 'ONE_WORD' || currentQuestion.question_type === 'SUBJECTIVE' ? (
  <div className="pt-2">
    <label className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 block">
      {currentQuestion.question_type === 'SUBJECTIVE' ? 'Write your answer:' : 'Enter one word answer:'}
    </label>
    <input
      type="text"
      value={numericalValue}
      onChange={(e) => setNumericalValue(e.target.value)}
      className="w-full px-4 py-3 rounded-xl border-2 border-primary-400 text-base font-mono focus:outline-none focus:ring-2 focus:ring-primary-500/30 min-h-[48px]"
      placeholder={currentQuestion.question_type === 'SUBJECTIVE' ? 'Write your answer here...' : 'Type one word...'}
      autoComplete="off"
    />
  </div>
) : currentQuestion.question_type === 'TRUE_FALSE' ? (
  <div className="space-y-3 max-w-xs">
    {[{key: 'TRUE', label: 'True'}, {key: 'FALSE', label: 'False'}].map(opt => (
      <div key={opt.key} onClick={() => handleOptionSelect(opt.key)} className={`...`}>{opt.label}</div>
    ))}
  </div>
) : (
  // MCQ options rendering
)}
```
Also fix the type badge at line 565–569 to handle all types, not just NUMERICAL/MCQ_MULTI.

**Also fix**: `saveCurrentResponse()` at line 278–285 — set `numerical_value` for `ONE_WORD`/`SUBJECTIVE` responses using `numericalValue` state (already done for NUMERICAL).

---

### BUG-02 · Numerical answer input is display-only widget [HIGH]
**File**: `frontend/src/components/VirtualNumpad.tsx`  
**Problem**: The VirtualNumpad shows a read-only `<div>` as the display, not a physical `<input>`. Hardware keyboard input is completely ignored — users on PC must click every digit. Breaks NTA CBT convention.  
**Fix required**:
1. Replace the display `<div>` (line 56–58) with a full-width `<input type="text">` that is focused on mount and accepts direct keyboard entry.
2. Add `onKeyDown` handler to accept digits, `.`, `-`, Backspace.
3. The numpad buttons should still work alongside keyboard.
4. Minimum height: 48px. Width: full container width.
5. Add keyboard shortcut hint label "or type directly".

---

### BUG-03 · LaTeX/MathML renders literal backslashes [MEDIUM]
**File**: `frontend/src/components/MathRenderer.tsx`  
**Problem**: The custom MathRenderer attempts to parse raw LaTeX tokens into MathML elements. It fails silently and returns the raw string (with literal backslashes) for most real-world expressions like `\sin(x)`, `\cos(x)`, `\sum_{n=1}^{10} n`.  
**Root cause**: The tokenizer regex and AST builder don't handle `\sum`, `\int`, `\lim`, function names like `\sin`, `\cos`, `\log`, nested grouping `{...}` with operators, or any display-mode constructs.  
**Fix required**: Replace the hand-rolled renderer with **KaTeX** (already a popular choice for this stack):
```bash
# In frontend/:
npm install katex @types/katex
```
```tsx
// MathRenderer.tsx — new implementation
import katex from 'katex';
import 'katex/dist/katex.min.css';

export function MathRenderer({ content, className = '' }: MathRendererProps) {
  if (!content) return null;
  const parts = content.split(/(\$\$[\s\S]*?\$\$|\$[^$]+?\$)/g);
  return (
    <div className={`whitespace-pre-wrap text-slate-800 leading-relaxed ${className}`}>
      {parts.map((part, i) => {
        if (part.startsWith('$$')) {
          const latex = part.slice(2, -2);
          try {
            return <span key={i} dangerouslySetInnerHTML={{ __html: katex.renderToString(latex, { displayMode: true, throwOnError: false }) }} />;
          } catch { return <span key={i}>{part}</span>; }
        } else if (part.startsWith('$')) {
          const latex = part.slice(1, -1);
          try {
            return <span key={i} dangerouslySetInnerHTML={{ __html: katex.renderToString(latex, { displayMode: false, throwOnError: false }) }} />;
          } catch { return <span key={i}>{part}</span>; }
        }
        return <span key={i}>{part}</span>;
      })}
    </div>
  );
}
```

---

### BUG-04 · ExamResultReportPage uses examId instead of attemptId [HIGH]
**File**: `frontend/src/pages/student/ExamResultReportPage.tsx` lines 22, 44  
**File**: `frontend/src/App.tsx` lines 37–40  
**Problem**: Route `/student/exam/:id/report` passes `examId` as `:id` param. The component calls `analyticsApi.getAttemptReport(id)` which hits `/api/v1/attempts/:id/report/` with an exam UUID → 404.  
**Fix**: Either:
- Option A: Add a dedicated route `/student/attempts/:attemptId/report` and navigate there after finish. `ExamFinishPage.tsx` should pass `attemptId` from `submitResult`.
- Option B: Add a backend alias endpoint `GET /api/v1/analytics/exam/:examId/my-report/` that looks up the user's latest attempt for that exam.  
**Recommended**: Option A — cleaner URL structure. The ExamFinishPage already receives `submitResult.attempt_id`.

---

### BUG-05 · Staff buttons show raw DOM modal IDs [LOW]
**File**: `frontend/src/pages/staff/ExaminationsPage.tsx`  
**Problem**: Button labels render as "New Examination (#new-exam-modal)" — the `#fragment-id` is literally in the JSX text.  
**Fix**: Remove all `(#...)` fragments from button labels. These are HTML Bootstrap-style data attributes that leaked into React button text.

---

### BUG-06 · ExaminationsPage card overflow at ~1100px viewport [LOW]
**File**: `frontend/src/pages/staff/ExaminationsPage.tsx`  
**Problem**: Exam cards overflow their container at medium viewport widths (1050px–1200px). Long exam names with status badges cause horizontal scroll.  
**Fix**: Add `overflow-hidden` + `truncate` on title element. Use `flex-wrap` on metadata row.

---

### BUG-07 · Brand name still "EZExam" everywhere [MEDIUM]
**Files**: 
- `frontend/src/pages/Login.tsx` lines 52, 54 — logo says "EZ", title says "EZExam Portal"
- `frontend/src/pages/student/ExamCBTPage.tsx` line 451 — CBT toolbar badge says "EZ"
- `frontend/index.html` — `<title>EZExam Platform</title>`  
**Fix**: Rename all to "Exam-Kraft". Replace "EZ" badge with the Exam-Kraft crown logo (SVG TBD). Update `<title>` in `frontend/index.html`.

---

### BUG-08 · VirtualNumpad not keyboard accessible [MEDIUM]
**File**: `frontend/src/components/VirtualNumpad.tsx`  
**Problem**: No `onKeyDown` handling; no `tabIndex`; display box has no accessible label.  
**Fix**: Part of BUG-02 fix above. Additionally add `aria-label="Numerical answer input"` and `role="textbox"`.

---

### BUG-09 · ONE_WORD/SUBJECTIVE responses use `selected_options` field incorrectly [HIGH]
**File**: `frontend/src/pages/student/ExamCBTPage.tsx` line 278–285 (saveCurrentResponse)  
**Problem**: For text-type questions, the response record should set `numerical_value` (or a new `text_value` field) with the typed text, NOT `selected_options`. Current code will send `numerical_value: null` for ONE_WORD if the student typed text into `numericalValue` state only if the type check at line 340 is correct.  
**Check**: Ensure `numericalValue` state is used for ONE_WORD/SUBJECTIVE and transmitted as `numerical_value` or add a `text_response` field.

---

## 5. BACKEND REMAINING AUDIT BATCHES

### Batch 3: Lifecycle & Data Retention [PENDING — awaiting user approval]
| Finding | File | Action |
|---------|------|--------|
| CX-006 | `examinations/views.py` → `PublishResultsView` | Add `finalize()` call to prevent score recalculation after publication |
| CX-011 | `engine/services.py` | Return D2 "PENDING_MANUAL_REVIEW" status for subjective questions |
| CX-012 | `examinations/models.py` | Validate `start_window < end_window`, reject past start |
| CX-009 | `question_bank/views.py`, `examinations/views.py` | Protect delete if exam is live/evaluated |
| AGY-007 | `question_bank/views.py` | Atomic replace for question options (currently non-atomic) |

### Batch 4: Frontend [PARALLEL with bug fixes above]
| Finding | Fix |
|---------|-----|
| CX-008 | Offline sync: submit queue flush on reconnect (already has localStorage cache, needs service-worker or beforeunload flush) |
| CX-023 + AGY-008 | Timer: heartbeat sync already implemented; verify `clockRef` reset on reconnect |
| CX-024 | Modal focus trap: `FinishConfirmationModal.tsx` needs `useFocusTrap()` hook |
| CX-025 | Numerical input redesign (covered by BUG-01 and BUG-02 above) |

### Batch 5: Gateway & Security [AFTER Batch 3]
| Finding | File | Action |
|---------|------|--------|
| CX-019 | `nginx/nginx.conf` | Strip `X-Forwarded-For` injection; add `proxy_set_header X-Real-IP` |
| CX-015 | `accounts/views.py` → `LoginView` | Add `django-ratelimit` decorator (5 attempts / 60s per IP) |
| AGY-002 | `config/settings.py` → `CORS_ALLOWED_ORIGINS` | Remove wildcard; use explicit list |
| AGY-005 | `config/settings.py` | Add `SECURE_BROWSER_XSS_FILTER`, `X_FRAME_OPTIONS = 'DENY'` |
| CX-016 | `accounts/views.py` → CSV import | Cap file size to 500KB; validate password complexity |
| CX-021 | `core/views.py` → `HealthView` | Strip exception tracebacks and internal hostnames from response |
| CX-018 | `engine/services.py` | Add `select_related` on delivery query (N+1 on sections) |
| CX-028 | `config/settings.py` | Assert `SECRET_KEY` is not default on startup |
| CX-020 | Root dir | Add `LICENSE` (MIT / AGPL non-commercial) |
| CX-026 | Root dir | Add `.env.example` with all required vars documented |
| CX-027 | Root `docker-compose.yml` + `nginx/nginx.conf` | Commit current working-tree changes |

### Batch 6: Tests & Docs [FINAL]
| Finding | Action |
|---------|--------|
| CX-010 | Write integration test for concurrent attempt creation (requires PostgreSQL; skip on SQLite) |
| AGY-003 | Add CSV import password validation test |
| AGY-004 | Add `UniqueConstraint` on `roll_number` per batch per organization |
| CX-025 docs | Add inline docstrings to `services.py` for `start_attempt` / `submit_attempt` |
| Rebranding | Update all "EZExam" strings to "Exam-Kraft" in backend `config/settings.py`, seed data, emails |

---

## 6. FRONTEND-BACKEND LINKING ISSUES

### API Routing Mismatches Found
| Frontend call | Backend URL | Status |
|---------------|-------------|--------|
| `POST /api/v1/student/attempts/start/` | ✅ `/api/v1/student/attempts/start/` | OK |
| `POST /api/v1/student/attempts/:id/responses/` | ✅ exists | OK |
| `POST /api/v1/student/attempts/:id/heartbeat/` | ✅ exists | OK |
| `POST /api/v1/student/attempts/:id/submit/` | ✅ exists | OK |
| `GET /api/v1/analytics/attempts/:id/report/` | ❓ verify URL in `analyticsApi.ts` | CHECK |
| `GET /api/v1/student/examinations/` | ✅ exists | OK |
| `GET /api/v1/auth/me/` | ✅ backend returns 200 | OK |
| Token refresh `POST /api/v1/auth/token/refresh/` | ✅ exists | OK |

### Type Gaps (frontend types vs backend serializer)
1. `CBTQuestion.question_type` should be a discriminated union — backend sends `ONE_WORD`, `SUBJECTIVE`, `CODING` but frontend CBT engine never handles them.
2. `CBTAttemptPayload.candidate` only has `roll_number` — missing `full_name` for greeting on CBT toolbar.
3. Backend `save_response` doesn't validate `ONE_WORD` responses have text — returns 200 for empty string.
4. `analyticsApi.getAttemptReport(id)` — verify the endpoint URL in `analyticsApi.ts` matches backend `analytics/urls.py`.

---

## 7. UNCOMMITTED CHANGES INVENTORY (working tree)

The following **26 files** have uncommitted modifications — these represent the Batch 1/2 fixes plus Codex integration work. They must be committed in order:

```
COMMIT GROUP A — Backend auth/login fix:
  backend/apps/accounts/views.py          (LoginView: auth_classes=[])
  backend/apps/accounts/serializers.py    (profile serializer fix)
  backend/config/settings.py              (CSRF trusted origins)
  backend/config/urls.py                  (URL routing updates)
  backend/manage.py                       (DJANGO_SETTINGS_MODULE)

COMMIT GROUP B — Backend exam/engine:
  backend/apps/examinations/views.py      (publish/assign endpoint fixes)
  backend/apps/examinations/serializers.py (delivery serializer)
  backend/tests/test_m2_all.py            (test updates)

COMMIT GROUP C — Frontend auth + routing:
  frontend/src/App.tsx                    (new routes for student)
  frontend/src/pages/Login.tsx            (role-aware redirect)
  frontend/src/components/layout/Shell.tsx (student vs staff sidebar)
  frontend/src/pages/NotFound.tsx         (branded 404 page)

COMMIT GROUP D — Frontend CBT + services:
  frontend/src/pages/student/ExamCBTPage.tsx
  frontend/src/pages/student/ExamLobbyPage.tsx
  frontend/src/pages/student/ExamFinishPage.tsx
  frontend/src/pages/student/ExamResultReportPage.tsx
  frontend/src/services/api.ts
  frontend/src/services/studentExamApi.ts
  frontend/src/types/index.ts
  frontend/src/components/MathRenderer.tsx

COMMIT GROUP E — Staff pages:
  frontend/src/pages/staff/ExaminationsPage.tsx
  frontend/src/pages/staff/QuestionBankPage.tsx
  frontend/src/pages/staff/StudentsPage.tsx

COMMIT GROUP F — Infra:
  docker-compose.yml
  nginx/nginx.conf
  README.md
  vite.config.ts

NEW UNTRACKED FILES (need git add):
  frontend/src/components/layout/ProtectedRoutes.tsx
  frontend/src/pages/student/CandidatePortal.tsx
  backend/apps/examinations/candidates.py
  audit_fix/   (entire directory)
  audit_browser/ (entire directory)
  audit_codex/  (read-only — do not modify)
  audit_agy/    (read-only — do not modify)
  scripts/      (sentinel daemon)
```

---

## 8. WORK ASSIGNMENT FOR TEAM

### AGENT: AGY (Antigravity) — Code Author
**Owns**: All file edits, test runs, commits  
**Next tasks in priority order**:
1. Fix BUG-01 (ONE_WORD/SUBJECTIVE/TRUE_FALSE question types in ExamCBTPage)
2. Fix BUG-02 (VirtualNumpad keyboard input)
3. Fix BUG-03 (MathRenderer → KaTeX migration)
4. Fix BUG-04 (ExamResultReportPage route param mismatch)
5. Fix BUG-05, BUG-06 (ExaminationsPage cosmetics)
6. Fix BUG-07 (rebrand EZExam → Exam-Kraft strings)
7. Run all tests, commit as "fix(batch-4): frontend CBT question types, KaTeX, report routing"
8. After user approval: execute Batch 3 (backend lifecycle)
9. After user approval: execute Batch 5 (gateway security)
10. After user approval: execute Batch 6 (tests + docs + rebranding)

### AGENT: Hydrogen (Browser QA)
**Owns**: Manual browser verification after each batch lands  
**Next tasks**:
1. After BUG-01 fix: Retest ONE_WORD and SUBJECTIVE question types in live CBT
2. After BUG-02 fix: Verify keyboard input on numerical questions
3. After BUG-03 fix: Verify LaTeX renders in Question Bank and CBT runner
4. After BUG-04 fix: Verify ExamResultReportPage loads with correct data
5. After Batch 3 lands: Retest F-07 (draft exam not startable), F-08 (edit window blocked)
6. After Batch 5 lands: Retest F-21 (health endpoint clean), F-22 (question paper 403)
7. File a new HB-006 for any new issues found

### AGENT: Teamwork Orchestrator
**Owns**: Coordination, status tracking, unblocking dependencies  
**Tasks**:
1. Track batch completion status
2. Ensure Batch 3 user approval before proceeding
3. Coordinate parallel work between AGY and Hydrogen
4. Alert user when test suite drops below 100% pass rate
5. Track the 26 uncommitted files and ensure they get committed in logical groups

---

## 9. TEST SUITE STATUS

```bash
# Backend (run from /backend):
.venv/bin/python manage.py test apps --verbosity=1   # 83/83 expected
.venv/bin/pytest tests/ -v                            # 104/104 expected

# Frontend (run from /frontend):
npm run build                                          # must succeed 0 errors
npm run typecheck                                      # must succeed 0 TS errors
```

**After every fix batch**: Both suites must pass 100% before commit.

---

## 10. CONSTRAINTS (NEVER VIOLATE)

1. **Never push to `origin/main`** without explicit user instruction
2. **Never edit** `audit_codex/` or `audit_agy/` — these are immutable audit inputs
3. **One batch at a time** — stop and wait for user approval before starting the next audit batch
4. **Non-commercial license** — Exam-Kraft is open-source, not for commercial resale
5. **Logo**: Keep "K" in Exam-Kraft; brand icon is a 3-pronged crown/E atop a flared K pedestal (SVG to be designed)
6. **Deferred items** (DO NOT implement): HttpOnly refresh cookie, manual grading UI, pagination for exam list, question shuffling (CX-013 part 2)
7. **Sentinel daemon** must stay running (`scripts/sentinel_auto_resume.sh`)
8. **Secrets**: Never print `SECRET_KEY` or token values in logs/artifacts

---

## 11. QUICK REFERENCE — KEY FILE PATHS

| What | Path |
|------|------|
| CBT Engine (frontend) | `frontend/src/pages/student/ExamCBTPage.tsx` |
| Math renderer | `frontend/src/components/MathRenderer.tsx` |
| Virtual numpad | `frontend/src/components/VirtualNumpad.tsx` |
| Student API service | `frontend/src/services/studentExamApi.ts` |
| App routes | `frontend/src/App.tsx` |
| Auth context | `frontend/src/context/AuthContext.tsx` |
| Type definitions | `frontend/src/types/index.ts` |
| Exam result report | `frontend/src/pages/student/ExamResultReportPage.tsx` |
| Examinations staff page | `frontend/src/pages/staff/ExaminationsPage.tsx` |
| Django engine views | `backend/apps/engine/views.py` |
| Django engine services | `backend/apps/engine/services.py` |
| Django engine models | `backend/apps/engine/models.py` |
| Settings | `backend/config/settings.py` |
| Backend URLs | `backend/config/urls.py` |
| Audit findings | `audit_browser/HB-001.md` through `HB-005.md` |
| Batch reports | `audit_fix/batch0_report.md`, `batch1_report.md`, `batch2_report.md` |
