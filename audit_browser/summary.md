# Gemini Hydrogen Browser Integration Pass — Summary

**Target Stack:** `http://localhost:5173` (Frontend) + `http://localhost:8000` (Backend)  
**Mode:** Token-efficient minimal-snapshot browser walkthrough  

## Flow Checklist (F-01 to F-22)

| Flow | Status | Evidence |
|---|---|---|
| F-01 Staff Login | PASS | `orgadmin@ezexam.local` -> `200`, redirected to `/staff/exams`, loaded `/api/v1/examinations/` |
| F-02 Invalid Login | PASS | Wrong password -> `401`, error banner shown, `/staff/exams` redirects to `/login` |
| F-03 Student Login | PASS | `candidate110@ezexam.local` -> `200`, landed on `/student`, 0 staff nav links |
| F-04 Token Refresh | PARTIAL | Refresh token issued; expiry cycle not forced in-browser |
| F-05 Logout & Back | PASS | `Sign out` -> `/login`; `goBack()` stays on `/login` |
| F-06 Question Bank | PARTIAL | Staff `/staff/question-bank` loaded 16 questions; student redirected to `/student` by SPA guard |
| F-07 Staff Exams | PASS | `/staff/exams` loaded 4 exams (`200`) |
| F-08 Staff Mutations | SKIPPED | Depends on Batch 2/3 |
| F-09 Exam Lobby & Start | PASS | Lobby -> `POST /api/v1/student/attempts/start/` (`200`), timer & palette rendered |
| F-10 MCQ Save & Next | PASS | `save_response` sent question UUID (`200`), no `is_correct`/`key` in delivery |
| F-11 Numerical Field | FAIL | Left-aligned read-only `div` (`46px` height) inside narrow Virtual Keypad; no `<input>`, ignores keyboard |
| F-12 Exam Submission | SKIPPED | Kept attempt open for F-13/F-16 |
| F-13 Report Blocked | PARTIAL | Attempt UUID returned `400` ("Attempt has not been submitted yet"); examId route returned `404` |
| F-14 Question Types | FAIL | `ONE_WORD` (Q4) renders as `"Single Correct Option"` with 0 options & 0 inputs (unanswerable) |
| F-15 Mark/Clear | SKIPPED | Depends on Batch 2+ |
| F-16 Proctoring Tab-Switch | PASS | Tab switch -> `POST .../proctoring_event/` (`200`), warning banner displayed |
| F-17–F-20 | SKIPPED | Depends on Batch 3/4/5 |
| F-21 Health Check | PASS | `GET /api/v1/health/` -> `200` (`healthy`, DB & Redis connected) |
| F-22 RBAC Isolation | PARTIAL | Frontend guard redirected student `/staff/question-bank` to `/student` |

## Filed Findings
- [HB-001.md](file:///Users/aurtx/teamwork_projects/ezexam_reconstruction/audit_browser/HB-001.md) — **F-11 Numerical Answer Field Redesign** (High / UI-Issue)
- [HB-002.md](file:///Users/aurtx/teamwork_projects/ezexam_reconstruction/audit_browser/HB-002.md) — **Virtual Calculator Feature Request** (Low / Feature-Request)
- [HB-003.md](file:///Users/aurtx/teamwork_projects/ezexam_reconstruction/audit_browser/HB-003.md) — **`ONE_WORD` Question Type Unanswerable in CBT** (Critical / Bug)
- [HB-004.md](file:///Users/aurtx/teamwork_projects/ezexam_reconstruction/audit_browser/HB-004.md) — **LaTeX Commands Render with Literal Backslashes** (Medium / UI-Issue)
- [HB-005.md](file:///Users/aurtx/teamwork_projects/ezexam_reconstruction/audit_browser/HB-005.md) — **Raw Modal IDs & Card Overflow on Staff UI** (Low / UI-Issue)
