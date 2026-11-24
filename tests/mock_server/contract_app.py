"""
EZExam Observable API Contract Mock Engine & HTTP Transport.
Implements the full observable REST API specifications from research/api_contracts.md
and PROJECT.md § Interface Contracts.
"""

import json
import re
import uuid
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import urllib.parse
import threading
import httpx


def parse_iso_datetime(dt_str: str) -> datetime:
    """Helper to parse ISO-8601 strings across Python 3.9-3.13 without 'Z' ValueError."""
    if not dt_str:
        return datetime.now(timezone.utc)
    cleaned = dt_str.replace("Z", "+00:00")
    return datetime.fromisoformat(cleaned)


class ContractState:
    """Thread-safe in-memory state store for multi-tenant examination engine."""

    def __init__(self):
        self.lock = threading.RLock()
        self.reset()

    def reset(self):
        with getattr(self, "lock", threading.RLock()):
            self.organizations: Dict[str, Dict[str, Any]] = {}
            self.users: Dict[str, Dict[str, Any]] = {}
            self.tokens: Dict[str, Dict[str, Any]] = {}
            self.refresh_tokens: Dict[str, Dict[str, Any]] = {}
            self.batches: Dict[str, Dict[str, Any]] = {}
            self.centers: Dict[str, Dict[str, Any]] = {}
            self.faculty: Dict[str, Dict[str, Any]] = {}
            self.students: Dict[str, Dict[str, Any]] = {}
            self.question_papers: Dict[str, Dict[str, Any]] = {}
            self.questions: Dict[str, Dict[str, Any]] = {}
            self.examinations: Dict[str, Dict[str, Any]] = {}
            self.candidate_assignments: Dict[str, List[str]] = {}
            self.attempts: Dict[str, Dict[str, Any]] = {}
            self.attempt_responses: Dict[str, Dict[str, Any]] = {}
            self.evaluation_results: Dict[str, Dict[str, Any]] = {}
            self.init_default_data()

    def init_default_data(self):
        # Default Org
        org_id = "8b51d113-11ef-42d4-bbbb-f26e382d5a0c"
        self.organizations[org_id] = {
            "id": org_id,
            "name": "Apex Engineering Academy",
            "slug": "ezexamqwertyuiop",
            "domain": "ezexamqwertyuiop.ezexam.in",
            "is_active": True,
            "settings": {
                "theme_primary_color": "#1eaeff",
                "allow_student_signup": False,
                "allow_student_pdf_download": True,
            },
        }

        # Second Org for multi-tenant isolation tests
        org2_id = "9c62e224-22fa-53e5-cccc-037f493e6b1d"
        self.organizations[org2_id] = {
            "id": org2_id,
            "name": "Zenith Medical Institute",
            "slug": "zenithmedical",
            "domain": "zenithmedical.ezexam.in",
            "is_active": True,
            "settings": {},
        }

        # Seed Users
        self._add_user(
            user_id="user-superadmin",
            username="superadmin@ezexam.in",
            password="SuperPassword123!",
            role="SUPERADMIN",
            org_id=None,
            name="Platform SuperAdmin",
        )
        self._add_user(
            user_id="user-orgadmin",
            username="admin@apex.edu",
            password="SecurePassword123!",
            role="ORG_ADMIN",
            org_id=org_id,
            name="Prof. Alan Turing",
        )
        self._add_user(
            user_id="user-faculty",
            username="faculty@apex.edu",
            password="FacultyPassword123!",
            role="FACULTY",
            org_id=org_id,
            name="Dr. Richard Feynman",
        )
        self._add_user(
            user_id="user-student1",
            username="student1@apex.edu",
            password="StudentPassword123!",
            role="STUDENT",
            org_id=org_id,
            name="Aryabhata Sharma",
            roll_number="2026001",
        )
        self._add_user(
            user_id="user-student2",
            username="student2@apex.edu",
            password="StudentPassword123!",
            role="STUDENT",
            org_id=org_id,
            name="Brahmagupta Patel",
            roll_number="2026002",
        )

        # Default batch & center
        batch_id = "11111111-1111-1111-1111-111111111111"
        self.batches[batch_id] = {
            "id": batch_id,
            "organization_id": org_id,
            "name": "Class 12 B",
            "code": "C12B",
            "stream": "JEE_MAIN",
            "is_active": True,
        }

        center_id = "55555555-5555-5555-5555-555555555555"
        self.centers[center_id] = {
            "id": center_id,
            "organization_id": org_id,
            "name": "North Campus Centre",
            "code": "NC01",
            "capacity": 150,
            "is_active": True,
        }

    def _add_user(self, user_id, username, password, role, org_id, name, roll_number=None):
        self.users[username] = {
            "id": user_id,
            "username": username,
            "password": password,
            "role": role,
            "organization_id": org_id,
            "name": name,
            "roll_number": roll_number,
            "is_active": True,
        }


state = ContractState()


class ContractHandler:
    """Synchronous contract router callable directly or via httpx.MockTransport."""

    def __init__(self, state_store: ContractState):
        self.state = state_store

    def __call__(self, request: httpx.Request) -> httpx.Response:
        method = request.method
        path = request.url.path
        headers = request.headers
        query_string = request.url.query.decode("utf-8") if isinstance(request.url.query, bytes) else str(request.url.query)
        query_params = urllib.parse.parse_qs(query_string)

        body_bytes = request.read()
        auth_header = headers.get("authorization")
        tenant_header = headers.get("x-tenant-id")
        content_type = headers.get("content-type", "")

        body_json = {}
        if body_bytes and "application/json" in content_type:
            try:
                body_json = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                body_json = {}

        status_code, resp_headers, resp_body = self.route_request(
            method=method,
            path=path,
            headers=headers,
            auth_header=auth_header,
            tenant_header=tenant_header,
            query_params=query_params,
            body_bytes=body_bytes,
            body_json=body_json,
            content_type=content_type,
        )

        return httpx.Response(
            status_code=status_code,
            headers=resp_headers,
            json=resp_body if isinstance(resp_body, (dict, list)) else None,
            content=resp_body.encode("utf-8") if isinstance(resp_body, str) else (None if isinstance(resp_body, (dict, list)) else resp_body),
        )

    def route_request(
        self, method, path, headers, auth_header, tenant_header, query_params, body_bytes, body_json, content_type
    ):
        with self.state.lock:
            # 1. AUTH ROUTES
            if path == "/api/v1/auth/login/" and method == "POST":
                return self._handle_login(body_json)

            if path == "/api/v1/auth/otp/send/" and method == "POST":
                return self._handle_otp_send(body_json)

            if path == "/api/v1/auth/otp/verify/" and method == "POST":
                return self._handle_otp_verify(body_json)

            if path == "/api/v1/auth/me/" and method == "GET":
                user = self._authenticate(auth_header)
                if not user:
                    return 401, {}, {"status": "ERROR", "code": "UNAUTHORIZED", "message": "Invalid or missing token"}
                return 200, {}, {
                    "status": "SUCCESS",
                    "user": {
                        "id": user["id"],
                        "name": user["name"],
                        "role": user["role"],
                        "permissions": ["manage_orgs", "manage_exams"] if user["role"] in ["SUPERADMIN", "ORG_ADMIN"] else [],
                        "organization_id": user.get("organization_id"),
                    },
                }

            if path == "/api/v1/auth/refresh/" and method == "POST":
                return self._handle_token_refresh(body_json)

            if path == "/api/v1/auth/logout/" and method == "POST":
                return self._handle_logout(body_json)

            # 2. MASTER DATA & ORGS
            if path == "/api/v1/organizations/select-fields/" and method == "GET":
                user = self._authenticate(auth_header)
                if not user:
                    return 401, {}, {"status": "ERROR", "code": "UNAUTHORIZED"}
                org_id = user.get("organization_id")
                classes = [b for b in self.state.batches.values() if b["organization_id"] == org_id]
                centres = [c for c in self.state.centers.values() if c["organization_id"] == org_id]
                return 200, {}, {
                    "status": "SUCCESS",
                    "classes": classes,
                    "groups": [{"id": "grp-1", "name": "JEE-Main", "code": "JEE"}],
                    "centres": centres,
                }

            if path in ["/api/v1/organizations/batches/", "/api/v1/organizations/batches"] or re.match(r"^/api/v1/organizations/[^/]+/batches/?$", path):
                user = self._authenticate(auth_header)
                if not user:
                    return 401, {}, {"status": "ERROR", "code": "UNAUTHORIZED"}
                if user["role"] not in ["SUPERADMIN", "ORG_ADMIN"]:
                    return 403, {}, {"status": "ERROR", "code": "FORBIDDEN"}
                org_id = user.get("organization_id")
                if method == "GET":
                    batches = [b for b in self.state.batches.values() if b["organization_id"] == org_id]
                    return 200, {}, {"status": "SUCCESS", "batches": batches, "count": len(batches)}
                elif method == "POST":
                    if not body_json.get("name") or not body_json.get("code"):
                        return 400, {}, {"status": "ERROR", "code": "VALIDATION_FAILED", "message": "Name and code required"}
                    # Duplicate code check
                    for b in self.state.batches.values():
                        if b["organization_id"] == org_id and b["code"] == body_json["code"]:
                            return 409, {}, {"status": "ERROR", "code": "DUPLICATE_CODE", "message": "Batch code already exists"}
                    bid = str(uuid.uuid4())
                    new_batch = {
                        "id": bid,
                        "organization_id": org_id,
                        "name": body_json["name"],
                        "code": body_json["code"],
                        "stream": body_json.get("stream", "JEE_MAIN"),
                        "is_active": body_json.get("is_active", True),
                    }
                    self.state.batches[bid] = new_batch
                    return 201, {}, {"status": "SUCCESS", "id": bid, "message": "Batch created successfully"}

            if path in ["/api/v1/organizations/centers/", "/api/v1/organizations/centers"] or re.match(r"^/api/v1/organizations/[^/]+/centers/?$", path):
                user = self._authenticate(auth_header)
                if not user:
                    return 401, {}, {"status": "ERROR", "code": "UNAUTHORIZED"}
                if user["role"] not in ["SUPERADMIN", "ORG_ADMIN"]:
                    return 403, {}, {"status": "ERROR", "code": "FORBIDDEN"}
                org_id = user.get("organization_id")
                if method == "GET":
                    centers = [c for c in self.state.centers.values() if c["organization_id"] == org_id]
                    return 200, {}, {"status": "SUCCESS", "centers": centers, "count": len(centers)}
                elif method == "POST":
                    capacity = body_json.get("capacity", 0)
                    if capacity <= 0:
                        return 400, {}, {"status": "ERROR", "code": "INVALID_CAPACITY", "message": "Center capacity must be greater than zero"}
                    cid = str(uuid.uuid4())
                    new_center = {
                        "id": cid,
                        "organization_id": org_id,
                        "name": body_json.get("name", "Center"),
                        "code": body_json.get("code", f"C-{cid[:4]}"),
                        "capacity": capacity,
                        "is_active": body_json.get("is_active", True),
                    }
                    self.state.centers[cid] = new_center
                    return 201, {}, {"status": "SUCCESS", "id": cid, "message": "Center created"}

            if path == "/api/v1/organizations/settings/" and method == "PATCH":
                user = self._authenticate(auth_header)
                if not user or user["role"] not in ["SUPERADMIN", "ORG_ADMIN"]:
                    return 403, {}, {"status": "ERROR", "code": "FORBIDDEN"}
                org_id = user.get("organization_id")
                if org_id in self.state.organizations:
                    self.state.organizations[org_id]["settings"].update(body_json)
                    return 200, {}, {"status": "SUCCESS", "settings": self.state.organizations[org_id]["settings"]}
                return 404, {}, {"status": "ERROR", "code": "NOT_FOUND"}

            # 3. FACULTY & STUDENTS
            if path == "/api/v1/users/faculty/":
                user = self._authenticate(auth_header)
                if not user or user["role"] not in ["SUPERADMIN", "ORG_ADMIN"]:
                    return 403, {}, {"status": "ERROR", "code": "FORBIDDEN"}
                if method == "GET":
                    fac_list = list(self.state.faculty.values())
                    return 200, {}, {"status": "SUCCESS", "faculties": fac_list}
                elif method == "POST":
                    fid = str(uuid.uuid4())
                    fac = {
                        "id": fid,
                        "name": body_json.get("name"),
                        "email": body_json.get("email"),
                        "subjects": body_json.get("subject_ids", []),
                        "is_active": body_json.get("is_active", True),
                    }
                    self.state.faculty[fid] = fac
                    return 201, {}, {"status": "SUCCESS", "id": fid}

            if path == "/api/v1/users/students/":
                user = self._authenticate(auth_header)
                if not user:
                    return 401, {}, {"status": "ERROR", "code": "UNAUTHORIZED"}
                if method == "GET":
                    page = int(query_params.get("page", ["1"])[0])
                    page_size = int(query_params.get("page_size", ["25"])[0])
                    if page_size <= 0:
                        return 400, {}, {"status": "ERROR", "code": "INVALID_PAGE_SIZE", "message": "Page size must be positive"}
                    students = list(self.state.students.values())
                    total = len(students)
                    start = (page - 1) * page_size
                    end = start + page_size
                    paginated = students[start:end] if start < total else []
                    return 200, {}, {
                        "status": "SUCCESS",
                        "count": total,
                        "current_page": page,
                        "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
                        "students": paginated,
                    }
                elif method == "POST":
                    roll = body_json.get("roll_number")
                    if not roll:
                        return 400, {}, {"status": "ERROR", "code": "VALIDATION_FAILED", "message": "Roll number is required"}
                    for s in self.state.students.values():
                        if s.get("roll_number") == roll:
                            return 409, {}, {"status": "ERROR", "code": "DUPLICATE_ROLL", "message": "Student roll number already exists"}
                    sid = str(uuid.uuid4())
                    student = {
                        "id": sid,
                        "roll_number": roll,
                        "name": body_json.get("name", "Student"),
                        "email": body_json.get("email"),
                        "batch_id": body_json.get("batch_id"),
                        "centre_id": body_json.get("centre_id"),
                        "is_active": True,
                    }
                    self.state.students[sid] = student
                    return 201, {}, {"status": "SUCCESS", "id": sid, "student": student}

            if path in ["/api/v1/users/students/bulk-upload/", "/api/v1/organizations/students/bulk-import/"] or re.match(r"^/api/v1/organizations/[^/]+/students/bulk-import/?$", path):
                user = self._authenticate(auth_header)
                if not user or user["role"] not in ["SUPERADMIN", "ORG_ADMIN"]:
                    return 403, {}, {"status": "ERROR", "code": "FORBIDDEN"}
                return self._handle_bulk_upload(body_bytes, body_json, content_type)

            # 4. QUESTION PAPERS & QUESTIONS
            if path in ["/api/v1/question-papers/", "/api/v1/question-papers"]:
                user = self._authenticate(auth_header)
                if not user:
                    return 401, {}, {"status": "ERROR", "code": "UNAUTHORIZED"}
                if method == "GET":
                    qps = list(self.state.question_papers.values())
                    return 200, {}, {"status": "SUCCESS", "question_papers": qps}
                elif method == "POST":
                    qpid = f"qpap-{uuid.uuid4().hex[:6]}"
                    qp = {
                        "id": qpid,
                        "name": body_json.get("name", "Untitled Paper"),
                        "exam_type": body_json.get("exam_type", "IIT-JEE"),
                        "duration_minutes": body_json.get("duration_minutes", 60),
                        "status": "DRAFT",
                        "questions": [],
                    }
                    self.state.question_papers[qpid] = qp
                    return 201, {}, {"status": "SUCCESS", "id": qpid, "message": "Question paper initialized."}

            # Question Paper Questions
            match_qp_q = re.match(r"^/api/v1/question-papers/([^/]+)/questions/?$", path)
            if match_qp_q:
                qpid = match_qp_q.group(1)
                user = self._authenticate(auth_header)
                if not user:
                    return 401, {}, {"status": "ERROR", "code": "UNAUTHORIZED"}
                if qpid not in self.state.question_papers:
                    return 404, {}, {"status": "ERROR", "code": "NOT_FOUND"}
                qp = self.state.question_papers[qpid]
                if method == "GET":
                    return 200, {}, {
                        "status": "SUCCESS",
                        "metadata": {
                            "id": qpid,
                            "name": qp["name"],
                            "duration_minutes": qp["duration_minutes"],
                            "total_questions": len(qp["questions"]),
                        },
                        "questions": qp["questions"],
                    }
                elif method == "POST":
                    if qp.get("status") == "PUBLISHED":
                        return 403, {}, {"status": "ERROR", "code": "LOCKED", "message": "Cannot modify questions in a published paper"}
                    # Validate question fields
                    qtype = body_json.get("question_type")
                    if qtype not in ["MCQ_SINGLE", "MCQ_MULTI", "NUMERICAL"]:
                        return 400, {}, {"status": "ERROR", "code": "INVALID_QUESTION_TYPE", "message": f"Unsupported question type: {qtype}"}
                    pos_marks = float(body_json.get("positive_marks", 4.0))
                    neg_marks = float(body_json.get("negative_marks", 0.0))
                    if abs(neg_marks) > pos_marks:
                        return 400, {}, {"status": "ERROR", "code": "INVALID_MARKING", "message": "Negative penalty cannot exceed total positive marks"}
                    if qtype in ["MCQ_SINGLE", "MCQ_MULTI"] and not body_json.get("options"):
                        return 400, {}, {"status": "ERROR", "code": "MISSING_OPTIONS", "message": "MCQs require option choices"}
                    if qtype == "NUMERICAL":
                        try:
                            float(body_json.get("key"))
                        except (TypeError, ValueError):
                            return 400, {}, {"status": "ERROR", "code": "INVALID_KEY", "message": "Numerical answer key must be a valid number"}
                    qid = int(body_json.get("id", len(self.state.questions) + 1000))
                    question_data = {
                        "id": qid,
                        "question_number": len(qp["questions"]) + 1,
                        "section": body_json.get("section", "General"),
                        "question_type": qtype,
                        "key": body_json.get("key"),
                        "positive_marks": pos_marks,
                        "negative_marks": neg_marks,
                        "partial_marks": float(body_json.get("partial_marks", 0.0)),
                        "content_text": body_json.get("content_text", ""),
                        "options": body_json.get("options", []),
                        "explanation": body_json.get("explanation", ""),
                    }
                    self.state.questions[str(qid)] = question_data
                    qp["questions"].append(question_data)
                    return 201, {}, {"status": "SUCCESS", "id": qid, "message": "Question added to paper"}

            # Direct Question creation endpoint
            if path in ["/api/v1/questions/", "/api/v1/questions"] and method == "POST":
                user = self._authenticate(auth_header)
                if not user:
                    return 401, {}, {"status": "ERROR", "code": "UNAUTHORIZED"}
                qid = len(self.state.questions) + 1001
                body_json["id"] = qid
                self.state.questions[str(qid)] = body_json
                return 201, {}, {"status": "SUCCESS", "id": qid}

            # 5. EXAMINATIONS
            if path in ["/api/v1/examinations/", "/api/v1/examinations"]:
                user = self._authenticate(auth_header)
                if not user:
                    return 401, {}, {"status": "ERROR", "code": "UNAUTHORIZED"}
                if method == "GET":
                    exs = list(self.state.examinations.values())
                    return 200, {}, {"status": "SUCCESS", "examinations": exs}
                elif method == "POST":
                    dur = body_json.get("duration_minutes", 60)
                    if dur <= 0:
                        return 400, {}, {"status": "ERROR", "code": "INVALID_DURATION", "message": "Exam duration must be greater than zero"}
                    if dur > 1440:
                        return 400, {}, {"status": "ERROR", "code": "DURATION_OVERFLOW", "message": "Exam duration cannot exceed 24 hours"}
                    start_w = body_json.get("start_window")
                    end_w = body_json.get("end_window")
                    if start_w and end_w and start_w >= end_w:
                        return 400, {}, {"status": "ERROR", "code": "INVALID_WINDOW", "message": "Start window must be before end window"}
                    eid = f"exam-{uuid.uuid4().hex[:6]}"
                    exam = {
                        "id": eid,
                        "name": body_json.get("name", "Mock Exam"),
                        "question_paper_id": body_json.get("question_paper_id"),
                        "duration_minutes": dur,
                        "start_window": start_w or "2026-01-01T00:00:00Z",
                        "end_window": end_w or "2026-12-31T23:59:59Z",
                        "status": "DRAFT",
                        "max_window_switches": body_json.get("max_window_switches", 3),
                        "allow_section_skip": body_json.get("allow_section_skip", True),
                        "assigned_batches": body_json.get("batch_ids", []),
                        "assigned_candidates": [],
                    }
                    self.state.examinations[eid] = exam
                    return 201, {}, {"status": "SUCCESS", "id": eid, "message": "Examination created."}

            match_assign = re.match(r"^/api/v1/examinations/([^/]+)/assign-candidates/?$", path)
            if match_assign and method == "POST":
                eid = match_assign.group(1)
                user = self._authenticate(auth_header)
                if not user or user["role"] not in ["SUPERADMIN", "ORG_ADMIN", "FACULTY"]:
                    return 403, {}, {"status": "ERROR", "code": "FORBIDDEN"}
                if eid not in self.state.examinations:
                    return 404, {}, {"status": "ERROR", "code": "NOT_FOUND"}
                cand_ids = body_json.get("student_ids", [])
                if body_json.get("select_all_matching_batches"):
                    for s in self.state.students.values():
                        if s.get("batch_id") in body_json.get("batch_ids", []):
                            cand_ids.append(s["id"])
                cand_ids = list(set(cand_ids))
                self.state.examinations[eid]["assigned_candidates"].extend(cand_ids)
                self.state.candidate_assignments[eid] = list(set(self.state.examinations[eid]["assigned_candidates"]))
                return 200, {}, {"status": "SUCCESS", "assigned_count": len(cand_ids)}

            match_pub = re.match(r"^/api/v1/examinations/([^/]+)/publish/?$", path)
            if match_pub and method == "POST":
                eid = match_pub.group(1)
                user = self._authenticate(auth_header)
                if not user or user["role"] not in ["SUPERADMIN", "ORG_ADMIN"]:
                    return 403, {}, {"status": "ERROR", "code": "FORBIDDEN"}
                if eid not in self.state.examinations:
                    return 404, {}, {"status": "ERROR", "code": "NOT_FOUND"}
                exam = self.state.examinations[eid]
                qpid = exam.get("question_paper_id")
                qp = self.state.question_papers.get(qpid, {})
                if not qp.get("questions"):
                    return 400, {}, {"status": "ERROR", "code": "EMPTY_EXAM", "message": "Cannot publish exam with no questions"}
                exam["status"] = "PUBLISHED"
                qp["status"] = "PUBLISHED"
                return 200, {}, {"status": "SUCCESS", "id": eid, "status": "PUBLISHED", "message": "Exam successfully published."}

            # 6. STUDENT ENGINE (Lobby, Start, Responses, Heartbeat, Submit)
            match_lobby = re.match(r"^/api/v1/student/lobby/([^/]+)/?$", path)
            if match_lobby and method == "GET":
                user = self._authenticate(auth_header)
                if not user:
                    return 401, {}, {"status": "ERROR", "code": "UNAUTHORIZED"}
                eid = match_lobby.group(1)
                exam = self.state.examinations.get(eid)
                if not exam:
                    return 404, {}, {"status": "ERROR", "code": "NOT_FOUND"}
                return 200, {}, {
                    "status": "SUCCESS",
                    "can_start": exam["status"] == "PUBLISHED",
                    "exam": {
                        "id": exam["id"],
                        "title": exam["name"],
                        "duration_minutes": exam["duration_minutes"],
                        "start_window": exam["start_window"],
                        "end_window": exam["end_window"],
                        "max_window_switches": exam["max_window_switches"],
                    },
                    "candidate": {"name": user["name"], "roll_number": user.get("roll_number")},
                }

            if path in ["/api/v1/student/attempts/start/", "/api/v1/examinations/start/"] or re.match(r"^/api/v1/examinations/([^/]+)/start/?$", path):
                user = self._authenticate(auth_header)
                if not user:
                    return 401, {}, {"status": "ERROR", "code": "UNAUTHORIZED"}
                eid = body_json.get("exam_id")
                if not eid:
                    m = re.match(r"^/api/v1/examinations/([^/]+)/start/?$", path)
                    if m:
                        eid = m.group(1)
                if not eid or eid not in self.state.examinations:
                    return 404, {}, {"status": "ERROR", "code": "EXAM_NOT_FOUND"}
                exam = self.state.examinations[eid]
                now_iso = datetime.now(timezone.utc).isoformat()
                # Window checks
                if exam.get("start_window") and now_iso < exam["start_window"]:
                    return 403, {}, {"status": "ERROR", "code": "EXAM_NOT_STARTED", "message": "Examination has not started yet"}
                if exam.get("end_window") and now_iso > exam["end_window"]:
                    return 403, {}, {"status": "ERROR", "code": "EXAM_EXPIRED", "message": "Examination window has passed"}

                # Check existing attempt for candidate
                cand_id = user["id"]
                existing_att = None
                for a in self.state.attempts.values():
                    if a["exam_id"] == eid and a["candidate_id"] == cand_id:
                        existing_att = a
                        break

                if existing_att:
                    if existing_att["status"] == "SUBMITTED":
                        return 409, {}, {"status": "ERROR", "code": "ALREADY_SUBMITTED", "message": "Attempt already completed"}
                    # Return recovered session
                    deadline_dt = parse_iso_datetime(existing_att["server_deadline"])
                    rem = max(0, int((deadline_dt - datetime.now(timezone.utc)).total_seconds()))
                    resps = self.state.attempt_responses.get(existing_att["attempt_id"], {})
                    return 200, {}, {
                        "status": "SUCCESS",
                        "attempt_id": existing_att["attempt_id"],
                        "attempt_token": existing_att["attempt_token"],
                        "remaining_seconds": rem,
                        "server_deadline": existing_att["server_deadline"],
                        "existing_responses": resps,
                        "sections": existing_att["sections"],
                        "is_recovered": True,
                    }

                # Create fresh attempt
                att_id = f"att-{uuid.uuid4().hex[:8]}"
                token = str(uuid.uuid4())
                dur_secs = exam["duration_minutes"] * 60
                now_dt = datetime.now(timezone.utc)
                deadline_dt = now_dt + timedelta(seconds=dur_secs)
                qpid = exam.get("question_paper_id")
                qp = self.state.question_papers.get(qpid, {"questions": []})
                sections_dict = {}
                for q in qp["questions"]:
                    sec = q.get("section", "General")
                    if sec not in sections_dict:
                        sections_dict[sec] = []
                    sections_dict[sec].append(q["id"])
                sections_payload = [
                    {"id": f"sec-{i+1}", "name": sname, "order": i+1, "question_ids": qids}
                    for i, (sname, qids) in enumerate(sections_dict.items())
                ] or [{"id": "sec-1", "name": "General", "order": 1, "question_ids": []}]

                attempt_record = {
                    "attempt_id": att_id,
                    "attempt_token": token,
                    "exam_id": eid,
                    "candidate_id": cand_id,
                    "started_at": now_dt.isoformat(),
                    "server_deadline": deadline_dt.isoformat(),
                    "status": "IN_PROGRESS",
                    "sections": sections_payload,
                    "window_blur_count": 0,
                    "max_window_switches": exam.get("max_window_switches", 3),
                    "allow_section_skip": exam.get("allow_section_skip", True),
                }
                self.state.attempts[att_id] = attempt_record
                self.state.attempt_responses[att_id] = {}

                return 200, {}, {
                    "status": "SUCCESS",
                    "attempt_id": att_id,
                    "attempt_token": token,
                    "started_at": attempt_record["started_at"],
                    "server_deadline": attempt_record["server_deadline"],
                    "remaining_seconds": dur_secs,
                    "sections": sections_payload,
                    "existing_responses": {},
                }

            # Response Autosave
            match_resp = re.match(r"^/api/v1/student/attempts/([^/]+)/responses/?$", path) or re.match(r"^/api/v1/attempts/([^/]+)/save_response/?$", path)
            if match_resp and method == "POST":
                att_id = match_resp.group(1)
                user = self._authenticate(auth_header)
                if not user:
                    return 401, {}, {"status": "ERROR", "code": "UNAUTHORIZED"}
                if att_id not in self.state.attempts:
                    return 404, {}, {"status": "ERROR", "code": "ATTEMPT_NOT_FOUND"}
                att = self.state.attempts[att_id]
                if att["status"] == "SUBMITTED":
                    return 403, {}, {"status": "ERROR", "code": "ATTEMPT_LOCKED", "message": "Attempt already submitted"}

                deadline_dt = parse_iso_datetime(att["server_deadline"])
                now_dt = datetime.now(timezone.utc)
                # Deadline enforcement with 15 second grace period
                if now_dt > deadline_dt + timedelta(seconds=15):
                    return 403, {}, {"status": "ERROR", "code": "DEADLINE_EXPIRED", "message": "Server deadline has expired"}

                raw_qid = body_json.get("question_id")
                if raw_qid is None or raw_qid == "":
                    return 400, {}, {"status": "ERROR", "code": "MISSING_QUESTION_ID"}
                qid = str(raw_qid)

                rem_secs = max(0, int((deadline_dt - now_dt).total_seconds()))
                resp_entry = {
                    "question_id": int(qid) if qid.isdigit() else qid,
                    "selected_options": body_json.get("selected_options", []),
                    "numerical_value": body_json.get("numerical_value"),
                    "status": body_json.get("status", "ANSWERED"),
                    "time_spent_seconds": body_json.get("time_spent_seconds", 0),
                    "saved_at": now_dt.isoformat(),
                }
                self.state.attempt_responses[att_id][qid] = resp_entry
                return 200, {}, {
                    "status": "SUCCESS",
                    "saved_at": resp_entry["saved_at"],
                    "question_id": resp_entry["question_id"],
                    "remaining_seconds": rem_secs,
                }

            # Heartbeat
            match_hb = re.match(r"^/api/v1/student/attempts/([^/]+)/heartbeat/?$", path) or re.match(r"^/api/v1/attempts/([^/]+)/heartbeat/?$", path)
            if match_hb and method == "POST":
                att_id = match_hb.group(1)
                user = self._authenticate(auth_header)
                if not user:
                    return 401, {}, {"status": "ERROR", "code": "UNAUTHORIZED"}
                if att_id not in self.state.attempts:
                    return 404, {}, {"status": "ERROR", "code": "ATTEMPT_NOT_FOUND"}
                att = self.state.attempts[att_id]
                deadline_dt = parse_iso_datetime(att["server_deadline"])
                now_dt = datetime.now(timezone.utc)
                rem_secs = max(0, int((deadline_dt - now_dt).total_seconds()))
                blur_count = body_json.get("window_blur_count", 0)
                if blur_count < 0:
                    return 400, {}, {"status": "ERROR", "code": "INVALID_METRIC", "message": "Blur count cannot be negative"}
                att["window_blur_count"] = max(att["window_blur_count"], blur_count)
                auto_term = False
                if att["window_blur_count"] > att["max_window_switches"]:
                    auto_term = True
                return 200, {}, {
                    "status": "SUCCESS",
                    "server_time": now_dt.isoformat(),
                    "server_deadline": att["server_deadline"],
                    "remaining_seconds": rem_secs,
                    "is_terminated": auto_term or att["status"] == "SUBMITTED",
                }

            # Final Submit (Idempotent)
            match_sub = re.match(r"^/api/v1/student/attempts/([^/]+)/submit/?$", path) or re.match(r"^/api/v1/attempts/([^/]+)/submit/?$", path)
            if match_sub and method == "POST":
                att_id = match_sub.group(1)
                user = self._authenticate(auth_header)
                if not user:
                    return 401, {}, {"status": "ERROR", "code": "UNAUTHORIZED"}
                if att_id not in self.state.attempts:
                    return 404, {}, {"status": "ERROR", "code": "ATTEMPT_NOT_FOUND"}
                att = self.state.attempts[att_id]
                now_dt = datetime.now(timezone.utc)

                # Check if already submitted (idempotent lock)
                if att["status"] == "SUBMITTED":
                    return 200, {}, {
                        "status": "SUCCESS",
                        "code": "ALREADY_SUBMITTED",
                        "attempt_id": att_id,
                        "submission_status": "SUBMITTED",
                        "submitted_at": att.get("submitted_at"),
                        "message": "Attempt was already recorded as submitted.",
                    }

                # Strict late check
                deadline_dt = parse_iso_datetime(att["server_deadline"])
                if now_dt > deadline_dt + timedelta(seconds=15) and body_json.get("submission_reason") != "AUTO_TIMER_EXPIRY":
                    return 403, {}, {"status": "ERROR", "code": "DEADLINE_EXPIRED", "message": "Submission rejected: deadline expired"}

                att["status"] = "SUBMITTED"
                att["submitted_at"] = now_dt.isoformat()
                att["submission_reason"] = body_json.get("submission_reason", "MANUAL_SUBMIT")
                return 200, {}, {
                    "status": "SUCCESS",
                    "attempt_id": att_id,
                    "submission_status": "SUBMITTED",
                    "submitted_at": att["submitted_at"],
                    "message": "Examination submitted successfully.",
                }

            # 7. EVALUATION & RANKINGS
            match_eval = re.match(r"^/api/v1/examinations/([^/]+)/evaluate/?$", path)
            if match_eval and method == "POST":
                eid = match_eval.group(1)
                user = self._authenticate(auth_header)
                if not user or user["role"] not in ["SUPERADMIN", "ORG_ADMIN", "FACULTY"]:
                    return 403, {}, {"status": "ERROR", "code": "FORBIDDEN"}
                return self._evaluate_exam(eid)

            match_res = re.match(r"^/api/v1/examinations/([^/]+)/results/?$", path)
            if match_res and method == "GET":
                eid = match_res.group(1)
                user = self._authenticate(auth_header)
                if not user:
                    return 401, {}, {"status": "ERROR", "code": "UNAUTHORIZED"}
                if eid not in self.state.evaluation_results:
                    # Run auto evaluation if not run yet
                    self._evaluate_exam(eid)
                res = self.state.evaluation_results.get(eid, {})
                return 200, {}, {"status": "SUCCESS", "results": res}

            match_rep = re.match(r"^/api/v1/attempts/([^/]+)/report/?$", path)
            if match_rep and method == "GET":
                att_id = match_rep.group(1)
                user = self._authenticate(auth_header)
                if not user:
                    return 401, {}, {"status": "ERROR", "code": "UNAUTHORIZED"}
                if att_id not in self.state.attempts:
                    return 404, {}, {"status": "ERROR", "code": "NOT_FOUND"}
                att = self.state.attempts[att_id]
                eid = att["exam_id"]
                if eid not in self.state.evaluation_results:
                    self._evaluate_exam(eid)
                ranks = self.state.evaluation_results.get(eid, {}).get("rankings", [])
                user_res = next((r for r in ranks if r["attempt_id"] == att_id), None)
                if not user_res:
                    return 404, {}, {"status": "ERROR", "code": "REPORT_NOT_READY"}
                return 200, {}, {"status": "SUCCESS", "report": user_res}

            return 404, {}, {"status": "ERROR", "code": "ENDPOINT_NOT_FOUND", "path": path}

    def _handle_login(self, body_json):
        username = body_json.get("username")
        password = body_json.get("password")
        if not username or not password:
            return 400, {}, {"status": "ERROR", "code": "MISSING_CREDENTIALS", "message": "Username and password required"}

        user = self.state.users.get(username)
        if not user or user["password"] != password:
            return 401, {}, {"status": "ERROR", "code": "INVALID_CREDENTIALS", "message": "Invalid username or password provided."}

        access_token = f"jwt-access-{uuid.uuid4().hex}"
        refresh_token = f"jwt-refresh-{uuid.uuid4().hex}"
        self.state.tokens[access_token] = user
        self.state.refresh_tokens[refresh_token] = user

        org = self.state.organizations.get(user.get("organization_id"), {})
        return 200, {}, {
            "status": "SUCCESS",
            "access": access_token,
            "refresh": refresh_token,
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["username"],
                "role": user["role"],
                "is_active": user["is_active"],
            },
            "organization": org,
        }

    def _handle_token_refresh(self, body_json):
        ref = body_json.get("refresh")
        if not ref or ref not in self.state.refresh_tokens:
            return 401, {}, {"status": "ERROR", "code": "INVALID_REFRESH_TOKEN", "message": "Refresh token expired or invalid"}
        user = self.state.refresh_tokens[ref]
        new_access = f"jwt-access-{uuid.uuid4().hex}"
        self.state.tokens[new_access] = user
        return 200, {}, {"status": "SUCCESS", "access": new_access}

    def _handle_logout(self, body_json):
        ref = body_json.get("refresh")
        if ref and ref in self.state.refresh_tokens:
            del self.state.refresh_tokens[ref]
        return 200, {}, {"status": "SUCCESS", "message": "Logged out successfully"}

    def _handle_otp_send(self, body_json):
        phone = body_json.get("phone")
        if not phone or len(phone) < 10:
            return 400, {}, {"status": "ERROR", "code": "INVALID_PHONE", "message": "Valid 10-digit phone number required"}
        return 200, {}, {"status": "SUCCESS", "message": "6-digit verification code dispatched to registered mobile."}

    def _handle_otp_verify(self, body_json):
        otp = body_json.get("otp")
        p1 = body_json.get("password1")
        p2 = body_json.get("password2")
        if not otp or otp != "482910":
            return 400, {}, {"status": "ERROR", "code": "INVALID_OTP", "message": "Verification code is incorrect"}
        if not p1 or p1 != p2:
            return 400, {}, {"status": "ERROR", "code": "PASSWORD_MISMATCH", "message": "Passwords do not match"}
        return 200, {}, {"status": "SUCCESS", "message": "Password updated successfully. You may now log in."}

    def _handle_bulk_upload(self, body_bytes, body_json, content_type):
        raw_text = body_bytes.decode("utf-8", errors="ignore")
        if not raw_text.strip():
            return 400, {}, {"status": "ERROR", "code": "EMPTY_FILE", "message": "Uploaded file is empty"}
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        if not lines:
            return 400, {}, {"status": "ERROR", "code": "EMPTY_CSV"}
        header = lines[0].split(",")
        required_headers = ["RollNumber", "Name"]
        for rh in required_headers:
            if not any(rh.lower() in h.lower() for h in header):
                return 400, {}, {"status": "ERROR", "code": "MALFORMED_HEADER", "message": f"Missing required column: {rh}"}

        created = 0
        updated = 0
        errors = []
        for line_no, line in enumerate(lines[1:], start=2):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2:
                errors.append(f"Line {line_no}: Incomplete data")
                continue
            roll = parts[0]
            name = parts[1]
            email = parts[3] if len(parts) > 3 else f"{roll}@student.org"
            sid = str(uuid.uuid4())
            self.state.students[sid] = {
                "id": sid,
                "roll_number": roll,
                "name": name,
                "email": email,
                "is_active": True,
            }
            created += 1

        return 200, {}, {
            "status": "SUCCESS",
            "total_processed": len(lines) - 1,
            "created_count": created,
            "updated_count": updated,
            "errors": errors,
        }

    def _authenticate(self, auth_header):
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        token = auth_header[7:].strip()
        return self.state.tokens.get(token)

    def _evaluate_exam(self, eid):
        exam = self.state.examinations.get(eid)
        if not exam:
            return 404, {}, {"status": "ERROR", "code": "EXAM_NOT_FOUND"}
        qpid = exam.get("question_paper_id")
        qp = self.state.question_papers.get(qpid, {"questions": []})

        attempts = [a for a in self.state.attempts.values() if a["exam_id"] == eid and a["status"] == "SUBMITTED"]
        cohort_results = []

        for att in attempts:
            att_id = att["attempt_id"]
            resps = self.state.attempt_responses.get(att_id, {})
            total_score = 0.0
            total_correct = 0
            total_incorrect = 0
            section_breakdown = {}
            question_reviews = []

            for q in qp["questions"]:
                qid = q["id"]
                sec = q.get("section", "General")
                if sec not in section_breakdown:
                    section_breakdown[sec] = {"score": 0.0, "correct": 0, "incorrect": 0}

                q_score = 0.0
                is_correct = False
                is_attempted = False
                user_resp = resps.get(str(qid)) or resps.get(qid)

                pos = float(q.get("positive_marks", 4.0))
                neg = float(q.get("negative_marks", 0.0))
                partial = float(q.get("partial_marks", 0.0))
                is_cancelled = q.get("is_cancelled", False)

                if is_cancelled:
                    q_score = pos
                    is_correct = True
                elif user_resp:
                    is_attempted = True
                    qtype = q.get("question_type")
                    correct_key = q.get("key")

                    if qtype == "MCQ_SINGLE":
                        sel = user_resp.get("selected_options", [])
                        user_ans = sel[0] if sel else None
                        if user_ans == correct_key:
                            q_score = pos
                            is_correct = True
                        elif user_ans is not None:
                            q_score = -abs(neg)
                            total_incorrect += 1
                    elif qtype == "MCQ_MULTI":
                        sel = set(user_resp.get("selected_options", []))
                        corr_set = set([k.strip() for k in str(correct_key).split(",")])
                        if sel == corr_set:
                            q_score = pos
                            is_correct = True
                        elif sel.issubset(corr_set) and len(sel) > 0:
                            q_score = partial * len(sel)
                        elif len(sel) > 0:
                            q_score = -abs(neg)
                            total_incorrect += 1
                    elif qtype == "NUMERICAL":
                        val_str = user_resp.get("numerical_value")
                        if val_str is not None:
                            try:
                                u_val = float(val_str)
                                k_val = float(correct_key)
                                if abs(u_val - k_val) <= 0.01:
                                    q_score = pos
                                    is_correct = True
                                else:
                                    q_score = -abs(neg)
                                    total_incorrect += 1
                            except ValueError:
                                q_score = -abs(neg)
                                total_incorrect += 1

                if is_correct:
                    total_correct += 1
                total_score += q_score
                section_breakdown[sec]["score"] += q_score
                if is_correct:
                    section_breakdown[sec]["correct"] += 1

                question_reviews.append({
                    "question_id": qid,
                    "section": sec,
                    "marks_awarded": q_score,
                    "is_correct": is_correct,
                    "is_attempted": is_attempted,
                    "explanation": q.get("explanation", ""),
                })

            cohort_results.append({
                "attempt_id": att_id,
                "candidate_id": att["candidate_id"],
                "total_score": round(total_score, 2),
                "total_correct": total_correct,
                "total_incorrect": total_incorrect,
                "section_scores": section_breakdown,
                "question_reviews": question_reviews,
            })

        cohort_results.sort(key=lambda x: (x["total_score"], -x["total_incorrect"]), reverse=True)
        total_candidates = len(cohort_results)

        for rank_idx, cand_res in enumerate(cohort_results, start=1):
            cand_res["rank"] = rank_idx
            score = cand_res["total_score"]
            le_count = sum(1 for c in cohort_results if c["total_score"] <= score)
            percentile = round((le_count / total_candidates) * 100.0, 2) if total_candidates > 0 else 100.0
            cand_res["percentile"] = percentile

        eval_summary = {
            "exam_id": eid,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "total_candidates": total_candidates,
            "highest_score": cohort_results[0]["total_score"] if cohort_results else 0.0,
            "lowest_score": cohort_results[-1]["total_score"] if cohort_results else 0.0,
            "average_score": round(sum(c["total_score"] for c in cohort_results) / total_candidates, 2) if total_candidates else 0.0,
            "rankings": cohort_results,
        }
        self.state.evaluation_results[eid] = eval_summary
        return 200, {}, {"status": "SUCCESS", "message": "Evaluation completed.", "summary": eval_summary}
