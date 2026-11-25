# Gemini analysis and fix handoff

Start with [the audit report](06_final_report.md) and [new findings](05_new_findings.md). This folder contains report files only.

1. Investigate concurrent attempt writes and verify whether errors reproduce under the supported PostgreSQL stack. Review transaction boundaries and retry behavior before changing code.
2. Confirm the intended question-upload contract for images and Excel keys, then address the missing ingestion paths.
3. Clarify the delivery field contract for the MCQ display label `key` before renaming a field used by the frontend. Preserve the tested exclusion of grading secrets.
4. Run rendered-browser regression checks after each fix. Preserve cohort isolation, early report denial, saved-answer recovery, and auto-submit locking.

The audit used headless Zen against Django and Vite with SQLite. Results publication and score checks finished for all ten candidates. The working tree already contains unrelated changes. Preserve them during remediation.
