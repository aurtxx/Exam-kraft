# Known regressions

| Prior finding | Runtime outcome |
| --- | --- |
| CX-002 | Safeguard held during pre-opening checks. Each of ten candidate question-paper detail requests returned HTTP 403. |
| CX-003 | Post-submission lock held for both auto-submitted attempts. Both answer writes returned HTTP 403 ATTEMPT_LOCKED. |
| CX-007 | Publication gate held for all ten finalized attempts. Each report request before publication returned HTTP 403 RESULTS_NOT_PUBLISHED. |
| CX-013 | Grading bounds were absent in all ten initial delivery payloads. The MCQ option display label `key` remained present. This fails the literal CHECK-08 requirement without exposing numerical grading bounds. |

This table covers the findings directly exercised by the current evidence. Remaining publication and score checks are tracked in the phase log and check results.
