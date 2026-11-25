# Exam-kraft run status

## Preflight

- Colima started. The host's legacy Compose client failed with an incompatible Docker SDK. Colima's bundled Compose client reached Docker Hub, where image transfers initially timed out.
- A sequential retry downloaded `nginx:alpine` and was pulling `redis:7-alpine` at the last poll.
- The latest health probe at `http://localhost/api/v1/health/` returned curl exit 7 and HTTP status `000`.
- Both mandatory Obscura commands, `obscura check --headless --js` and `obscura check --intercept`, returned exit 127 because the executable was unavailable. The workspace search found no project-local binary. The specified `obscura-browser` Cargo registry entry returned HTTP 404.

## Phases 0–5

Pending. No agents were spawned, no checks ran, and no deployment verdict was established.

## Resumed preflight

- Nginx and Redis images are present in the local Docker image store. The PostgreSQL pull is still active.
- The backend and frontend builds timed out resolving `python:3.12-slim` and `node:20-alpine` on Docker Hub. Direct pulls also timed out. Pulls for the same tags through Google's mirror are active.
- The supplied upstream Obscura macOS archive began downloading. After the first transfer timed out, the resumed transfer reached 12 MiB of 66.5 MiB. Extraction and both capability checks are pending.

## Obscura release verification

The supplied archive downloaded and extracted successfully. The executable reports `obscura 0.2.7`. Both required capability checks returned `unrecognized subcommand 'check'`. The CLI help lists `serve`, `fetch`, `scrape`, and `mcp` and omits the required agent lifecycle and interception commands. Testing stopped at preflight.

## Headless Zen preflight

- The user authorized replacing Obscura with headless Zen. Zen 1.24.3b rendered a local test page at 1366 × 768 using an isolated profile. A separate headless instance evaluated JavaScript through WebDriver BiDi and accepted a network response subscription. No application traffic was tested.
- The application health endpoint still refused connections on port 80. The Node image pull failed with an unexpected EOF and was restarted. The Python and PostgreSQL pulls were still active at the last check.
- The application test phases remain pending at the health gate.

## Docker-free local smoke test

- The user authorized skipping Docker downloads. Django ran on loopback with a fresh isolated SQLite database under audit_swarm, and the existing Vite project proxied the API. The health endpoint returned HTTP 200 with status healthy.
- Headless Zen signed in as a seeded candidate through the React login form. The login API returned HTTP 200 and the browser reached the student dashboard displaying exam content.
- This smoke test does not establish the outcomes of the full role-based stress run or the Docker deployment.

## Phase 0 started

- Started the administrator role in its own headless Zen session workflow against the healthy local stack. The setup is pending confirmation in the application.
- Created the PNG and Excel fixtures under audit_swarm/fixtures. The Excel fixture uses standard Office Open XML because the openpyxl download was still retrying. Its package passed ZIP integrity validation.

- Rebuilt the answer-key fixture with openpyxl 3.1.5 once the dependency finished installing. Reopened it and verified the headers and all three data rows against the objective.

- The administrator signed into Django admin in headless Zen. The organization form returned HTTP 500 on Python 3.14. The server traceback identified a Django 5.1 template context copy failure.
- Restarted the local backend on the repository's documented Python 3.12 runtime using cached dependencies and the same disposable database. The health endpoint returned HTTP 200. The administrator is retrying the form.

## Phase 0 passed

The administrator created and verified one school, four batches, ten students, three teachers, four empty question papers, and four draft exams assigned to their corresponding batches in headless Zen. The administrator session remains available. No exams were published.

## Phase 1 started

The Physics, Chemistry, and Biology teacher roles were launched concurrently. The phase gate requires 10 questions on each PCM paper and 15 on each PCB paper.

## Phase 1 passed

All 50 questions were created through JSON, including the fallbacks for image and Excel uploads. The administrator independently verified 10 questions in QP-11-PCM, 15 in QP-11-PCB, 10 in QP-12-PCM, and 15 in QP-12-PCB. All count requests returned HTTP 200. The earlier administrator browser process ended between agent turns, so the administrator resumed the count check with the preserved profile and token.

- The administrator prepared and syntax-checked the publication script. It will set a common opening five minutes after scheduling and closing sixty-five minutes after scheduling. Publication is pending the student controller.

- The administrator prepared the results workflow. It will record the exam closing time, final attempt statuses, violation counts, and publication responses. The workflow checks readiness before publishing. Syntax checks passed for the publication and results scripts.

## Phase 2 passed and Phase 3 started

The administrator published all four exams after confirming each had a five-switch cap. The shared opening is 2026-11-25 08:02:16 UTC and the shared close is 09:02:16 UTC. Each attempt is scheduled for 55 minutes. The candidate controller was launched with ten isolated Zen profiles. The run uses the normal admin session and candidate token refresh through the results phase.

## Phase 3 observed results

All ten started at the shared opening and finalized. Six ordinary candidates submitted, S-02 submitted after three switches, S-03 recovered three saved answers and submitted, and S-06 and S-08 auto-submitted at six switches. Both auto-submitted attempts rejected further saves. All ten pre-publication report requests returned HTTP 403. Concurrent writes triggered intermittent SQLite lock errors and the controller retried. Score verification awaits the scheduled examination close.

## Phase 4 waiting for exam close

The administrator rechecked the attempt lists and counted all ten attempts finalized across the four cohorts. The candidate controller remains live in tool session 10903. The administrator's detached scheduler exited before scheduling could be verified. The same guarded script was launched as a tracked process, PID 10578 in tool session 95458, to recheck the readiness gates and publish after 09:02:16 UTC.

## Phase 4 passed and testing stopped at user direction

All four cohorts passed the post-close readiness check and published successfully at 09:02:21 UTC. All ten candidate score checks passed. S-03's report included all three recovered answers. Both controllers exited successfully, and no Zen process remained for the audit profiles. The user stopped further testing and requested a handoff for Gemini.
