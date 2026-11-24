# User Workflows Specification: EZExam Platform

**Investigation Target**: EZExam Examination Platform  
**Document**: Core User Workflows & Operational Lifecycles  
**Author**: Browser Exploration Specialist (Agent 1)  
**Status**: Complete Architectural Specification

---

## 1. Master Data Lifecycle Workflow

This workflow establishes the organizational hierarchy, user personas, physical/virtual testing venues, and candidate groupings required before examinations can be authored or delivered.

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  Organization   │ ────> │  Batches /      │ ────> │  Examination    │
│  Setup & Brand  │       │  Cohorts        │       │  Centers        │
└─────────────────┘       └─────────────────┘       └─────────────────┘
                                   │                         │
                                   ▼                         ▼
                          ┌─────────────────┐       ┌─────────────────┐
                          │  Student        │ <──── │  Center         │
                          │  Enrollment     │       │  Allocation     │
                          └─────────────────┘       └─────────────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │  Faculty &      │
                          │  Examiners      │
                          └─────────────────┘
```

### 1.1 Step-by-Step Execution

#### Step 1: Organization Creation & White-Label Configuration
- **Actor**: System SuperAdmin / Organization Administrator.
- **Route**: `/settings/`, `/profile/`
- **Actions**:
  1. Define Organization metadata: Name, Organization Code, Contact Details, Primary Domain/Subdomain (`<slug>.ezexam.in`).
  2. Upload institutional branding: Favicon (`favicon.png`), Navigation Logo (`logo.png`), Login Banner Background.
  3. Configure global policies: Session timeout limit, Default timezone (`Asia/Kolkata`), SMS/Email OTP notification gateway credentials.
- **Invariants**:
  - All subsequent database records (batches, students, exams) are bound to `organization_id` ensuring tenant isolation.

#### Step 2: Batch & Cohort Definition
- **Actor**: OrgAdmin.
- **Route**: `/batches/`, `/batch/create/`
- **Actions**:
  1. Define academic cohort: e.g., "JEE Main 2027 Morning Batch", "NEET Repeater Batch A".
  2. Set start date, expected graduation date, stream/specialization (e.g., Engineering, Medical, Foundation).
  3. Assign faculty coordinators to specific batches.

#### Step 3: Examination Center Configuration
- **Actor**: OrgAdmin.
- **Route**: `/centers/`, `/center/create/`
- **Actions**:
  1. Define physical or virtual testing centers: Center Name, Center Code, City, Address.
  2. Set Maximum Seat Capacity (e.g. 150 workstations).
  3. Allocate local subnet IP range (for on-premise locked-down LAN exam environments).

#### Step 4: Candidate & Faculty Provisioning
- **Actor**: OrgAdmin / Data Operator.
- **Route**: `/students/`, `/faculty/`
- **Actions**:
  1. **Single Entry**: Add individual candidate via modal (Name, Roll Number, Mobile, Email, Assigned Batch).
  2. **Bulk Ingestion via CSV/Excel**:
     - Columns: `roll_number`, `first_name`, `last_name`, `email`, `phone_number`, `batch_code`, `center_code`.
     - System executes pre-validation: rejects duplicate roll numbers or malformed phone numbers.
     - Auto-generates initial credentials or enables Phone OTP self-activation.
  3. **Faculty Account Creation**:
     - Assign Roles: `OrgAdmin`, `FacultyAuthor` (can create questions/exams), `Examiner` (evaluates and monitors).

---

## 2. Examination Authoring & Publishing Workflow

This workflow covers the end-to-end authoring lifecycle from question bank creation through question curation, section division, marking scheme configuration, scheduling, candidate assignment, and final publication.

```
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  Question Bank   │ ───> │  Exam Blueprint  │ ───> │  Section         │
│  & Taxonomy      │      │  & Metadata      │      │  Configuration   │
└──────────────────┘      └──────────────────┘      └──────────────────┘
                                                              │
                                                              ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  Exam Publish    │ <─── │  Candidate       │ <─── │  Marking Scheme  │
│  (Locked State)  │      │  Assignment      │      │  & Scheduling    │
└──────────────────┘      └──────────────────┘      └──────────────────┘
```

### 2.1 Step-by-Step Execution

#### Step 1: Question Bank Management & Question Authoring
- **Actor**: Faculty / Content Author.
- **Route**: `/question-bank/`, `/questions/create/`
- **Actions**:
  1. Create Subject and Topic taxonomy: e.g., `Physics > Thermodynamics > Carnot Engine`.
  2. Create Questions selecting one of three core types:
     - **MCQ_SINGLE**:
       - Rich text prompt (supports inline LaTeX formulas e.g. `$PV = nRT$`, embedded diagrams/images).
       - 3 to 6 answer options.
       - Radio selector designating exactly one option as `is_correct = True`.
     - **MCQ_MULTI**:
       - Multiple checkboxes where 1 or more options can be correct.
       - Partial credit eligibility flag.
     - **NUMERICAL**:
       - Numerical value prompt with expected answer (e.g., `24.5`).
       - Numerical precision tolerance: absolute delta ($\pm 0.1$) or integer match.
  3. Provide comprehensive solution / explanation text for post-exam review.

#### Step 2: Examination Blueprint Creation
- **Actor**: Faculty / OrgAdmin.
- **Route**: `/exam/create/`
- **Actions**:
  1. Define Exam Title, Unique Exam Code (e.g. `MOCK-JEE-2027-01`).
  2. Select Mode: `Online CBT` or `OMR Offline`.
  3. Define Total Duration in minutes (e.g., `180` minutes).
  4. Specify Instructions text (supports rich formatting, bullet points, advisory notes).

#### Step 3: Section Definition & Question Allocation
- **Actor**: Exam Coordinator.
- **Route**: `/exam/<id>/sections/`
- **Actions**:
  1. Partition exam into logical sections:
     - Section 1: Physics (e.g., 20 MCQs + 5 Numerical).
     - Section 2: Chemistry (e.g., 20 MCQs + 5 Numerical).
     - Section 3: Mathematics (e.g., 20 MCQs + 5 Numerical).
  2. Select questions from Question Bank or author inline.
  3. Reorder questions using drag-and-drop or index assignment.
  4. Configure section-level rules: e.g., "Candidate must answer any 5 out of 10 questions in Section B".

#### Step 4: Marking Scheme Configuration
- **Actor**: Exam Coordinator.
- **Route**: `/exam/<id>/marking/`
- **Actions**:
  1. Configure standard scoring parameters:
     - Correct Response: `+4.00`
     - Incorrect Response (Negative Marking): `-1.00`
     - Unattempted Question: `0.00`
  2. Configure Multi-Correct Partial Marking (if enabled):
     - If all 4 options correct: +4
     - If 3 options correct and selected: +3
     - If 2 options correct and selected: +2
     - If any incorrect option selected: `-2` or `-1`
  3. Numerical questions: `+4` for correct value, `0` for incorrect (no negative marking for numerical per NTA standards).

#### Step 5: Scheduling & Candidate Assignment
- **Actor**: Exam Coordinator.
- **Route**: `/exam/<id>/schedule/`, `/exam/<id>/assign/`
- **Actions**:
  1. Define Examination Window:
     - `start_window`: Timestamp when test becomes accessible (e.g. `2026-12-01 09:00:00 IST`).
     - `end_window`: Timestamp after which no new attempts may be started (e.g. `2026-12-01 12:00:00 IST`).
     - `late_login_buffer_minutes`: Grace window allowing delayed login (e.g., 15 minutes).
  2. Candidate Allocation:
     - Assign by Batch: Select one or more batches (e.g. "Batch-A", "Batch-B").
     - Assign by Center: Map candidates to specific test centers or workstation seats.

#### Step 6: Pre-Flight Audit & Publication
- **Actor**: OrgAdmin.
- **Route**: `/exam/<id>/publish/`
- **Actions**:
  1. System executes validation checklist:
     - Are all questions mapped with verified answer keys?
     - Does the sum of question marks equal total configured marks?
     - Is the candidate assignment non-empty?
     - Are start and end timestamps valid?
  2. Confirm publication.
  3. State Transition: `DRAFT` $\rightarrow$ `PUBLISHED`.
  4. Invariant: Exam configuration becomes immutable once published; question content and marking schemes are locked to preserve integrity.

---

## 3. Examination Delivery Workflow (Student Experience)

This workflow is the high-stakes candidate examination lifecycle, matching the **NTA CBT** interface standards with high fault tolerance for unreliable network connections.

```
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  Candidate Login │ ───> │  Exam Lobby &    │ ───> │  Instructions &  │
│  & Auth          │      │  Schedule Check  │      │  Declaration     │
└──────────────────┘      └──────────────────┘      └──────────────────┘
                                                              │
                                                              ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  Question        │ <─── │  Section         │ <─── │  CBT Launch &    │
│  Answering       │      │  Navigation      │      │  Timer Sync      │
└──────────────────┘      └──────────────────┘      └──────────────────┘
         │
         ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  Autosave &      │ ───> │  Pre-Submit      │ ───> │  Final Atomic    │
│  Palette Update  │      │  Summary Modal   │      │  Submission      │
└──────────────────┘      └──────────────────┘      └──────────────────┘
```

### 3.1 Step-by-Step Execution

#### Step 1: Candidate Access & Authentication
- **Actor**: Registered Student.
- **Route**: `/login` $\rightarrow$ `/online-exams`
- **Actions**:
  1. Candidate logs in using Username/Password or Mobile OTP.
  2. Exam Lobby displays allocated tests.
  3. Action button displays:
     - "Upcoming" (disabled before `start_window`).
     - "Start Exam" (active when `current_time` is within `[start_window, end_window]`).
     - "Expired" (if window has passed).

#### Step 2: System Pre-Check & Instructions
- **Actor**: Student.
- **Route**: `/online-exams/<id>/instructions/`
- **Actions**:
  1. Verify candidate details: Name, Roll Number, Photo, Assigned Test.
  2. Review Examination Instructions:
     - Duration, total questions, section breakdown.
     - Explanation of the **5 NTA Question Palette Symbols**:
       - **Not Visited** (Gray square): Question not visited yet.
       - **Not Answered** (Red/Orange square): Visited but no option selected.
       - **Answered** (Green square): Question answered.
       - **Marked for Review** (Purple circle): Question flagged for review without answer.
       - **Answered & Marked for Review** (Purple circle with Green dot): Question answered AND flagged for review; **will be evaluated**.
  3. Mandatory Checkbox: *"I have read and understood all instructions. I confirm that I am not carrying any unauthorized materials."*
  4. Click `[ Proceed to Test ]`.

#### Step 3: Exam Initiation & Server-Authoritative Timer
- **Actor**: Student Browser $\leftrightarrow$ Backend Engine.
- **Route**: `/online-exams/<id>/test/`
- **Protocol**:
  1. Browser dispatches `POST /api/v1/examinations/<id>/start/`.
  2. Backend checks attempt status:
     - If attempt does NOT exist: creates `ExaminationAttempt` with `started_at = now()`, computes `server_deadline = started_at + duration_minutes`.
     - If attempt already exists: returns existing attempt state (resuming interrupted attempt).
  3. Response payload includes:
     - Attempt token.
     - Exact remaining seconds (`server_deadline - now()`).
     - Complete section and question tree (without answer keys).
     - Previously persisted response map (for state recovery).
  4. Browser timer initiates countdown based on server-computed remaining seconds.
  5. WebSocket heartbeat connects (`/ws/exam/<attempt_id>/`) for drift correction.

#### Step 4: Section & Question Navigation
- **Actor**: Student.
- **Actions**:
  1. **Section Selection**: Tabs at top allow jumping between Physics, Chemistry, Mathematics.
  2. **Palette Navigation**: Clicking any number in the right-hand palette instantly displays that question.
  3. Status changes dynamically:
     - Navigating to a "Not Visited" question immediately updates its palette status to "Not Answered" (Red).

#### Step 5: Question Response & Autosave Persistence
- **Actor**: Student.
- **Actions**:
  1. **Single/Multi-Choice**: Candidate selects option radio/checkbox.
  2. **Numerical Input**: Candidate types value into numeric field or clicks on-screen keypad.
  3. **Action Triggers**:
     - `[ Save & Next ]`: Marks question as "Answered" (Green). Asynchronously saves response to server and advances to next question.
     - `[ Mark for Review & Next ]`:
       - If an option was selected: Marks as "Answered & Marked for Review" (Purple with Green indicator).
       - If no option was selected: Marks as "Marked for Review" (Purple).
       - Saves response state and advances.
     - `[ Clear Response ]`: Deselects active choice, transitions status back to "Not Answered" (Red), and syncs removal to server.
     - `[ Previous ]`: Saves draft locally and moves to previous question.
  4. **Fault-Tolerant Autosave Mechanism**:
     - Responses are immediately persisted to `localStorage` (offline guarantee).
     - Simultaneously, an asynchronous `POST` is dispatched to the backend save endpoint.
     - If network drops, responses queue in browser storage and retry automatically upon network restoration.
     - If page is refreshed, the interface seamlessly restores all selected answers and remaining time.

#### Step 6: Pre-Submission Summary & Confirmation
- **Actor**: Student.
- **Route**: `/online-exams/<id>/summary/` (Modal)
- **Actions**:
  1. Candidate clicks `[ Submit Exam ]`.
  2. System displays a modal with a detailed status matrix:
     - Columns: Section Name | Total | Answered | Not Answered | Marked for Review | Answered & Review | Not Visited
     - Alerts student if unvisited or unanswered questions remain.
  3. Options: `[ Return to Exam ]` or `[ Confirm Final Submit ]`.

#### Step 7: Final Submission & Idempotent Atomic Lock
- **Actor**: Student or Server-Authoritative Timer Expiry.
- **Protocol**:
  1. If candidate clicks `[ Confirm Final Submit ]` OR server timer reaches `server_deadline`:
  2. Backend dispatches `POST /api/v1/attempts/<id>/submit/`.
  3. System executes atomic transaction:
     - Sets attempt `status = SUBMITTED` (or `AUTO_SUBMITTED`).
     - Records `submitted_at = now()`.
     - Locks attempt: any subsequent save requests return HTTP 403 / 409 (`Attempt Closed`).
  4. Redirects candidate to `/online-exams/<id>/finish/` displaying submission confirmation, date-time receipt, and exit instructions.

---

## 4. Post-Examination Evaluation & Analytics Workflow

This workflow processes candidate submissions, calculates scores and rankings, and generates deep performance analytics.

```
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  Conclude Exam   │ ───> │  Answer Key      │ ───> │  Asynchronous    │
│  & Lock Attempts │      │  Verification    │      │  Evaluation Job  │
└──────────────────┘      └──────────────────┘      └──────────────────┘
                                                              │
                                                              ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  Publish Results │ <─── │  Analytics &     │ <─── │  Merit Rank &    │
│  to Students     │      │  Reports Engine  │      │  Percentile Calc │
└──────────────────┘      └──────────────────┘      └──────────────────┘
```

### 4.1 Step-by-Step Execution

#### Step 1: Exam Closure & Answer Key Audit
- **Actor**: Exam Coordinator / Faculty.
- **Route**: `/evaluation/`, `/evaluation/<id>/answer-key/`
- **Actions**:
  1. Once `end_window` passes, exam transitions to `CLOSED`. Any active attempts are automatically finalized.
  2. Faculty reviews the Master Answer Key.
  3. Answer Key Challenge / Override (if needed):
     - If a question is found ambiguous, faculty can mark it as "Dropped / Full Marks to All" or add a secondary valid option.

#### Step 2: Automated Scoring Pipeline Execution
- **Actor**: Background Worker (Celery + Redis) triggered by `/evaluation/<id>/evaluate/`.
- **Computation Rules**:
  1. For each attempt, iterates through all questions in each section:
     - **MCQ_SINGLE**:
       - Correct option matched $\rightarrow$ adds `positive_marks` (+4).
       - Incorrect option selected $\rightarrow$ subtracts `negative_marks` (-1).
       - No option selected $\rightarrow$ 0 marks.
     - **MCQ_MULTI**:
       - Exact match of all correct options $\rightarrow$ full positive marks (+4).
       - Partial correct options marked with no wrong options $\rightarrow$ partial credit.
       - Any incorrect option marked $\rightarrow$ negative penalty (-1 or -2).
     - **NUMERICAL**:
       - Value within $[ \text{correct} - \epsilon, \text{correct} + \epsilon ]$ $\rightarrow$ +4 marks.
       - Incorrect value $\rightarrow$ 0 marks (no negative penalty).
  2. Aggregates Section Scores:
     $$\text{Section Score} = \sum \text{Correct Marks} - \sum \text{Negative Marks}$$
  3. Computes Total Raw Score:
     $$\text{Total Score} = \sum_{\text{sections}} \text{Section Score}$$

#### Step 3: Merit Rank & Percentile Generation
- **Actor**: Evaluation Worker.
- **Actions**:
  1. Sorts all candidates in the exam attempt cohort in descending order of Total Score.
  2. Applies **Deterministic Tie-Breaking Rules**:
     - Rule 1: Higher score in Mathematics (or designated primary subject).
     - Rule 2: Higher score in Physics (secondary subject).
     - Rule 3: Ratio of correct to incorrect responses (fewer negative marks gets higher rank).
     - Rule 4: Candidate seniority by birthdate.
  3. Computes Percentile for each candidate:
     $$P = \frac{\text{Number of candidates with score } \le S}{N} \times 100$$
     where $N$ is total candidates who attempted the exam.

#### Step 4: Analytics Generation & Reports
- **Actor**: Reporting Engine.
- **Route**: `/reports/`, `/analytics/`
- **Outputs**:
  1. **Batch Level Analytics (Staff View)**:
     - Score Distribution Histogram (Gaussian distribution / Bell curve).
     - Subject-wise comparative performance (Average, Median, Highest, Lowest).
     - Question Difficulty Discrimination Index (identifies questions where majority failed).
     - Time Spent Analysis (identifies questions where students spent excessive time).
  2. **Student Performance Scorecard (Candidate View)**:
     - Individual Rank, Percentile, Total Score, Maximum Possible Marks.
     - Sectional Breakdown: Attempted, Correct, Incorrect, Accuracy %.
     - Question-by-Question Solution Review: shows candidate's chosen response vs correct answer and detailed explanation.
     - Time taken per question compared to batch average.

#### Step 5: Publication of Results
- **Actor**: OrgAdmin.
- **Route**: `/results/`
- **Actions**:
  1. Toggle "Publish Results to Students".
  2. When enabled, student dashboard `/online-exams/` shows "View Result / Scorecard" button.
  3. Automated SMS / Email alerts dispatched notifying students that results are accessible.

---

## 5. State Machine Invariants & Security Boundaries

```
Exam State Machine:
  [ DRAFT ] ───────────> [ PUBLISHED ] ───────────> [ CLOSED ] ───────────> [ EVALUATED ]
    (editable)             (locked schedule)          (no attempts)            (ranks ready)

Candidate Attempt State Machine:
  [ ASSIGNED ] ────────> [ IN_PROGRESS ] ─────────> [ SUBMITTED ] ────────> [ GRADED ]
                               │                            ▲
                               └────── (Timer Expiry) ──────┘
```

1. **Immutability of Published Content**:
   - Once an exam enters `PUBLISHED`, questions, options, and marking schemes cannot be edited to prevent race conditions during active candidate attempts.
2. **Server-Authoritative Enforcement**:
   - The server maintains the true start and deadline timestamps. Client clocks are untrusted. Any response received after `server_deadline + 15s (grace period)` is rejected.
3. **Idempotent Submission**:
   - Final submission is atomic and idempotent. Repeated submission requests return HTTP 200 with the already recorded submission record without re-triggering evaluation duplicate jobs.
4. **Offline Resilience**:
   - If network drops during testing, student can continue answering cached questions. Answers persist locally in `localStorage` and synchronize asynchronously when connection recovers.
