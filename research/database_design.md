# EZExam Reconstruction — PostgreSQL Relational Schema & Data Architecture

**Document Version**: 1.0.0  
**Status**: Architecture Approved  
**Author**: Agent 3 (System Architecture Analyst)  
**Date**: 2026-11-24  
**Persistence Engine**: PostgreSQL 16+ with Django 5 ORM  

---

## 1. Multi-Tenant Architecture & Isolation Model

### 1.1 Multi-Tenancy Strategy: Shared Database with Row-Level Isolation
To maximize performance, support thousands of students across multiple educational institutions, and keep deployment infrastructure lean:
- **Tenant Entity**: Represented by `Organization` (`accounts_organization`).
- **Tenant Key**: All tenant-scoped tables contain a non-nullable foreign key `organization_id` referencing `accounts_organization(id)`.
- **Tenant Isolation Enforcement**:
  1. **Base Tenant Model (`TenantModel`)**: Abstract Django base model that automatically attaches the tenant foreign key and overrides `objects` with `TenantManager`.
  2. **Automatic Query Filtering**: `TenantManager.get_queryset()` inspects thread-local or context-variable tenant context populated by `TenantMiddleware` from JWT / domain / headers, guaranteeing no query can accidentally return data belonging to another institution.
  3. **Composite Unique Constraints**: Uniqueness constraints (such as student roll numbers, batch codes, or question numbers) are composite with `organization_id` (`UNIQUE (organization_id, roll_number)`).

```python
# Multi-Tenant Base Pattern (Django 5)
class TenantManager(models.Manager):
    def get_queryset(self):
        tenant = get_current_tenant()
        if tenant:
            return super().get_queryset().filter(organization=tenant)
        return super().get_queryset()

class BaseTenantModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'accounts.Organization', 
        on_delete=models.CASCADE, 
        related_name='%(class)ss',
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True
```

---

## 2. Relational Entity-Relationship Model

```
+---------------------------------------------------------------------------------------------------+
|                                      ACCOUNTS & ORGANIZATIONS                                     |
|                                                                                                   |
|   +-----------------------+              +-----------------------+        +-------------------+   |
|   |     Organization      |1-----------* |         User          |1-----1 |    UserProfile    |   |
|   +-----------------------+              +-----------------------+        +-------------------+   |
|               |                                      |                                            |
+---------------+--------------------------------------+--------------------------------------------+
                |                                      |
+---------------+--------------------------------------+--------------------------------------------+
|               |                        ORGANIZATIONAL STRUCTURE                                   |
|               |                                      |                                            |
|   +-----------v-----------+              +-----------v-----------+        +-------------------+   |
|   |   ExaminationCenter   |1-----------* |  StudentBatchEnroll   |*-----1 |       Batch       |   |
|   +-----------------------+              +-----------------------+        +-------------------+   |
|                                                                                                   |
+---------------+-----------------------------------------------------------------------------------+
                |
+---------------+-----------------------------------------------------------------------------------+
|               |                        QUESTION BANK & AUTHORING                                  |
|               |                                                                                   |
|   +-----------v-----------+              +-----------------------+        +-------------------+   |
|   |     QuestionBank      |1-----------* |       Question        |1-----* |      Option       |   |
|   +-----------------------+              +-----------------------+        +-------------------+   |
|               |                                      |                                            |
|   +-----------v-----------+                          |                                            |
|   |        Section        |1-------------------------+                                            |
|   +-----------------------+                                                                       |
+---------------+-----------------------------------------------------------------------------------+
                |
+---------------+-----------------------------------------------------------------------------------+
|               |                        EXAMINATION & SCHEDULING                                   |
|               |                                                                                   |
|   +-----------v-----------+              +-----------------------+        +-------------------+   |
|   |      Examination      |1-----------* |  ExaminationSection   |1-----* |  ExaminationQuest |   |
|   +-----------------------+              +-----------------------+        +-------------------+   |
|         1           1                                                                             |
|         |           |                                                                             |
|         |           +------------------* +-----------------------+                                |
|         |                                |  CandidateAssignment  |                                |
|         |                                +-----------------------+                                |
|         |                                            |                                            |
+---------+--------------------------------------------+--------------------------------------------+
          |                                            |
+---------+--------------------------------------------+--------------------------------------------+
|         |                        EXAMINATION ENGINE & PERSISTENCE                                 |
|         |                                            |                                            |
|   +-----v-----------------+              +-----------v-----------+        +-------------------+   |
|   |  ExaminationAttempt   |1-----------* |    AttemptResponse    |        |  AttemptAuditLog  |   |
|   +-----------------------+              +-----------------------+        +-------------------+   |
|               1                                                                                   |
|               |                                                                                   |
|   +-----------v-----------+                                                                       |
|   |   EvaluationResult    |                                                                       |
|   +-----------------------+                                                                       |
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
```

---

## 3. Detailed Table Specifications & Data Dictionaries

### 3.1 App: `accounts`

#### Table: `accounts_organization`
Stores tenant profiles and tenant-wide operational settings.
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | Unique tenant identifier |
| `name` | `VARCHAR(255)` | `NOT NULL` | Registered name of institution |
| `slug` | `VARCHAR(100)` | `NOT NULL, UNIQUE, INDEX` | URL tenant slug (e.g. `ezexamqwertyuiop`) |
| `domain` | `VARCHAR(255)` | `NULLABLE, UNIQUE` | Custom custom domain mapping |
| `is_active` | `BOOLEAN` | `NOT NULL, DEFAULT TRUE` | Active subscription status |
| `settings` | `JSONB` | `NOT NULL, DEFAULT '{}'` | Tenant branding, colors, proctoring defaults |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL, DEFAULT NOW()` | Record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL, DEFAULT NOW()` | Record update timestamp |

#### Table: `accounts_user`
Unified user model implementing Django's `AbstractBaseUser` and `PermissionsMixin`.
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | Unique user identifier |
| `organization_id`| `UUID` | `NULLABLE, FK -> accounts_organization(id) ON DELETE CASCADE` | Null only for Platform SuperAdmin |
| `username` | `VARCHAR(150)` | `NOT NULL, UNIQUE` | Unique handle / system username |
| `email` | `VARCHAR(254)` | `NULLABLE` | Contact email address |
| `phone` | `VARCHAR(20)` | `NULLABLE` | Verified contact phone number |
| `password_hash`| `VARCHAR(255)` | `NOT NULL` | Argon2id / PBKDF2 hashed password |
| `role` | `VARCHAR(30)` | `NOT NULL` | `SUPERADMIN`, `ORG_ADMIN`, `FACULTY`, `STUDENT` |
| `is_active` | `BOOLEAN` | `NOT NULL, DEFAULT TRUE` | Account status |
| `is_staff` | `BOOLEAN` | `NOT NULL, DEFAULT FALSE` | Administrative portal access |
| `date_joined` | `TIMESTAMPTZ` | `NOT NULL, DEFAULT NOW()` | Registration timestamp |

*Indices & Constraints*:
- `CREATE INDEX idx_user_org_role ON accounts_user(organization_id, role);`
- `CREATE INDEX idx_user_phone ON accounts_user(phone);`

#### Table: `accounts_userprofile`
Extends user accounts with institutional profile attributes.
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | Profile record ID |
| `user_id` | `UUID` | `NOT NULL, UNIQUE, FK -> accounts_user(id) ON DELETE CASCADE` | One-to-one user link |
| `full_name` | `VARCHAR(255)` | `NOT NULL` | Candidate / Staff full name |
| `avatar_url` | `VARCHAR(500)` | `NULLABLE` | S3 profile image URL |
| `parent_name` | `VARCHAR(255)` | `NULLABLE` | Student parent/guardian name |
| `parent_phone`| `VARCHAR(20)` | `NULLABLE` | Parent emergency contact |
| `metadata` | `JSONB` | `NOT NULL, DEFAULT '{}'` | Arbitrary extensible attributes |

---

### 3.2 App: `organizations`

#### Table: `organizations_examinationcenter`
Physical examination venues, test labs, or regional centers.
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | Center ID |
| `organization_id`| `UUID` | `NOT NULL, FK -> accounts_organization(id) ON DELETE CASCADE` | Tenant owner |
| `name` | `VARCHAR(255)` | `NOT NULL` | Center name (e.g. North Campus Lab) |
| `code` | `VARCHAR(50)` | `NOT NULL` | Short code (e.g. `NC01`) |
| `address` | `TEXT` | `NULLABLE` | Physical venue address |
| `capacity` | `INTEGER` | `NOT NULL, DEFAULT 0` | Candidate terminal seat capacity |
| `is_active` | `BOOLEAN` | `NOT NULL, DEFAULT TRUE` | Operational state |

*Indices & Constraints*:
- `CONSTRAINT uq_center_code UNIQUE (organization_id, code);`

#### Table: `organizations_batch`
Cohorts, academic classes, or student divisions (e.g. "Class 12 B", "JEE Elite").
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | Batch ID |
| `organization_id`| `UUID` | `NOT NULL, FK -> accounts_organization(id) ON DELETE CASCADE` | Tenant owner |
| `name` | `VARCHAR(255)` | `NOT NULL` | Batch name |
| `code` | `VARCHAR(50)` | `NOT NULL` | Batch code |
| `stream` | `VARCHAR(50)` | `NOT NULL, DEFAULT 'OTHER'` | `JEE_MAIN`, `JEE_ADVANCED`, `NEET`, `OTHER` |
| `is_active` | `BOOLEAN` | `NOT NULL, DEFAULT TRUE` | Active academic status |

*Indices & Constraints*:
- `CONSTRAINT uq_batch_code UNIQUE (organization_id, code);`

#### Table: `organizations_studentbatchenrollment`
Student enrollment linking a candidate to their assigned Batch, Center, and Roll Number.
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | Enrollment ID |
| `student_id` | `UUID` | `NOT NULL, FK -> accounts_user(id) ON DELETE CASCADE` | Student account |
| `batch_id` | `UUID` | `NOT NULL, FK -> organizations_batch(id) ON DELETE CASCADE` | Enrolled batch |
| `center_id` | `UUID` | `NULLABLE, FK -> organizations_examinationcenter(id) ON DELETE SET NULL` | Test center |
| `roll_number` | `VARCHAR(100)` | `NOT NULL` | Institutional Roll Number |
| `enrolled_at` | `TIMESTAMPTZ` | `NOT NULL, DEFAULT NOW()` | Enrollment timestamp |
| `is_active` | `BOOLEAN` | `NOT NULL, DEFAULT TRUE` | Active enrollment flag |

*Indices & Constraints*:
- `CONSTRAINT uq_batch_rollnum UNIQUE (batch_id, roll_number);`
- `CREATE INDEX idx_student_roll ON organizations_studentbatchenrollment(roll_number);`

---

### 3.3 App: `question_bank`

#### Table: `questionbank_questionbank`
Catalog container organizing questions by subject or curriculum.
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | Question bank ID |
| `organization_id`| `UUID` | `NOT NULL, FK -> accounts_organization(id) ON DELETE CASCADE` | Tenant owner |
| `title` | `VARCHAR(255)` | `NOT NULL` | Title of question bank |
| `description` | `TEXT` | `NULLABLE` | Syllabus / scope description |
| `created_by_id` | `UUID` | `NOT NULL, FK -> accounts_user(id)` | Authoring faculty |

#### Table: `questionbank_section`
Academic subjects and examination sections (e.g. Mathematics, Physics, Chemistry).
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | Section ID |
| `organization_id`| `UUID` | `NOT NULL, FK -> accounts_organization(id) ON DELETE CASCADE` | Tenant owner |
| `name` | `VARCHAR(100)` | `NOT NULL` | Section name (e.g. "Physics") |
| `code` | `VARCHAR(30)` | `NOT NULL` | Code (e.g. `PHY`) |

#### Table: `questionbank_tag`
Topics and sub-topics for question classification and analytics.
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | Tag ID |
| `organization_id`| `UUID` | `NOT NULL, FK -> accounts_organization(id) ON DELETE CASCADE` | Tenant owner |
| `name` | `VARCHAR(100)` | `NOT NULL` | Topic name (e.g. "Electromagnetism") |
| `slug` | `VARCHAR(120)` | `NOT NULL` | Slug identifier |

#### Table: `questionbank_question`
Individual questions with multi-type support and rich content.
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | Question ID |
| `organization_id`| `UUID` | `NOT NULL, FK -> accounts_organization(id) ON DELETE CASCADE` | Tenant owner |
| `qbank_id` | `UUID` | `NULLABLE, FK -> questionbank_questionbank(id) ON DELETE SET NULL` | Linked question bank |
| `section_id` | `UUID` | `NOT NULL, FK -> questionbank_section(id) ON DELETE RESTRICT` | Subject section |
| `question_type` | `VARCHAR(30)` | `NOT NULL` | `MCQ_SINGLE`, `MCQ_MULTI`, `NUMERICAL`, `TEXT_SUBJECTIVE`, `CODING` |
| `content_text`| `TEXT` | `NOT NULL` | Question statement (Markdown / LaTeX) |
| `content_html`| `TEXT` | `NULLABLE` | Pre-rendered HTML representation |
| `image_url` | `VARCHAR(500)` | `NULLABLE` | S3 question image URL |
| `explanation` | `TEXT` | `NULLABLE` | Detailed solution / rationale |
| `solution_image_url`| `VARCHAR(500)` | `NULLABLE` | S3 solution diagram URL |
| `difficulty` | `VARCHAR(20)` | `NOT NULL, DEFAULT 'MEDIUM'` | `EASY`, `MEDIUM`, `HARD` |
| `is_cancelled` | `BOOLEAN` | `NOT NULL, DEFAULT FALSE` | Flag for invalidated questions |

*Indices & Constraints*:
- `CREATE INDEX idx_question_type_diff ON questionbank_question(question_type, difficulty);`

#### Table: `questionbank_option`
Choice options for MCQ questions.
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | Option ID |
| `question_id` | `UUID` | `NOT NULL, FK -> questionbank_question(id) ON DELETE CASCADE` | Parent question |
| `option_key` | `VARCHAR(5)` | `NOT NULL` | Option identifier: `A`, `B`, `C`, `D`, `E` |
| `content_text`| `TEXT` | `NOT NULL` | Option text / LaTeX |
| `content_html`| `TEXT` | `NULLABLE` | Rendered option HTML |
| `is_correct` | `BOOLEAN` | `NOT NULL, DEFAULT FALSE` | Answer key flag |
| `order` | `INTEGER` | `NOT NULL, DEFAULT 0` | Display order index |

*Indices & Constraints*:
- `CONSTRAINT uq_question_option_key UNIQUE (question_id, option_key);`

---

### 3.4 App: `examinations`

#### Table: `examinations_examination`
Central configuration for scheduled online tests.
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | Examination ID |
| `organization_id`| `UUID` | `NOT NULL, FK -> accounts_organization(id) ON DELETE CASCADE` | Tenant owner |
| `title` | `VARCHAR(255)` | `NOT NULL` | Examination title |
| `code` | `VARCHAR(50)` | `NOT NULL` | Unique exam code |
| `slug` | `VARCHAR(100)` | `NOT NULL` | URL short slug (e.g. `jee01mock`) |
| `instructions` | `TEXT` | `NULLABLE` | Examination instructions for lobby |
| `duration_minutes`| `INTEGER` | `NOT NULL, DEFAULT 60` | Test time limit in minutes |
| `total_marks` | `DECIMAL(8,2)`| `NOT NULL, DEFAULT 0.00` | Sum of all question marks |
| `passing_marks` | `DECIMAL(8,2)`| `NULLABLE` | Qualifying cut-off marks |
| `status` | `VARCHAR(20)` | `NOT NULL, DEFAULT 'DRAFT'` | `DRAFT`, `PUBLISHED`, `SCHEDULED`, `IN_PROGRESS`, `CLOSED`, `EVALUATED` |
| `start_window` | `TIMESTAMPTZ` | `NOT NULL` | Window open datetime |
| `end_window` | `TIMESTAMPTZ` | `NOT NULL` | Window close datetime |
| `shuffle_questions`| `BOOLEAN` | `NOT NULL, DEFAULT FALSE` | Randomize question order per student |
| `shuffle_options` | `BOOLEAN` | `NOT NULL, DEFAULT FALSE` | Randomize MCQ options |
| `camera_proctoring`| `BOOLEAN` | `NOT NULL, DEFAULT FALSE` | Periodic webcam snapshots enabled |
| `max_window_switches`| `INTEGER`| `NOT NULL, DEFAULT 3` | Disqualification limit for tab switching |
| `allow_section_skip`| `BOOLEAN` | `NOT NULL, DEFAULT TRUE` | Free section navigation permission |
| `practice_mode` | `BOOLEAN` | `NOT NULL, DEFAULT FALSE` | Practice mode without strict timer |
| `pc_only` | `BOOLEAN` | `NOT NULL, DEFAULT FALSE` | Enforce desktop/laptop browser only |
| `hide_results` | `BOOLEAN` | `NOT NULL, DEFAULT FALSE` | Suppress scores after submission |
| `hide_rank` | `BOOLEAN` | `NOT NULL, DEFAULT FALSE` | Suppress ranking display |
| `created_by_id` | `UUID` | `NOT NULL, FK -> accounts_user(id)` | Authoring staff |

*Indices & Constraints*:
- `CONSTRAINT uq_exam_code UNIQUE (organization_id, code);`
- `CREATE INDEX idx_exam_window ON examinations_examination(start_window, end_window, status);`

#### Table: `examinations_examinationsection`
Sections allocated to an examination (e.g. Section 1: Maths, Section 2: Physics).
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | Exam section ID |
| `exam_id` | `UUID` | `NOT NULL, FK -> examinations_examination(id) ON DELETE CASCADE` | Parent exam |
| `section_id` | `UUID` | `NOT NULL, FK -> questionbank_section(id) ON DELETE RESTRICT` | Master section |
| `title` | `VARCHAR(100)` | `NOT NULL` | Display title |
| `order` | `INTEGER` | `NOT NULL, DEFAULT 1` | Section sequence order |
| `total_questions`| `INTEGER` | `NOT NULL, DEFAULT 0` | Total questions in section |
| `marks_per_question`| `DECIMAL(5,2)`| `NOT NULL, DEFAULT 4.00` | Default positive marking |
| `negative_marks` | `DECIMAL(5,2)`| `NOT NULL, DEFAULT 1.00` | Default negative marking penalty |
| `partial_marks` | `DECIMAL(5,2)`| `NOT NULL, DEFAULT 0.00` | Partial marking for multi-correct |

*Indices & Constraints*:
- `CONSTRAINT uq_exam_section_order UNIQUE (exam_id, "order");`

#### Table: `examinations_examinationquestion`
Maps questions to examination sections with specific marking overrides.
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | Mapping ID |
| `exam_section_id`| `UUID` | `NOT NULL, FK -> examinations_examinationsection(id) ON DELETE CASCADE` | Section |
| `question_id` | `UUID` | `NOT NULL, FK -> questionbank_question(id) ON DELETE RESTRICT` | Question |
| `order` | `INTEGER` | `NOT NULL` | Sequence number within section |
| `marks` | `DECIMAL(5,2)`| `NOT NULL` | Positive marks for this question |
| `negative_marks`| `DECIMAL(5,2)`| `NOT NULL` | Negative marks for incorrect response |
| `partial_marks` | `DECIMAL(5,2)`| `NOT NULL, DEFAULT 0.00` | Partial marks (for multi-select) |

*Indices & Constraints*:
- `CONSTRAINT uq_exam_section_qorder UNIQUE (exam_section_id, "order");`

#### Table: `examinations_candidateassignment`
Assigns candidates (by batch, center, or individual) to take the examination.
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | Assignment ID |
| `exam_id` | `UUID` | `NOT NULL, FK -> examinations_examination(id) ON DELETE CASCADE` | Assigned exam |
| `student_id` | `UUID` | `NOT NULL, FK -> accounts_user(id) ON DELETE CASCADE` | Candidate |
| `batch_id` | `UUID` | `NULLABLE, FK -> organizations_batch(id) ON DELETE SET NULL` | Candidate batch |
| `center_id` | `UUID` | `NULLABLE, FK -> organizations_examinationcenter(id) ON DELETE SET NULL` | Assigned center |
| `assigned_at` | `TIMESTAMPTZ` | `NOT NULL, DEFAULT NOW()` | Assignment timestamp |

*Indices & Constraints*:
- `CONSTRAINT uq_exam_student UNIQUE (exam_id, student_id);`
- `CREATE INDEX idx_candidate_exam ON examinations_candidateassignment(student_id, exam_id);`

---

### 3.5 App: `engine` (Real-Time Examination Engine)

#### Table: `engine_examinationattempt`
Candidate examination session state with server-authoritative timer.
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | Attempt ID |
| `attempt_token` | `UUID` | `NOT NULL, UNIQUE, DEFAULT gen_random_uuid()` | Secure access token for WebSocket & REST |
| `exam_id` | `UUID` | `NOT NULL, FK -> examinations_examination(id) ON DELETE CASCADE` | Exam attempted |
| `student_id` | `UUID` | `NOT NULL, FK -> accounts_user(id) ON DELETE CASCADE` | Candidate |
| `status` | `VARCHAR(30)` | `NOT NULL, DEFAULT 'ASSIGNED'` | `ASSIGNED`, `IN_PROGRESS`, `SUBMITTED`, `AUTO_SUBMITTED`, `EVALUATED`, `TERMINATED` |
| `started_at` | `TIMESTAMPTZ` | `NULLABLE` | Exact server timestamp when candidate started |
| `server_deadline`| `TIMESTAMPTZ`| `NULLABLE` | Calculated: `started_at + duration + grace_period` |
| `submitted_at` | `TIMESTAMPTZ` | `NULLABLE` | Final submission timestamp |
| `window_switch_count`| `INTEGER`| `NOT NULL, DEFAULT 0` | Proctoring window switch tally |
| `client_ip` | `INET` | `NULLABLE` | IP address at start |
| `user_agent` | `TEXT` | `NULLABLE` | Browser client string |
| `is_reopened` | `BOOLEAN` | `NOT NULL, DEFAULT FALSE` | Administrative reopen override flag |

*Indices & Constraints*:
- `CONSTRAINT uq_attempt_candidate_exam UNIQUE (exam_id, student_id);` (Only 1 attempt per candidate per exam)
- `CREATE INDEX idx_attempt_token ON engine_examinationattempt(attempt_token);`
- `CREATE INDEX idx_attempt_status_deadline ON engine_examinationattempt(status, server_deadline);`

#### Table: `engine_attemptresponse`
Granular candidate answers for each question, updated via autosave.
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | Response ID |
| `attempt_id` | `UUID` | `NOT NULL, FK -> engine_examinationattempt(id) ON DELETE CASCADE` | Parent attempt |
| `question_id` | `UUID` | `NOT NULL, FK -> questionbank_question(id) ON DELETE RESTRICT` | Answered question |
| `selected_options`| `JSONB` | `NULLABLE` | Array of selected option keys (e.g. `["A", "C"]`) |
| `numerical_response`| `DECIMAL(12,4)`| `NULLABLE` | Value for numerical answer questions |
| `text_response`| `TEXT` | `NULLABLE` | Text for subjective / coding questions |
| `status` | `VARCHAR(40)` | `NOT NULL, DEFAULT 'NOT_VISITED'` | `NOT_VISITED`, `NOT_ANSWERED`, `ANSWERED`, `MARKED_FOR_REVIEW`, `ANSWERED_AND_MARKED_FOR_REVIEW` |
| `time_spent_seconds`| `INTEGER` | `NOT NULL, DEFAULT 0` | Time elapsed on this specific question |
| `saved_at` | `TIMESTAMPTZ` | `NOT NULL, DEFAULT NOW()` | Last update timestamp |
| `server_received_at`| `TIMESTAMPTZ`| `NOT NULL, DEFAULT NOW()` | Server receipt timestamp |

*Indices & Constraints*:
- `CONSTRAINT uq_attempt_question UNIQUE (attempt_id, question_id);`
- `CREATE INDEX idx_response_attempt_status ON engine_attemptresponse(attempt_id, status);`

#### Table: `engine_attemptauditlog`
Tamper-proof event log capturing candidate activity during the test.
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | Audit event ID |
| `attempt_id` | `UUID` | `NOT NULL, FK -> engine_examinationattempt(id) ON DELETE CASCADE` | Parent attempt |
| `event_type` | `VARCHAR(50)` | `NOT NULL` | `START`, `HEARTBEAT`, `SAVE_RESPONSE`, `WINDOW_BLUR`, `WINDOW_FOCUS`, `AUTO_SUBMIT`, `MANUAL_SUBMIT`, `PROCTOR_ALERT` |
| `event_data` | `JSONB` | `NOT NULL, DEFAULT '{}'` | Payload (e.g. current question, switch count) |
| `timestamp` | `TIMESTAMPTZ` | `NOT NULL, DEFAULT NOW()` | Event timestamp |

---

### 3.6 App: `evaluation`

#### Table: `evaluation_evaluationresult`
Scored results, ranks, and percentiles computed by automated grading engine.
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | Result ID |
| `attempt_id` | `UUID` | `NOT NULL, UNIQUE, FK -> engine_examinationattempt(id) ON DELETE CASCADE` | Linked attempt |
| `total_score` | `DECIMAL(8,2)`| `NOT NULL, DEFAULT 0.00` | Aggregate marks scored |
| `score_percentage`| `DECIMAL(5,2)`| `NOT NULL, DEFAULT 0.00` | Percentage of total marks |
| `passed` | `BOOLEAN` | `NOT NULL, DEFAULT FALSE` | Whether passing marks achieved |
| `correct_count`| `INTEGER` | `NOT NULL, DEFAULT 0` | Number of correct responses |
| `incorrect_count`| `INTEGER` | `NOT NULL, DEFAULT 0` | Number of incorrect responses |
| `unattempted_count`| `INTEGER`| `NOT NULL, DEFAULT 0` | Number of skipped questions |
| `section_scores`| `JSONB` | `NOT NULL, DEFAULT '{}'` | Breakdown: `{ "Maths": 15.0, "Physics": 17.0 }` |
| `rank` | `INTEGER` | `NULLABLE` | Institutional cohort rank |
| `percentile` | `DECIMAL(6,3)`| `NULLABLE` | Cohort percentile (0.000 to 100.000) |
| `evaluated_at` | `TIMESTAMPTZ` | `NOT NULL, DEFAULT NOW()` | Evaluation timestamp |
| `is_published` | `BOOLEAN` | `NOT NULL, DEFAULT FALSE` | Visibility to candidate |

*Indices & Constraints*:
- `CREATE INDEX idx_eval_rank ON evaluation_evaluationresult(total_score DESC, evaluated_at ASC);`

---

## 4. State Machines & System Invariants

### 4.1 Examination Lifecycle State Machine

```
                   +-------------+
                   |    DRAFT    |
                   +-------------+
                          |
                   [Staff Publishes]
                          v
                   +-------------+
                   |  PUBLISHED  |
                   +-------------+
                          |
             [Start Window Configured]
                          v
                   +-------------+
                   |  SCHEDULED  |
                   +-------------+
                          |
               [Current Time >= Start]
                          v
                   +-------------+
                   | IN_PROGRESS |
                   +-------------+
                          |
            [Current Time > End Window]
                          v
                   +-------------+
                   |   CLOSED    |
                   +-------------+
                          |
               [Automated Evaluation]
                          v
                   +-------------+
                   |  EVALUATED  |
                   +-------------+
```

#### Transition Guards & Invariants:
1. **DRAFT -> PUBLISHED**: Guard: Must have at least 1 section and at least 1 question. Sum of question marks must equal `total_marks`.
2. **PUBLISHED -> SCHEDULED**: Guard: `start_window` and `end_window` must be defined, with `end_window > start_window` and `duration_minutes <= (end_window - start_window)`.
3. **SCHEDULED -> IN_PROGRESS**: Automated server trigger: `NOW() >= start_window`.
4. **IN_PROGRESS -> CLOSED**: Automated server trigger: `NOW() > end_window`. Rejects any new attempt starts.
5. **CLOSED -> EVALUATED**: Celery background task executes grading pipeline once all attempts are in terminal state (`SUBMITTED` or `AUTO_SUBMITTED`).

---

### 4.2 Candidate Attempt State Machine

```
               +-------------+
               |  ASSIGNED   |
               +-------------+
                      |
           [Student Clicks Start]
                      v
               +-------------+
   +---------->| IN_PROGRESS |<---------+
   |           +-------------+          |
   |              |         |           |
[Page          [Manual   [Server        [Admin
Refresh /     Submit]    Timer Expiry] Re-Open]
Recovery]         |         |           |
   |              v         v           |
   +--------+  +---------------+        |
            |  |   SUBMITTED   |--------+
            |  |AUTO_SUBMITTED |
            |  +---------------+
            |          |
            |    [Grading Run]
            |          v
            |  +---------------+
            +->|   EVALUATED   |
               +---------------+
```

#### Attempt Invariants:
1. **Single Active Attempt Invariant**: A candidate can have at most one attempt per exam (`UNIQUE (exam_id, student_id)`).
2. **Server-Authoritative Deadline Invariant**:
   $$\text{server\_deadline} = \min(\text{started\_at} + \text{duration\_minutes}, \text{end\_window})$$
   The server computes and permanently stores `server_deadline` when the candidate initiates the attempt. The client timer is strictly a display mirror.
3. **Grace Period Invariant**: The server allows a grace window (default: 30 seconds) to absorb high network latency. Any response received where `NOW() > server_deadline + grace_period` is strictly rejected with HTTP `403 FORBIDDEN` (`DEADLINE_EXPIRED`).
4. **Idempotent Submission Invariant**:
   Final submission runs inside an atomic transaction with a pessimistic row lock:
   ```python
   with transaction.atomic():
       attempt = ExaminationAttempt.objects.select_for_update().get(id=attempt_id)
       if attempt.status in [AttemptStatus.SUBMITTED, AttemptStatus.AUTO_SUBMITTED]:
           return Response({"status": "SUCCESS", "message": "Already submitted"}, status=status.HTTP_200_OK)
       attempt.status = AttemptStatus.SUBMITTED
       attempt.submitted_at = timezone.now()
       attempt.save(update_fields=['status', 'submitted_at'])
   ```
   This eliminates duplicate attempt records, double-submission race conditions, and accidental multiple score computations.
