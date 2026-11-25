# Teacher upload findings

## Physics

- Direct JSON authoring created and verified five Physics questions in each of the four papers, for 20 total.
- TEACHER-FINDING-001. Eight multipart PNG requests returned HTTP 400 with `INVALID_QUESTION_TYPE`. No server-side image question parsing path was identified. The teacher entered those questions through the JSON authoring route.
- TEACHER-FINDING-002. No Excel answer-key import endpoint was found in the question authoring routes. The teacher used the JSON fallback.

## Biology

- Direct JSON authoring created and verified five Biology questions in each PCB paper, for 10 total.
- Four multipart PNG requests returned HTTP 400 with `INVALID_QUESTION_TYPE`. No Excel answer-key import endpoint was found. The teacher completed the affected questions via JSON.

## Chemistry

- Direct JSON authoring created and verified five Chemistry questions per paper, for 20 total.
- Eight multipart PNG requests returned HTTP 400 with `INVALID_QUESTION_TYPE`. No Excel answer-key import endpoint was found. JSON fallback completed the affected questions.

## Totals

Teachers verified 50 authored questions collectively. All 20 PNG requests were rejected. The administrator independently verified 10 questions in each PCM paper and 15 in each PCB paper. All four reads returned HTTP 200.
