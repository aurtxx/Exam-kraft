# EZExam Reconstruction — Observable API Contracts Specification

**Document Version**: 1.0.0  
**Status**: Specification Complete  
**Author**: Agent 3 (System Architecture Analyst)  
**Date**: 2026-11-24  
**Target Architecture**: Django 5 + Django REST Framework + Django Channels (ASGI)  

---

## 1. Architectural Overview & Protocols

The EZExam platform follows a hybrid communication architecture:
1. **RESTful HTTP/2 APIs**: Used for authentication, administrative operations, question paper authoring, candidate assignments, student batch management, and evaluation reporting. Standard response envelopes follow predictable JSON structures with HTTP status codes.
2. **WebSocket (ASGI / Django Channels)**: Used during active candidate examination sessions for:
   - Server-authoritative timer synchronization.
   - Periodic candidate heartbeat and connectivity monitoring.
   - Real-time proctoring alerts (window switch warnings, focus loss, proctor broadcasts).
   - High-throughput response autosave acknowledgment.
3. **HTTP REST Fallback**: If WebSocket connection fails or is blocked by network proxies, candidate exam clients fall back transparently to periodic HTTP polling and REST response persistence (`/api/v1/attempts/{id}/heartbeat/` and `/api/v1/attempts/{id}/save_response/`).

---

## 2. Global Headers & Envelopes

### 2.1 Standard Request Headers
```http
Authorization: Bearer <access_jwt_token>
X-CSRFToken: <csrftoken>             (when using session-based / cookie auth)
X-Tenant-ID: <organization_uuid_or_slug>
Content-Type: application/json
Accept: application/json
```

### 2.2 Standard Success Response Envelope
```json
{
  "status": "SUCCESS",
  "data": { ... },
  "message": "Operation completed successfully"
}
```

### 2.3 Standard Error Response Envelope
```json
{
  "status": "ERROR",
  "code": "VALIDATION_FAILED | UNAUTHORIZED | EXAM_EXPIRED | ATTEMPT_LOCKED",
  "message": "Human-readable explanation of error",
  "errors": {
    "field_name": ["Specific validation error description"]
  }
}
```

---

## 3. Observable API Contracts by Functional Module

---

### Module A: Authentication & User Session Management

#### 1. Staff / User Login
- **Endpoint**: `POST /api/v1/auth/login/` (Legacy Reference: `POST /login`)
- **Description**: Authenticate staff, faculty, or students using credentials. Supports username/email/phone.
- **Request Body**:
  ```json
  {
    "username": "admin@institution.edu",
    "password": "SecurePassword123!",
    "next": "/staff"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "status": "SUCCESS",
    "access": "eyJhbGciOiJIUzI1NiIsIn...",
    "refresh": "eyJhbGciOiJIUzI1NiIsIn...",
    "user": {
      "id": "e2a4874c-478a-49f9-a29d-075e33d02a91",
      "name": "Prof. Alan Turing",
      "email": "admin@institution.edu",
      "phone": "+919876543210",
      "role": "ORG_ADMIN",
      "is_active": true
    },
    "organization": {
      "id": "8b51d113-11ef-42d4-bbbb-f26e382d5a0c",
      "slug": "ezexamqwertyuiop",
      "name": "Apex Engineering Academy",
      "domain": "ezexamqwertyuiop.ezexam.in"
    }
  }
  ```
- **Response `401 Unauthorized`**:
  ```json
  {
    "status": "ERROR",
    "code": "INVALID_CREDENTIALS",
    "message": "Invalid username or password provided."
  }
  ```

#### 2. OTP Authentication Initiation
- **Endpoint**: `POST /api/v1/auth/otp/send/` (Legacy Reference: `POST /login/phone`)
- **Request Body**:
  ```json
  {
    "phone": "9876543210",
    "usertype": "staff"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "status": "SUCCESS",
    "message": "6-digit verification code dispatched to registered mobile."
  }
  ```

#### 3. OTP Verification & Password Reset
- **Endpoint**: `POST /api/v1/auth/otp/verify/` (Legacy Reference: `POST /login/otp`)
- **Request Body**:
  ```json
  {
    "phone": "9876543210",
    "otp": "482910",
    "password1": "NewStrongPass#2026",
    "password2": "NewStrongPass#2026"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "status": "SUCCESS",
    "message": "Password updated successfully. You may now log in."
  }
  ```

#### 4. Current User Session Profile
- **Endpoint**: `GET /api/v1/auth/me/`
- **Response `200 OK`**:
  ```json
  {
    "status": "SUCCESS",
    "user": {
      "id": "e2a4874c-478a-49f9-a29d-075e33d02a91",
      "name": "Administrator",
      "role": "SUPERADMIN",
      "permissions": ["manage_orgs", "manage_exams", "manage_users", "view_reports"]
    }
  }
  ```

---

### Module B: Organization & Master Data Management

#### 1. Retrieve Master Data Select Lists
- **Endpoint**: `GET /api/v1/organizations/select-fields/` (Legacy Reference: `GET /staff/studs_select_fields`)
- **Description**: Returns all classes/batches, branches/groups, and examination centers configured for the active organization.
- **Response `200 OK`**:
  ```json
  {
    "status": "SUCCESS",
    "classes": [
      { "id": "11111111-1111-1111-1111-111111111111", "name": "Class 11 A", "code": "C11A" },
      { "id": "22222222-2222-2222-2222-222222222222", "name": "Class 12 B", "code": "C12B" }
    ],
    "groups": [
      { "id": "33333333-3333-3333-3333-333333333333", "name": "JEE-Main", "code": "JEE" },
      { "id": "44444444-4444-4444-4444-444444444444", "name": "NEET", "code": "NEET" }
    ],
    "centres": [
      { "id": "55555555-5555-5555-5555-555555555555", "name": "North Campus Centre", "code": "NC01" },
      { "id": "66666666-6666-6666-6666-666666666666", "name": "South Campus Centre", "code": "SC02" }
    ]
  }
  ```

#### 2. Create / Update Batch / Class
- **Endpoint**: `POST /api/v1/organizations/batches/` (Legacy Reference: `POST /staff/add_edit_class`)
- **Request Body**:
  ```json
  {
    "name": "Class 12 Physics Elite",
    "code": "C12PE",
    "branch_id": "33333333-3333-3333-3333-333333333333",
    "description": "2026 JEE Advanced Target Batch"
  }
  ```
- **Response `201 Created`**:
  ```json
  {
    "status": "SUCCESS",
    "id": "77777777-7777-7777-7777-777777777777",
    "name": "Class 12 Physics Elite",
    "message": "Batch created successfully"
  }
  ```

#### 3. Create / Update Examination Center
- **Endpoint**: `POST /api/v1/organizations/centers/` (Legacy Reference: `POST /staff/add_edit_centre`)
- **Request Body**:
  ```json
  {
    "name": "City Center Lab 3",
    "code": "CCL03",
    "address": "4th Floor, Tech Hub Tower, Bengaluru",
    "capacity": 150,
    "is_active": true
  }
  ```

#### 4. Update Organization Branding & Settings
- **Endpoint**: `PATCH /api/v1/organizations/settings/` (Legacy Reference: `POST /admin/edit_org_info`, `/staff/update_insti`)
- **Request Body**:
  ```json
  {
    "title": "Apex National Academy",
    "domain": "apex.ezexam.in",
    "allow_student_signup": false,
    "allow_student_pdf_download": true,
    "enable_video_assistance": false,
    "theme_primary_color": "#1eaeff",
    "logo_url": "https://storage.provider.com/logos/apex.png"
  }
  ```

---

### Module C: Faculty & Student Roster Management

#### 1. Retrieve Faculty List
- **Endpoint**: `GET /api/v1/users/faculty/` (Legacy Reference: `POST /staff/get_facs`)
- **Response `200 OK`**:
  ```json
  {
    "status": "SUCCESS",
    "faculties": [
      {
        "id": "fac-001",
        "name": "Dr. Richard Feynman",
        "phone": "+919876500001",
        "email": "feynman@apex.edu",
        "subjects": ["Physics", "Mechanics"],
        "centres": ["North Campus Centre"],
        "is_active": true
      }
    ]
  }
  ```

#### 2. Create / Update Faculty Member
- **Endpoint**: `POST /api/v1/users/faculty/` (Legacy Reference: `POST /staff/add_fac`)
- **Request Body**:
  ```json
  {
    "name": "Dr. Richard Feynman",
    "phone": "+919876500001",
    "email": "feynman@apex.edu",
    "password": "FacultyPassword#2026",
    "subject_ids": ["subj-phys-01"],
    "centre_ids": ["centre-nc-01"],
    "batch_ids": ["batch-12a"],
    "is_active": true
  }
  ```

#### 3. Paginated Student Roster
- **Endpoint**: `GET /api/v1/users/students/` (Legacy Reference: `POST /staff/get_studs_paging`)
- **Query Parameters**:
  - `page`: Integer (default: 1)
  - `page_size`: Integer (default: 25)
  - `search`: String (searches name, roll number, phone)
  - `batch_id`: UUID
  - `centre_id`: UUID
- **Response `200 OK`**:
  ```json
  {
    "status": "SUCCESS",
    "count": 120,
    "total_pages": 5,
    "current_page": 1,
    "students": [
      {
        "id": "stud-101",
        "roll_number": "2026001",
        "name": "Aryabhata Sharma",
        "phone": "+919123456789",
        "email": "aryabhata@student.org",
        "batch_name": "Class 12 B",
        "centre_name": "North Campus Centre",
        "branch_name": "JEE-Main",
        "is_active": true
      }
    ]
  }
  ```

#### 4. Single Student Creation / Edit
- **Endpoint**: `POST /api/v1/users/students/` (Legacy Reference: `POST /staff/add_stud`, `form-add-student`)
- **Request Body**:
  ```json
  {
    "roll_number": "2026001",
    "current_roll_number": "2026001",
    "name": "Aryabhata Sharma",
    "phone": "+919123456789",
    "email": "aryabhata@student.org",
    "password": "StudentPin@2026",
    "batch_id": "22222222-2222-2222-2222-222222222222",
    "centre_id": "55555555-5555-5555-5555-555555555555",
    "branch_id": "33333333-3333-3333-3333-333333333333",
    "is_active": true
  }
  ```

#### 5. Bulk Student CSV Upload
- **Endpoint**: `POST /api/v1/users/students/bulk-upload/` (Legacy Reference: `POST /staff/add_studs_csv`)
- **Request Format**: `multipart/form-data` with `file`: CSV / XLSX file.
- **CSV Headers Expected**: `RollNumber,Name,Phone,Email,BatchCode,CentreCode,BranchCode,Password`
- **Response `200 OK`**:
  ```json
  {
    "status": "SUCCESS",
    "total_processed": 50,
    "created_count": 48,
    "updated_count": 2,
    "errors": []
  }
  ```

---

### Module D: Question Bank & Question Paper Authoring

#### 1. Retrieve Question Papers
- **Endpoint**: `GET /api/v1/question-papers/` (Legacy Reference: `POST /staff/get_qpaps`)
- **Response `200 OK`**:
  ```json
  {
    "status": "SUCCESS",
    "question_papers": [
      {
        "id": "qpap-47327",
        "name": "Demo Exam",
        "exam_type": "IIT-JEE",
        "subjects": ["Maths", "Physics", "Chemistry"],
        "duration_minutes": 60,
        "total_questions": 15,
        "status": "PUBLISHED",
        "created_by": "Admin",
        "created_date": "2026-10-21"
      }
    ]
  }
  ```

#### 2. Create Question Paper
- **Endpoint**: `POST /api/v1/question-papers/` (Legacy Reference: `POST /staff/add_qpap`)
- **Request Body**:
  ```json
  {
    "name": "JEE Advanced Physics & Maths Grand Test 01",
    "exam_type": "JEE-Advanced",
    "duration_minutes": 180,
    "instructions": "All questions are compulsory. Use of calculators is strictly prohibited.",
    "is_full_pdf": false
  }
  ```
- **Response `201 Created`**:
  ```json
  {
    "status": "SUCCESS",
    "id": "qpap-99001",
    "message": "Question paper initialized."
  }
  ```

#### 3. Retrieve Complete Question Paper Payload (Questions & Answers)
- **Endpoint**: `GET /api/v1/question-papers/{id}/questions/` (Legacy Reference: `GET /staff/onexam/{qpap_id}`)
- **Response `200 OK`**:
  ```json
  {
    "status": "SUCCESS",
    "metadata": {
      "id": "qpap-47327",
      "name": "Demo Exam",
      "s3_directory": "custom/84So8ji1tmHr23cTPvEXsg",
      "salt": "46726902",
      "duration_minutes": 60,
      "total_questions": 15
    },
    "questions": [
      {
        "id": 2859523,
        "question_number": 1,
        "section": "Maths",
        "question_type": "MCQ_SINGLE",
        "key": "C",
        "positive_marks": 3.0,
        "negative_marks": -1.0,
        "partial_marks": 0.0,
        "difficulty": "MEDIUM",
        "is_cancelled": false,
        "content_text": "Let $A$ be a $3 \\times 3$ invertible matrix. If $\\det(A) = 4$, then $\\det(2 \\text{adj}(A))$ equals:",
        "options": [
          { "key": "A", "text": "32" },
          { "key": "B", "text": "64" },
          { "key": "C", "text": "128" },
          { "key": "D", "text": "256" }
        ],
        "explanation": "Formula: $\\det(k \\text{adj}(A)) = k^n (\\det(A))^{n-1} = 2^3 \\times 4^2 = 8 \\times 16 = 128$."
      },
      {
        "id": 2859528,
        "question_number": 6,
        "section": "Physics",
        "question_type": "MCQ_MULTI",
        "key": "A,C,D",
        "positive_marks": 4.0,
        "negative_marks": 0.0,
        "partial_marks": 1.0,
        "difficulty": "HARD",
        "is_cancelled": false,
        "content_text": "A particle moves in the $xy$-plane according to equations $x(t) = 3\\cos(2t)$ and $y(t) = 4\\sin(2t)$. Which of the following statements are true?",
        "options": [
          { "key": "A", "text": "The trajectory is an ellipse." },
          { "key": "B", "text": "The speed is constant." },
          { "key": "C", "text": "The acceleration is directed toward the origin." },
          { "key": "D", "text": "The period of motion is $\\pi$ seconds." }
        ]
      },
      {
        "id": 2859533,
        "question_number": 11,
        "section": "Chemistry",
        "question_type": "NUMERICAL",
        "key": "4",
        "positive_marks": 4.0,
        "negative_marks": 0.0,
        "partial_marks": 0.0,
        "difficulty": "HARD",
        "is_cancelled": false,
        "content_text": "Calculate the total number of unpaired electrons in $[\\text{Fe}(\\text{H}_2\\text{O})_6]^{2+}$."
      }
    ]
  }
  ```

#### 4. Add / Update Question in Paper
- **Endpoint**: `POST /api/v1/question-papers/{id}/questions/` (Legacy Reference: `POST /staff/add_qstn`, `POST /staff/update_qstn`)
- **Request Body (or Multipart Form)**:
  ```json
  {
    "question_number": 1,
    "section": "Maths",
    "question_type": "MCQ_SINGLE",
    "key": "C",
    "positive_marks": 3.0,
    "negative_marks": -1.0,
    "partial_marks": 0.0,
    "difficulty": 2,
    "topic": "Matrices and Determinants",
    "content_text": "Question statement in LaTeX / Markdown",
    "options": [
      { "key": "A", "text": "Option A text" },
      { "key": "B", "text": "Option B text" },
      { "key": "C", "text": "Option C text" },
      { "key": "D", "text": "Option D text" }
    ],
    "explanation": "Step-by-step solution"
  }
  ```

---

### Module E: Online Examination Lifecycle & Scheduling

#### 1. Retrieve Scheduled Online Exams
- **Endpoint**: `GET /api/v1/examinations/` (Legacy Reference: `POST /staff/get_onexs`)
- **Response `200 OK`**:
  ```json
  {
    "status": "SUCCESS",
    "examinations": [
      {
        "id": "60297",
        "question_paper_id": "47327",
        "name": "TEST-ONLY Browser Research 20261104",
        "start_window": "2026-10-21T20:13:00Z",
        "end_window": "2026-10-31T20:13:00Z",
        "duration_minutes": 60,
        "status": "SCHEDULED",
        "assigned_groups": ["JEE-Main"],
        "assigned_centres": [],
        "shuffle_questions": false,
        "camera_proctoring": false,
        "max_window_switches": 5,
        "allow_section_skip": false,
        "practice_mode": false,
        "pc_only": false,
        "short_url": "ezex.in/sample"
      }
    ]
  }
  ```

#### 2. Create / Schedule Online Examination
- **Endpoint**: `POST /api/v1/examinations/` (Legacy Reference: `POST /staff/add_onex`, `POST /staff/add_onex_link`)
- **Request Body**:
  ```json
  {
    "question_paper_id": "47327",
    "name": "JEE Main All-India Mock 01",
    "start_window": "2026-11-25T09:00:00Z",
    "end_window": "2026-11-25T12:00:00Z",
    "duration_minutes": 180,
    "batch_ids": ["33333333-3333-3333-3333-333333333333"],
    "centre_ids": [],
    "shuffle_questions": true,
    "camera_proctoring": true,
    "max_window_switches": 3,
    "allow_section_skip": false,
    "hide_results": true,
    "hide_rank": true,
    "hide_analytics": true,
    "pc_only": true,
    "practice_mode": false
  }
  ```
- **Response `201 Created`**:
  ```json
  {
    "status": "SUCCESS",
    "id": "60298",
    "short_url": "ezex.in/jee01mock",
    "message": "Online examination created and scheduled."
  }
  ```

#### 3. Assign Candidates to Examination
- **Endpoint**: `POST /api/v1/examinations/{id}/assign-candidates/` (Legacy Reference: `POST /staff/get_onex_studs`)
- **Request Body**:
  ```json
  {
    "student_ids": ["stud-101", "stud-102", "stud-103"],
    "select_all_matching_batches": true,
    "batch_ids": ["33333333-3333-3333-3333-333333333333"]
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "status": "SUCCESS",
    "assigned_count": 105,
    "message": "105 candidates assigned to examination."
  }
  ```

---

### Module F: Student Examination Engine (Candidate Real-Time API)

#### 1. Candidate Exam Verification & Lobby Entry
- **Endpoint**: `GET /api/v1/student/lobby/{short_code_or_exam_id}/`
- **Authentication**: Candidate Bearer Token or Session Cookie.
- **Description**: Validates candidate assignment, checks device compliance (PC-only), verifies camera readiness, and renders instructions.
- **Response `200 OK`**:
  ```json
  {
    "status": "SUCCESS",
    "can_start": true,
    "exam": {
      "id": "60297",
      "title": "JEE Main All-India Mock 01",
      "duration_minutes": 180,
      "total_questions": 15,
      "total_marks": 60,
      "start_window": "2026-11-25T09:00:00Z",
      "end_window": "2026-11-25T12:00:00Z",
      "instructions": "All questions carry 4 marks. For MCQs, 1 mark is deducted for wrong answers.",
      "security": {
        "pc_only": true,
        "camera_required": true,
        "max_window_switches": 3
      }
    },
    "candidate": {
      "roll_number": "2026001",
      "name": "Aryabhata Sharma"
    }
  }
  ```

#### 2. Start Examination Attempt
- **Endpoint**: `POST /api/v1/student/attempts/start/`
- **Request Body**:
  ```json
  {
    "exam_id": "60297",
    "client_screen_resolution": "1920x1080",
    "browser_user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)..."
  }
  ```
- **Response `200 OK` (Attempt Initialized)**:
  ```json
  {
    "status": "SUCCESS",
    "attempt_token": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "attempt_id": "att-88192",
    "started_at": "2026-11-25T09:00:05.123Z",
    "server_deadline": "2026-11-25T12:00:05.123Z",
    "remaining_seconds": 10800,
    "sections": [
      {
        "id": "sec-m",
        "name": "Maths",
        "order": 1,
        "total_questions": 5,
        "question_ids": [2859523, 2859524, 2859525, 2859526, 2859527]
      },
      {
        "id": "sec-p",
        "name": "Physics",
        "order": 2,
        "total_questions": 5,
        "question_ids": [2859528, 2859529, 2859530, 2859531, 2859532]
      },
      {
        "id": "sec-c",
        "name": "Chemistry",
        "order": 3,
        "total_questions": 5,
        "question_ids": [2859533, 2859534, 2859535, 2859536, 2859537]
      }
    ],
    "existing_responses": {},
    "palette_summary": {
      "answered": 0,
      "unanswered": 15,
      "marked_for_review": 0,
      "answered_marked_for_review": 0,
      "not_visited": 15
    }
  }
  ```

#### 3. Save Question Response (Debounced REST Autosave)
- **Endpoint**: `POST /api/v1/student/attempts/{attempt_id}/responses/`
- **Request Body**:
  ```json
  {
    "question_id": 2859523,
    "selected_options": ["C"],
    "numerical_value": null,
    "status": "ANSWERED",
    "time_spent_seconds": 45,
    "client_timestamp": "2026-11-25T09:05:10.000Z"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "status": "SUCCESS",
    "saved_at": "2026-11-25T09:05:10.150Z",
    "question_id": 2859523,
    "remaining_seconds": 10495
  }
  ```
- **Error `403 Forbidden` (Late Submission After Deadline)**:
  ```json
  {
    "status": "ERROR",
    "code": "DEADLINE_EXPIRED",
    "message": "Response rejected: Server deadline + grace period has expired."
  }
  ```

#### 4. Real-Time Heartbeat & Server Timer Synchronization
- **Endpoint (HTTP Fallback)**: `POST /api/v1/student/attempts/{attempt_id}/heartbeat/`
- **Request Body**:
  ```json
  {
    "client_time": "2026-11-25T09:15:00.000Z",
    "window_blur_count": 1,
    "current_question_id": 2859528
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "status": "SUCCESS",
    "server_time": "2026-11-25T09:15:00.100Z",
    "server_deadline": "2026-11-25T12:00:05.123Z",
    "remaining_seconds": 9905,
    "is_terminated": false
  }
  ```

#### 5. Real-Time WebSocket Channel Protocol
- **Connection URL**: `wss://ezexamqwertyuiop.ezexam.in/ws/exam/{attempt_id}/?token={attempt_token}`
- **Protocol Flow**:
  1. **Client -> Server: PING**:
     ```json
     { "type": "heartbeat", "client_now": 1795598100 }
     ```
  2. **Server -> Client: PONG**:
     ```json
     {
       "type": "heartbeat_ack",
       "server_now": 1795598100150,
       "remaining_seconds": 9905
     }
     ```
  3. **Client -> Server: SAVE_RESPONSE**:
     ```json
     {
       "type": "save_response",
       "question_id": 2859528,
       "selected_options": ["A", "C", "D"],
       "status": "ANSWERED",
       "time_spent": 120
     }
     ```
  4. **Server -> Client: RESPONSE_SAVED**:
     ```json
     {
       "type": "save_ack",
       "question_id": 2859528,
       "persisted_at": 1795598100220
     }
     ```
  5. **Server -> Client: PROCTOR_WARNING**:
     ```json
     {
       "type": "warning",
       "event": "WINDOW_SWITCH_DETECTED",
       "message": "Warning 1/3: Navigating away from test screen is forbidden.",
       "switches_remaining": 2
     }
     ```

#### 6. Final Examination Submission (Idempotent)
- **Endpoint**: `POST /api/v1/student/attempts/{attempt_id}/submit/`
- **Request Body**:
  ```json
  {
    "submission_reason": "MANUAL_SUBMIT",
    "total_questions_answered": 14,
    "client_completed_at": "2026-11-25T11:45:20.000Z"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "status": "SUCCESS",
    "attempt_id": "att-88192",
    "submission_status": "SUBMITTED",
    "submitted_at": "2026-11-25T11:45:20.450Z",
    "message": "Examination submitted successfully. Results will be published by faculty."
  }
  ```
- **Response `409 Conflict` (Duplicate Submission Intercepted)**:
  ```json
  {
    "status": "SUCCESS",
    "code": "ALREADY_SUBMITTED",
    "submitted_at": "2026-11-25T11:45:20.450Z",
    "message": "Attempt was already recorded as submitted."
  }
  ```

---

### Module G: Submissions, Audit Logs & Evaluation Results

#### 1. Retrieve Candidate Submissions for an Exam
- **Endpoint**: `POST /api/v1/examinations/{id}/submissions/` (Legacy Reference: `POST /staff/get_subm`)
- **Request Body**:
  ```json
  {
    "onexid": "60297"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "status": "SUCCESS",
    "num_subm": 25,
    "num_paid": 0,
    "subm": [
      {
        "id": "subm-501",
        "stud__rollnum": "2026001",
        "stud__name": "Aryabhata Sharma",
        "started_at": "2026-11-25T09:00:05Z",
        "submitted_at": "2026-11-25T11:45:20Z",
        "final": true,
        "ignore": false,
        "score": 48.0,
        "rank": 1
      }
    ]
  }
  ```

#### 2. Retrieve Detailed Submission Audit Log
- **Endpoint**: `POST /api/v1/examinations/{id}/submissions/{roll_number}/audit/` (Legacy Reference: `POST /staff/get_subm_log`)
- **Request Body**:
  ```json
  {
    "onexid": "60297",
    "rollnum": "2026001"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "status": "SUCCESS",
    "rollnum": "2026001",
    "name": "Aryabhata Sharma",
    "resp": ",C,A,D,B,C,A+C+D,A+B+C+D,A+D,B+D,C,4,5,5,6,-",
    "qtypes": "1,1,1,1,1,2,2,2,2,2,3,3,3,3,3",
    "num_answered": 14,
    "total_questions": 15,
    "switches_count": 0,
    "caps": [
      { "timestamp": "2026-11-25T09:05:00Z", "url": "https://s3.provider.com/caps/c1.jpg" }
    ]
  }
  ```

#### 3. Re-open Closed Submission (Administrative Override)
- **Endpoint**: `POST /api/v1/examinations/{id}/submissions/{roll_number}/reopen/` (Legacy Reference: `POST /staff/set_subm_nonfinal`)
- **Request Body**:
  ```json
  {
    "onexid": "60297",
    "rollnum": "2026001",
    "additional_minutes": 15,
    "reason": "Power outage at exam center reported by proctor"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "status": "SUCCESS",
    "message": "Submission status set to non-final. Candidate may resume attempt."
  }
  ```

#### 4. Retrieve Evaluation Results & Rankings
- **Endpoint**: `POST /api/v1/examinations/{id}/results/` (Legacy Reference: `POST /staff/get_res`)
- **Request Body**:
  ```json
  {
    "onexid": "60297"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "status": "SUCCESS",
    "res": [
      {
        "RollNum": "2026001",
        "Name": "Aryabhata Sharma",
        "Rank": 1,
        "TotalScore": 52.0,
        "Percentile": 100.0,
        "CorrectCount": 13,
        "IncorrectCount": 1,
        "UnattemptedCount": 1,
        "SectionScores": {
          "Maths": 15.0,
          "Physics": 17.0,
          "Chemistry": 20.0
        }
      }
    ]
  }
  ```
