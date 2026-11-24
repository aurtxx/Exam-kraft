# Reference Route Inventory: EZExam Examination Platform

**Investigation Target**: https://ezexamqwertyuiop.ezexam.in (with reference documentation from https://ezexam.in)  
**Investigation Date**: 2026-11-24  
**Investigator**: Browser Exploration Specialist (Agent 1)  
**Status**: Comprehensive Reverse-Engineered Route Map

---

## 1. Architectural Overview & URL Routing Paradigm

The reference application is an enterprise examination management and delivery platform built on **Django / Nginx**, delivering an authenticated staff back-office and a student-facing examination engine modeled after the **NTA (National Testing Agency) computer-based test (CBT)** paradigm.

### Key Observed Routing Characteristics:
1. **Django URL Dispatcher with Append-Slash**:
   - Routes without a trailing slash redirect with HTTP 301 (`/dashboard` → `/dashboard/`, `/exam` → `/exam/`).
   - Protected endpoints require an active session cookie (`sessionid`) and CSRF token (`csrftoken`), redirecting unauthenticated traffic via HTTP 302 to `/login?next=<path>`.
   - Invalid paths return a custom HTTP 404 error page titled `EZexam - Page not found!`.
2. **Multi-Tenant Scoping**:
   - Institutions are isolated by subdomain (e.g., `ezexamqwertyuiop.ezexam.in` or custom domain `institute.ezexam.in`).
   - Branding assets (logos, favicons, custom themes) are dynamically resolved based on the host header or organization record.
3. **Role-Based Views**:
   - **Staff / Admin Roles**: SuperAdmin, OrgAdmin, Faculty / Examiner.
   - **Student / Candidate Roles**: Registered exam takers assigned to specific batches and schedules.

---

## 2. Route Inventory Table

| ID | Page / View Name | Route URL | Allowed Roles | Method | Purpose | Key Actions & Forms |
|:---|:---|:---|:---|:---:|:---|:---|
| **AUTH-01** | Login Page | `/login` | Public / All | GET, POST | User authentication via username/password or mobile OTP | - Username & Password form<br>- Toggle Mobile OTP login<br>- Sign-up modal trigger |
| **AUTH-02** | Phone OTP Request | `/login/phone` | Public | POST | Dispatches 4-digit SMS OTP to registered phone number | - Mobile number input (10 digits)<br>- Role selector (`student` vs `staff`) |
| **AUTH-03** | Phone OTP Verify | `/login/otp` | Public | POST | Validates OTP and verifies new password setup | - 4 individual OTP input boxes<br>- Password & Confirm Password inputs |
| **AUTH-04** | Candidate Self-Signup | `/login/signup` | Public | POST | Direct registration for open examination links | - Name, 10-digit mobile, email inputs<br>- Trigger OTP verification |
| **AUTH-05** | Logout | `/logout` | Authenticated | GET, POST | Terminates session and redirects to `/login` | - Session purge & cookie invalidation |
| **STF-01** | Staff Root / Overview | `/staff`, `/dashboard/` | OrgAdmin, Faculty | GET | Central operational dashboard with key metrics | - Summary cards: Total Exams, Active Candidates, Pending Evaluations, Question Count |
| **STF-02** | Batches Master List | `/batches/`, `/batch/` | OrgAdmin, Faculty | GET, POST | Manage student cohorts, academic batches, streams | - "Create Batch" modal<br>- "Import Students" CSV button<br>- Batch status toggle |
| **STF-03** | Batch Detail & Members | `/batches/<id>/` | OrgAdmin, Faculty | GET, PUT, DEL | View and manage enrolled students within a batch | - Search filter bar<br>- "Add Candidate" modal<br>- "Export Roster" Excel |
| **STF-04** | Examination Centers | `/centers/`, `/center/` | OrgAdmin | GET, POST | Define physical or virtual test centers, capacity | - Center name, address, code, max capacity<br>- "Add Center" modal |
| **STF-05** | Student Roster | `/students`, `/student/` | OrgAdmin, Faculty | GET, POST | Comprehensive candidate directory across all batches | - Search by Roll No, Name, Mobile<br>- Bulk CSV upload<br>- Edit student modal |
| **STF-06** | Faculty Management | `/faculty/`, `/teachers/` | OrgAdmin | GET, POST | Manage teacher accounts, subject assignments, examiners | - Name, email, mobile, subject assignment<br>- Role toggle (Admin/Faculty) |
| **STF-07** | Organization Settings | `/settings`, `/profile/` | OrgAdmin | GET, POST | Institutional white-label branding, logos, notifications | - Org logo upload, banner upload<br>- Contact details, SMS gateway config |
| **STF-08** | Notices & Broadcasts | `/notices/`, `/notice/` | OrgAdmin, Faculty | GET, POST | Broadcast exam notices and advisories to students | - Notice title, rich text body, target batch<br>- Publish / Expiration date |
| **EXM-01** | Examination Dashboard | `/exams`, `/exam/` | OrgAdmin, Faculty | GET | List of all authored exams across draft and published states | - Status filters: Draft, Published, Ongoing, Closed<br>- "Create Exam" button<br>- Action menu |
| **EXM-02** | Examination Wizard | `/exam/create/` | OrgAdmin, Faculty | GET, POST | Multi-step authoring: Metadata, Sections, Marking Scheme | - Step 1: Basic Info & Duration<br>- Step 2: Section definition<br>- Step 3: Marking scheme configuration |
| **EXM-03** | Question Bank Manager | `/question-bank/`, `/questions/` | OrgAdmin, Faculty | GET, POST | Repository of questions categorized by subject & tag | - Subject filter, difficulty filter<br>- "Add Question" modal / page<br>- Question preview drawer |
| **EXM-04** | Question Editor Modal | `/questions/create/` | OrgAdmin, Faculty | GET, POST | Author individual questions with LaTeX/Math and options | - Type: MCQ Single, MCQ Multi, Numerical<br>- Rich text question body<br>- Options editor (3 to 6 options)<br>- Correct option selector |
| **EXM-05** | Exam Section Config | `/exam/<id>/sections/` | OrgAdmin, Faculty | GET, POST | Configure sections (e.g. Physics, Chemistry, Math) | - Section title, question selection from bank<br>- Question order re-indexing<br>- Section instructions |
| **EXM-06** | Marking Scheme Config | `/exam/<id>/marking/` | OrgAdmin, Faculty | GET, POST | Define positive, negative, and unattempted mark values | - Standard positive marks (e.g., +4)<br>- Negative marks (e.g., -1)<br>- Partial marking rules for multi-correct |
| **EXM-07** | Schedule & Assignment | `/schedule/`, `/exam/<id>/assign/` | OrgAdmin, Faculty | GET, POST | Define exam window, duration, batch & center allocation | - Start datetime & End datetime picker<br>- Candidate batch multi-select<br>- Center allocation |
| **EXM-08** | Exam Publication | `/exam/<id>/publish/` | OrgAdmin, Faculty | POST | Locks configuration and transitions exam to PUBLISHED | - Pre-flight checklist modal<br>- Confirmation prompt |
| **EXM-09** | Live Monitoring & Proctoring | `/monitoring/`, `/attendance/` | OrgAdmin, Faculty | GET | Real-time monitoring of in-progress exam attempts | - Live candidate grid<br>- Status: Not Started, In Progress, Submitted<br>- Window switch alerts, IP tracking |
| **STU-01** | Student Exam Portal | `/online-exams`, `/online-exams/` | Student | GET | Student lobby listing assigned active and upcoming tests | - "Start Exam" button (enabled during window)<br>- Test card: Title, Duration, Start Time, Status |
| **STU-02** | Exam Instructions | `/online-exams/<id>/instructions/` | Student | GET | Pre-test advisory, system check, declaration agreement | - General instructions, symbol legend (NTA)<br>- Checkbox: "I have read all instructions"<br>- "Proceed to Test" button |
| **STU-03** | CBT Test Screen | `/online-exams/<id>/test/` | Student | GET | Active exam delivery engine (NTA CBT layout) | - Top Bar: Exam Title, Candidate Info, Countdown Timer<br>- Section Navigation Tabs<br>- Question Pane (Rich content, options)<br>- Question Palette (5 statuses)<br>- Action Buttons |
| **STU-04** | Response Auto-Save | `/online-exams/<id>/save/` | Student | POST (AJAX) | Idempotent persistence of current question response | - Payload: `question_id`, `selected_options`, `numerical_val`, `status` |
| **STU-05** | Pre-Submit Summary | `/online-exams/<id>/summary/` | Student | GET / Modal | Confirmation modal displaying summary table before submission | - Counts: Total, Answered, Unanswered, Marked for Review, Not Visited<br>- "Yes, Submit" / "Return to Exam" |
| **STU-06** | Exam Completion Screen | `/online-exams/<id>/finish/` | Student | GET | Post-submission confirmation and acknowledgments | - Attempt timestamp, receipt number, return link |
| **EVL-01** | Evaluation Dashboard | `/evaluation/`, `/evaluate/` | OrgAdmin, Faculty | GET | Assessment overview for concluded examinations | - "Evaluate Exam" trigger button<br>- Scoring status, un-evaluated count |
| **EVL-02** | Answer Key Manager | `/evaluation/<id>/answer-key/` | OrgAdmin, Faculty | GET, POST | Review or override official answer keys post-exam | - Question-by-question key matrix<br>- Option correction or question drop flag |
| **EVL-03** | Results & Merit List | `/results/`, `/result/` | OrgAdmin, Faculty, Student | GET | Scores, rank calculation, and scorecards | - Batch merit rank table<br>- Individual scorecard view<br>- "Publish Results to Students" toggle |
| **EVL-04** | Analytics & Performance | `/reports/`, `/analytics/` | OrgAdmin, Faculty, Student | GET | Deep graphical performance analytics | - Percentile distribution curve<br>- Subject-wise accuracy & time-spent charts<br>- PDF scorecard generator |
| **ADM-01** | System Administration | `/admin/` | SuperAdmin | GET, POST | Low-level Django admin panel for system diagnostics | - Standard Django admin auth and model inspect |
| **API-01** | REST API Endpoint Root | `/api/` | Authenticated | ANY | RESTful endpoints powering frontend async operations | - JSON responses for attempts, sync, telemetry |

---

## 3. Deep-Dive Specification of Critical Views

### 3.1 AUTH-01 & AUTH-04: Multi-Mode Authentication (`/login`)
- **Page Title**: `Login - Ezexamqwertyuiop`
- **Visual Design**: High-contrast blue gradient background (`linear-gradient(to top right, #1eaeff, #1474d8)`), centered floating card, responsive on mobile and desktop.
- **Form Controls**:
  - Tab 1: Username & Password
    - `input[name="username"]`: Username, Email, or 10-digit Indian Mobile.
    - `input[name="password"]`: Password input with show/hide toggle eye icon.
    - `input[name="remember-me"]`: Boolean checkbox.
    - `button#btn-login`: Primary submit button with loading spinner state.
  - Tab 2: Mobile OTP Login
    - `input[name="phone"]`: 10-digit mobile number.
    - Radio group `usertype`: `student` (default) vs `staff`.
    - OTP Step: 4 individual digit boxes with auto-focus advance, countdown timer ("Resend in 15s").
  - Tab 3: Self-Registration (`#signup-form`)
    - `input[name="name"]`: Full candidate name (regex: `^[a-zA-Z\s]{5,30}$`).
    - `input[name="phone"]`: 10-digit mobile (`^[1-9][0-9]{9}$`).
    - `input[name="email"]`: Valid email address.
    - Captures `?next=` query parameter to route directly into candidate's target exam after verification.

---

### 3.2 STF-01: Operational Staff Dashboard (`/staff` & `/dashboard/`)
- **Layout Structure**:
  - **Left Collapsible Sidebar Navigation** (`#left-sidebar-nav`):
    - Institutional Logo & Name at top.
    - Navigation Items:
      1. Dashboard (`/dashboard/`)
      2. Examinations (`/exams`)
         - All Exams
         - Create New Exam
         - Online Exams Monitor
      3. Question Bank (`/question-bank/`)
         - Questions List
         - Import Questions
         - Subjects & Sections
      4. Batches & Candidates (`/batches/`)
         - Student Cohorts
         - Center Management
         - Faculty Roster
      5. Evaluation & Results (`/results/`)
         - Answer Keys
         - Merit Ranks
         - Analytics Reports
      6. System Settings (`/settings`)
  - **Top Navigation Bar**:
    - Sidebar toggle icon (hamburger/pin).
    - Quick global search input (`.header-search-input`).
    - Notification bell with unread badge counter.
    - User Profile Dropdown: Name, Role, Organization, "My Profile", "Logout".
  - **Main Content Area**:
    - **KPI Metrics Ribbon**:
      - Total Conducted Exams (Card with blue gradient)
      - Active Candidates Enrolled (Card with teal background)
      - Question Bank Volume (Card with purple accent)
      - Recent Completed Exams awaiting evaluation (Card with orange alert)
    - **Recent Exams Table**:
      - Columns: `Exam Code`, `Title`, `Batch`, `Duration`, `Scheduled Window`, `Status (Badge)`, `Actions`.
      - Status Badges:
        - `Draft`: Neutral gray badge
        - `Published`: Info blue badge
        - `Ongoing`: Pulse green badge (`ee-green`)
        - `Closed`: Warning amber badge
        - `Evaluated`: Success dark-green badge

---

### 3.3 EXM-02 to EXM-06: Examination Authoring & Question Management
- **Exam Configuration Workflow**:
  1. **Metadata Definition**:
     - Exam Title, Subject Code, Description.
     - Examination Mode: `ONLINE_CBT` (Computer-Based) or `OMR_OFFLINE`.
     - Total Duration (Minutes, e.g. 180 min).
     - Total Marks (Auto-computed from questions or fixed).
     - Passing Percentage / Minimum Qualifying Marks.
     - Strict Instructions markup (displayed before test launch).
  2. **Section Architecture**:
     - Ability to partition exam into sequential or free-navigation sections (e.g. Physics, Chemistry, Mathematics).
     - Per-section properties: Section Title, Instructions, Optional vs Mandatory questions.
  3. **Question Authoring & Types**:
     - **MCQ_SINGLE**: Standard multiple choice with 1 correct option (3, 4, 5, or 6 choices).
     - **MCQ_MULTI**: Multiple-correct choice questions with full or partial credit marking.
     - **NUMERICAL**: Numerical integer or decimal answer within an acceptable precision tolerance ($\pm \epsilon$).
     - Rich content: Supports mathematical formulas (LaTeX/MathJax), diagram images, and tabular formatting.
  4. **Marking Scheme Rules**:
     - Positive Marks per correct answer (e.g., `+4`).
     - Negative Marks penalty for incorrect answer (e.g., `-1`).
     - Zero marks for unattempted questions (`0`).
     - Partial Marking rules for Multi-Correct (e.g., +1 for each correct option marked provided no incorrect option is chosen).

---

### 3.4 STU-03: National Testing Agency (NTA) Style Student Examination Interface
- **Screen Geometry & Responsive Layout**:
  - **Top Fixed Header**:
    - Left: Institution Brand & Exam Name.
    - Center: Active Section title and Question numbering indicator (`Question No. 12 of 30`).
    - Right: Candidate Profile card (Candidate Name, Roll No, Avatar placeholder) and **High-Visibility Countdown Timer** (`HH:MM:SS` format, switches to flashing red warning when time < 10 minutes).
  - **Section Navigation Bar**:
    - Horizontal tabs indicating each subject/section (e.g. `[ Physics (30) ] [ Chemistry (30) ] [ Mathematics (30) ]`).
    - Clicking a tab navigates to the first question in that section or persists the last visited position.
  - **Left/Center Main Examination Canvas**:
    - Header: Question Number, Marks info (`Mark(s): +4.00, Negative: -1.00`).
    - Question Content: Crisp rendered text, tables, and formula equations.
    - Option List:
      - Radio buttons for `MCQ_SINGLE`.
      - Checkboxes for `MCQ_MULTI`.
      - Number input pad / on-screen virtual keypad for `NUMERICAL` input.
  - **Right Sidebar — NTA Question Palette**:
    - **Five Distinct Palette States**:
      1. `Not Visited`: Light Gray rectangular/rounded tile (Question not opened yet).
      2. `Not Answered`: Bright Orange/Red tile (Question viewed but no option selected).
      3. `Answered`: Solid Green tile (Response selected and saved).
      4. `Marked for Review`: Deep Purple circular tile (Question marked for later review without answer).
      5. `Answered & Marked for Review`: Purple tile with a distinct Green badge/dot (Option selected, but candidate flagged for secondary verification; **evaluated in final scoring** per NTA guidelines).
    - Grid of Question Numbers: Clickable tiles for instant non-linear navigation.
    - Live Summary Counters: Real-time badges displaying current counts for each of the 5 states.
  - **Bottom Action Footer Bar**:
    - Left:
      - `[ Mark for Review & Next ]` (purple outline button): Sets status to Marked for Review and advances to next question.
      - `[ Clear Response ]` (gray outline button): Clears active selection for current question.
    - Right:
      - `[ Previous ]`: Navigates to preceding question in sequence.
      - `[ Save & Next ]` (primary blue button): Dispatches asynchronous autosave payload and advances.
      - `[ Submit Exam ]` (accent green/red button): Triggers pre-submission summary dialog.

---

### 3.5 STU-05: Pre-Submission Summary Confirmation Modal
- **Trigger**: Click on `[ Submit Exam ]` or **Automatic Server-Authoritative Timer Expiry**.
- **Summary Matrix Table**:
  | Section | Total Questions | Answered | Not Answered | Marked for Review | Answered & Marked for Review | Not Visited |
  |:---|:---:|:---:|:---:|:---:|:---:|:---:|
  | Section 1: Physics | 30 | 24 | 3 | 1 | 2 | 0 |
  | Section 2: Chemistry | 30 | 20 | 5 | 2 | 1 | 2 |
  | Section 3: Mathematics | 30 | 18 | 8 | 0 | 1 | 3 |
  | **Overall Total** | **90** | **62** | **16** | **3** | **4** | **5** |
- **Confirmation Prompt**:
  - "Are you sure you want to submit your examination? Once submitted, no further changes can be made."
  - Action buttons: `[ Cancel / Return to Exam ]` vs `[ Confirm Final Submission ]`.

---

### 3.6 EVL-01 to EVL-04: Automated Evaluation & Deep Analytics
- **Scoring Pipeline**:
  - Evaluation executed asynchronously on background workers (Celery + Redis).
  - Matches candidate attempt responses against finalized answer keys.
  - Calculates:
    - Raw Score = $\sum (\text{Correct} \times \text{Positive}) - \sum (\text{Incorrect} \times \text{Negative})$
    - Accuracy % = $\frac{\text{Correct}}{\text{Attempted}} \times 100$
    - Percentile = $\frac{\text{Total Candidates with Score } \le S}{N} \times 100$
    - Merit Rank: Deterministic tie-breaking rules (higher subject score, fewer negatives, candidate age).
- **Analytics Presentation**:
  - Batch performance histogram (bell curve distribution).
  - Subject-wise comparative radar charts.
  - Question difficulty discrimination index (identifies questions where high performers failed).
  - Downloadable student scorecards and batch merit list in PDF/Excel formats.

---

## 4. Reverse-Engineered Route Map Diagram

```
Public / Auth Layer:
  ├── GET  /login                 (Login Hub: Password, OTP, Signup tabs)
  ├── POST /login                 (Credentials Auth -> Returns session + redirect)
  ├── POST /login/phone           (Dispatches SMS OTP)
  ├── POST /login/otp             (Verifies SMS OTP + Sets Password)
  ├── POST /login/signup          (Self-registration)
  └── POST /logout                (Session invalidation)

Staff Administrative Layer:
  ├── GET  /staff/ or /dashboard/ (Operational KPI Overview)
  ├── CRUD /batches/              (Batch cohort rosters & enrollments)
  ├── CRUD /centers/              (Test center definition & capacity)
  ├── CRUD /students/             (Student master records)
  ├── CRUD /faculty/              (Staff & examiner accounts)
  ├── CRUD /question-bank/        (Question repository & tag taxonomy)
  ├── CRUD /exams/                (Exam authoring, sections & marking schemes)
  ├── POST /exam/<id>/schedule/   (Date-time window & batch allocation)
  ├── POST /exam/<id>/publish/    (Transition to PUBLISHED)
  ├── GET  /monitoring/           (Live proctoring & attendance grid)
  ├── POST /evaluation/<id>/      (Automated grading pipeline trigger)
  ├── GET  /results/              (Rank list, scoreboards, batch reports)
  └── GET  /settings/             (Institution white-label configuration)

Student Examination Engine Layer:
  ├── GET  /online-exams/         (Candidate exam lobby)
  ├── GET  /online-exams/<id>/instructions/  (Advisory & declaration)
  ├── GET  /online-exams/<id>/test/          (NTA CBT interactive examination screen)
  ├── POST /online-exams/<id>/save/          (Asynchronous idempotent autosave)
  ├── GET  /online-exams/<id>/summary/       (Pre-submission status matrix)
  ├── POST /online-exams/<id>/submit/        (Final atomic lock & evaluation enqueue)
  └── GET  /online-exams/<id>/finish/        (Completion receipt & scorecard access)
```
