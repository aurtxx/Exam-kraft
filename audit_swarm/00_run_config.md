# Exam-kraft headless Zen run configuration

The authorized local stack uses Django, Vite, and a disposable SQLite database. The browser base URL is http://127.0.0.1:5173. Use an isolated headless Zen profile and WebDriver BiDi session per role. The local run cannot validate PostgreSQL concurrency or the Docker deployment.

## Roster

| Role | Assignment |
| --- | --- |
| AGENT-ADMIN | Setup, publication, and results for all cohorts |
| AGENT-TEACHER-PHY | Physics across all four papers |
| AGENT-TEACHER-CHEM | Chemistry across all four papers |
| AGENT-TEACHER-BIO | Biology for the two PCB papers |
| AGENT-S-01, AGENT-S-02, AGENT-S-03 | BATCH-11-PCM, QP-11-PCM, EXAM-11-PCM |
| AGENT-S-04, AGENT-S-05, AGENT-S-06 | BATCH-11-PCB, QP-11-PCB, EXAM-11-PCB |
| AGENT-S-07, AGENT-S-08 | BATCH-12-PCM, QP-12-PCM, EXAM-12-PCM |
| AGENT-S-09, AGENT-S-10 | BATCH-12-PCB, QP-12-PCB, EXAM-12-PCB |

S-02, S-06, and S-08 have 3, 6, and 10 tab switches planned at 30-second intervals, subject to auto-submission. S-03 disconnects at minute 3 and resumes at minute 4.5. The other six students answer normally with 20-second heartbeats.

## Phase timing

1. Create the organization, users, batches, empty papers, and draft exams.
2. Upload five questions per teacher per assigned paper and verify a total of ten per PCM paper and fifteen per PCB paper.
3. Publish with a shared opening five minutes after scheduling, a closing sixty-five minutes after scheduling, and a fifty-five-minute attempt duration.
4. Start all ten candidates at the shared opening and exercise their assigned behaviors.
5. Verify submitted confirmations and publish results after the applicable closing conditions.
6. Verify the eight specified checks using captured evidence, with the unpublished report check recorded before publication.

## Evidence at timing boundaries

Capture the report access check after an attempt is submitted and before the administrator publishes results. Capture delivery field presence as booleans and retain only the bounded excerpts specified by the objective. Capture the crash candidate's saved-answer count before disconnect, after reconnect, and in the published result. Record the final submission status and violation count for each tab-switch candidate. SQLite permits the functional flow, with database-specific deployment checks outside the evidence from this run.

The access JWT lifetime is sixty minutes, which is shorter than the shared exam window measured from scheduling. Keep the administrator's normal Django session available for results publication, and retain each candidate's own refresh credential privately for post-publication checks.
