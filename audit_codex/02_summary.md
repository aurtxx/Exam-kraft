# Deployment verdict

Exam-Kraft is unsafe to deploy for real students in the reviewed state. Candidates can read grading keys, access exams without assignment, and receive results before release. An unattended timeout can block a cohort's publication, and the submission path does not reliably preserve the answer set. The default test command cannot validate the real database concurrency guarantees.

## Top 10 risks

1. CX-001 Unauthenticated WebSocket can modify attempt telemetry
2. CX-002 Student-readable authoring endpoints return answer keys
3. CX-003 Attempt launch omits exam status and assignment checks
4. CX-004 Concurrent starts can create multiple attempts per candidate
5. CX-005 Autosave and proctoring can write after the submission lock
6. CX-006 Disconnected attempts can indefinitely prevent result publication
7. CX-007 Attempt report bypasses result publication
8. CX-008 Cached offline responses can be discarded at final submission
9. CX-009 Deleting users or exams cascades into assessment records
10. CX-010 Default E2E runs validate the mock, while default pytest excludes backend suites

## Severity counts

| Severity | Count |
|---|---:|
| Critical | 2 |
| High | 9 |
| Medium | 11 |
| Low | 4 |
| Info | 2 |

## Category counts

| Category | Count |
|---|---:|
| A | 6 |
| B | 4 |
| C | 5 |
| D | 2 |
| E | 1 |
| F | 2 |
| G | 3 |
| H | 1 |
| I | 1 |
| J | 2 |
| K | 1 |

## Needs user permission to verify

These commands were left unexecuted. The live suite requires a disposable PostgreSQL-backed instance and matching fixtures.

| Goal | Exact command |
|---|---|
| Compare Django test discovery against the default pytest scope | `python -m pytest --collect-only -q` and `python backend/manage.py test --verbosity 2`. |
| Exercise implemented Django engine and analytics paths | `python backend/manage.py test apps.engine apps.analytics --verbosity 2` |
| Evaluate the contract suite against a disposable live backend | `BASE_URL=http://127.0.0.1:8080 bash ./run_e2e_tests.sh --all` |
| Render the effective deployment config without printing environment values | `docker compose config --quiet` |
| Inspect actual nginx configuration in the isolated stack | `docker compose exec -T nginx nginx -T` |
| Check frontend dependency advisories | `cd frontend && npm audit --omit=dev` |
