# Physics upload findings

- Direct JSON authoring passed. The Physics faculty account created and verified five Physics items in each of QP-11-PCM, QP-11-PCB, QP-12-PCM, and QP-12-PCB.
- TEACHER-FINDING-001. PDF/image question upload has no server-side parsing; text must be entered manually. Eight real multipart PNG requests returned HTTP 400 with `INVALID_QUESTION_TYPE` and `question_type is required.` Inspection of the authoring route found no uploaded-image field handling. Both image-method items per paper were entered as JSON.
- TEACHER-FINDING-002. Excel answer key import not implemented. The question-bank and question API URL declarations expose no Excel import route. No POST was sent to a guessed route. The Excel-method item in each paper was entered as JSON.
- The authorization assertion is assigned to an independent student role using its own session.
