# Check results

Phases 0 through 2 passed. All ten attempts finalized and all ten published scores were confirmed.

| Check | Evidence required | Status |
| --- | --- | --- |
| CHECK-01 | Student question-paper detail response denies access or omits correctness and answer keys | PASS before opening. All ten candidate requests returned HTTP 403. |
| CHECK-02 | Candidate report request before publication denies access | PASS. All ten candidates received HTTP 403 RESULTS_NOT_PUBLISHED. |
| CHECK-03 | Candidate from 11 PCM cannot start the 11 PCB exam | PASS. S-01 received HTTP 404 EXAM_NOT_FOUND. |
| CHECK-04 | Candidate from 12 PCM cannot start the 11 PCM exam | PASS. S-07 received HTTP 404 EXAM_NOT_FOUND. |
| CHECK-05 | Candidate's three saved responses are present after reconnect and included in grading | PASS. S-03 resumed with all three saved responses, submitted, and the published review included all three as graded. |
| CHECK-06 | Threshold-crossing attempt auto-submits and subsequent edits are refused | PASS. S-06 and S-08 auto-submitted at count 6. Both subsequent saves returned HTTP 403 ATTEMPT_LOCKED. |
| CHECK-07 | Staff can publish after deadlines without a lingering in-progress attempt | PASS. The administrator verified 10 of 10 attempts finalized after close and published all ten results. |
| CHECK-08 | All student delivery responses omit numerical bounds, correctness flags, and keys | FAIL on the literal field rule. All ten initial deliveries included the MCQ option display label `key`. No numerical bounds, correctness flags, or question-level answer keys were observed in those deliveries. |
