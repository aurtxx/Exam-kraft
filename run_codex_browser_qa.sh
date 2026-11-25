#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

PROMPT="You are the Lead QA & Full-Stack Integration Engineer for the Exam-Kraft (EZExam Reconstruction) project.
Working directory: $DIR.

YOUR MISSION:
Perform complete end-to-end frontend-to-backend integration testing and fix all broken linkages, navigation bugs, and data mismatches across the React frontend (running on http://localhost:5173) and Django backend (running on http://localhost:8000).

SPECIFIC CHECKS & FIXES NEEDED:
1. Student Login Redirection:
   - In frontend/src/pages/Login.tsx, when a user with role 'STUDENT' logs in, they should NOT be redirected to /staff/exams.
   - Redirect students to their active examination lobby (/student/exam/:id/lobby or /online-exams/:id) or an intuitive candidate portal page.
2. Staff vs Student Role Routing:
   - Ensure Shell.tsx and ProtectedRoutes forbid STUDENT roles from rendering staff navigation/pages (/staff/*).
3. Question Bank & Examinations Integration:
   - Check that creating questions, adding options, creating exams, and assigning question papers works smoothly through the UI and REST APIs.
   - Verify that student CBT engine (/student/exam/:id/test) renders questions, LaTeX formulas, timer, and submits answers properly without 403 or 500 errors.
4. Batch & Center Roster Flow:
   - Test bulk student CSV upload, batch assignment, and candidate roster view.
5. Record Everything:
   - Write all discovered issues, fixes applied, files modified, and verification results into:
     $DIR/audit_fix/codex_browser_integration_fixes.md
   - Ensure 'python backend/manage.py test' passes with 0 failures after all your fixes.

Execute these integration fixes directly and comprehensively now."

echo "Starting Codex Full-Stack Browser & Linkage Integration Session..."
codex exec -c model_reasoning_effort="low" "$PROMPT"
