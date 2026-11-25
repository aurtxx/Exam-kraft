# Exam-kraft headless Zen audit

**Deployment verdict — UNSAFE for school use on the tested SQLite configuration. Production readiness remains unverified.**

Concurrent SQLite writes returned 87 HTTP 500 responses across starts, saves, and proctoring events. Retries allowed all ten attempts to finalize. Docker and PostgreSQL were skipped at user direction. The PNG and Excel ingestion requirements were fulfilled through manual JSON fallback. The run recorded 606 action-log entries, including retries and assertions.

| Phase | Outcome |
| --- | --- |
| 0. Setup | PASS. One school, four batches, ten students, three teachers, four papers and four draft exams. |
| 1. Upload | PASS for counts and JSON authoring. All 50 questions verified. PNG and Excel paths unsupported. |
| 2. Publish exams | PASS. All four exams shared the planned opening and close. |
| 3. Attempts | PARTIAL. All ten started and finalized. SQLite contention caused transient failures. Browser-context API checks covered the functional flow. The full rendered CBT flow was outside that evidence. |
| 4. Publish results | PASS. Published all ten results after close. All ten candidate report responses contained scores. |
| 5. Checks | PARTIAL. Seven checks passed. CHECK-08 failed the literal field rule. Further testing stopped at user direction. |

| Check | Verdict |
| --- | --- |
| CHECK-01 | PASS. Ten student paper-detail requests returned 403. |
| CHECK-02 | PASS. Ten early report requests returned 403. |
| CHECK-03 | PASS. Wrong stream start returned 404. |
| CHECK-04 | PASS. Wrong class start returned 404. |
| CHECK-05 | PASS. RECOVERED. Three pre-disconnect responses survived and appeared in the graded review. |
| CHECK-06 | PASS. S-06 and S-08 auto-submitted at six switches and subsequent saves returned 403. |
| CHECK-07 | PASS. All ten attempts were finalized after close and all four publication requests returned 200. |
| CHECK-08 | FAIL. Delivery included the MCQ display label `key`. Observed payloads omitted numerical bounds, correctness flags, and question-level answer keys. |

S-02 submitted normally after three switches, below the cap. S-06 and S-08 auto-submitted after six each. Staff counts agreed with the candidate event evidence.

Teacher upload verdict is API PASS, PDF/image UNSUPPORTED, Excel UNSUPPORTED. See [teacher upload findings](teacher_upload_findings.md). The numerical input location and floating calculator requests are in [UI findings](ui_findings.md). CX-002, CX-003, CX-007, and the numerical bounds portion of CX-013 held in the observed flows. [Known regressions](04_regression_list.md)

Two new findings were recorded, one high and one low. [New findings](05_new_findings.md)

The candidate harness used application API calls inside ten isolated Zen browser sessions. Its simulated disconnect was a 90-second pause in outbound test traffic. Submission locks were verified through API responses. The original administrator browser process exited between steps and the saved profile was reused. The user stopped further testing after score verification. Profiles and credentials remain local and should be excluded from any external handoff.
