#!/bin/bash
set -e
cd /Users/aurtx/teamwork_projects/ezexam_reconstruction

echo "[$(date)] Starting 1-Hour Autonomous Codex Verification & Test Suite..."

# 1. Run all backend tests
echo "[$(date)] Running backend test suite..."
source backend/.venv/bin/activate
cd backend
python3 manage.py test --verbosity=2
cd ..

# 2. Run E2E requirement test suite
echo "[$(date)] Running 104-case E2E test runner..."
bash run_e2e_tests.sh --tier all

# 3. Compile frontend production build
echo "[$(date)] Checking frontend build integrity..."
cd frontend
npm run build 2>&1 || true
cd ..

# 4. Trigger Codex CLI to audit, fix any discovered edge-case bugs, and document progress
echo "[$(date)] Launching Codex CLI autonomous review and test verification..."
codex exec -c model_reasoning_effort="low" -C /Users/aurtx/teamwork_projects/ezexam_reconstruction \
  "You are the autonomous lead engineer for Exam-Kraft. Run all test suites (python3 manage.py test in backend, bash run_e2e_tests.sh). If any test fails or any route has missing serializers/views, fix it directly. Ensure frontend/dist compiles cleanly. Update management/PROGRESS.md with verified results. Work autonomously for the next hour without requiring assistance."

echo "[$(date)] Autonomous Codex cycle finished."
