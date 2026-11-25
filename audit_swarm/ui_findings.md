# UI findings

## FINDING: NUMERICAL-FIELD-LOCATION

The delivery serializer declares a question type and an options list. It does not declare a response input value or numerical grading bounds. All ten browser start payloads lacked a numerical response input field in the question data. The separate response request accepts the candidate entry as `numerical_value`. MCQ options carry a display label under `key`.

Place a full-width numerical input directly below the last option row, outside the MCQ option list. Label it “Enter your answer” and give it a minimum height of 48 px.

## FINDING: VIRTUAL-CALCULATOR

Provide an opt-in floating panel toggled by a calculator icon in the CBT toolbar. Make it available by default on numerical questions. Allow dragging and Escape dismissal, and position it clear of the question stem. This is a frontend feature request.
