import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from asgiref.sync import async_to_sync
from django.core.handlers.asgi import ASGIHandler
from django.db import IntegrityError, connection, connections, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.organizations.models import Organization, Batch
from apps.accounts.models import User, UserRole, UserProfile
from apps.question_bank.models import QuestionBank, Question, Option, QuestionType
from apps.examinations.models import Examination, ExaminationStatus, ExaminationSection, ExaminationQuestion
from apps.engine.models import ExaminationAttempt, AttemptResponse, ProctoringLog, AttemptStatus, ResponseStatus


class EngineComprehensiveTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(
            name="Apex Institute of Technology",
            slug="apex-tech",
            domain="apex-tech.ezexam.in",
        )
        self.student_user = User.objects.create_user(
            username="student1@apex.edu",
            email="student1@apex.edu",
            password="StudentPassword123!",
            role=UserRole.STUDENT,
            organization=self.org,
        )
        UserProfile.objects.create(user=self.student_user, full_name="Candidate Student 1")
        self.client.force_authenticate(user=self.student_user)
        self.tenant_headers = {"HTTP_X_TENANT_ID": str(self.org.id)}

        # Setup Question Bank
        self.paper = QuestionBank.objects.create(
            organization=self.org,
            name="Joint Entrance Mock Exam",
            duration_minutes=60,
        )

        # Questions
        # Q1: Maths MCQ Single
        self.q1 = Question.objects.create(
            question_bank=self.paper,
            section_name="Maths",
            question_number=1,
            question_type=QuestionType.MCQ_SINGLE,
            content_text="Solve $\\det(2A)$",
            key="C",
            explanation="Secret solution explanation: 2^n * det(A) = 128",
            positive_marks=3.0,
            negative_marks=1.0,
        )
        Option.objects.create(question=self.q1, option_key="A", content_text="32", is_correct=False, order=1)
        Option.objects.create(question=self.q1, option_key="B", content_text="64", is_correct=False, order=2)
        Option.objects.create(question=self.q1, option_key="C", content_text="128", is_correct=True, order=3)
        Option.objects.create(question=self.q1, option_key="D", content_text="256", is_correct=False, order=4)

        # Q2: Physics MCQ Multi
        self.q2 = Question.objects.create(
            question_bank=self.paper,
            section_name="Physics",
            question_number=2,
            question_type=QuestionType.MCQ_MULTI,
            content_text="Select valid statements",
            key="A,C",
            positive_marks=4.0,
            negative_marks=1.0,
            partial_marks=1.0,
        )
        Option.objects.create(question=self.q2, option_key="A", content_text="Statement A", is_correct=True, order=1)
        Option.objects.create(question=self.q2, option_key="B", content_text="Statement B", is_correct=False, order=2)
        Option.objects.create(question=self.q2, option_key="C", content_text="Statement C", is_correct=True, order=3)

        # Q3: Chemistry Numerical
        self.q3 = Question.objects.create(
            question_bank=self.paper,
            section_name="Chemistry",
            question_number=3,
            question_type=QuestionType.NUMERICAL,
            content_text="Number of unpaired electrons",
            key="4",
            positive_marks=4.0,
            negative_marks=0.0,
            numerical_min=4.0,
            numerical_max=4.0,
        )

        # Setup Examination
        self.exam = Examination.objects.create(
            organization=self.org,
            name="Grand CBT Exam 2026",
            question_paper=self.paper,
            duration_minutes=60,
            total_marks=11.0,
            status=ExaminationStatus.PUBLISHED,
            max_window_switches=3,
        )

        # Create Examination Sections
        self.sec_maths = ExaminationSection.objects.create(
            exam=self.exam, title="Maths", order=1, total_questions=1
        )
        ExaminationQuestion.objects.create(exam_section=self.sec_maths, question=self.q1, order=1)

        self.sec_physics = ExaminationSection.objects.create(
            exam=self.exam, title="Physics", order=2, total_questions=1
        )
        ExaminationQuestion.objects.create(exam_section=self.sec_physics, question=self.q2, order=1)

        self.sec_chem = ExaminationSection.objects.create(
            exam=self.exam, title="Chemistry", order=3, total_questions=1
        )
        ExaminationQuestion.objects.create(exam_section=self.sec_chem, question=self.q3, order=1)

    # =========================================================================
    # 1. Attempt Lifecycle & Question Delivery (No Secret Leak)
    # =========================================================================
    def test_attempt_start_and_payload_delivery(self):
        url = f"/api/v1/examinations/{self.exam.id}/start/"
        res = self.client.post(url, **self.tenant_headers)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data

        self.assertEqual(data["status"], "SUCCESS")
        self.assertIn("attempt_id", data)
        self.assertIn("attempt_token", data)
        self.assertIn("server_deadline", data)
        self.assertEqual(data["remaining_seconds"], 3600)
        self.assertFalse(data["is_recovered"])

        # Sections check
        self.assertEqual(len(data["sections"]), 3)
        sec_names = [s["name"] for s in data["sections"]]
        self.assertIn("Maths", sec_names)
        self.assertIn("Physics", sec_names)
        self.assertIn("Chemistry", sec_names)

        # Confirm NO leak of secret answer keys, explanations, or numerical bounds
        for sec in data["sections"]:
            for q in sec["questions"]:
                self.assertNotIn("key", q)
                self.assertNotIn("explanation", q)
                self.assertNotIn("numerical_min", q)
                self.assertNotIn("numerical_max", q)
                if "options" in q:
                    for opt in q["options"]:
                        self.assertNotIn("is_correct", opt)

    def test_delivery_payload_excludes_numerical_bounds_on_start_and_resume(self):
        # Start via /student/attempts/start/
        start_res = self.client.post(
            "/api/v1/student/attempts/start/",
            {"exam_id": str(self.exam.id)},
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(start_res.status_code, status.HTTP_200_OK)
        attempt_id = start_res.data["attempt_id"]

        start_questions = [q for sec in start_res.data["sections"] for q in sec["questions"]]
        self.assertTrue(any(str(q["id"]) == str(self.q3.id) for q in start_questions))
        for q in start_questions:
            self.assertNotIn("numerical_min", q)
            self.assertNotIn("numerical_max", q)

        # Resume via /student/attempts/{id}/resume/
        resume_res = self.client.get(
            f"/api/v1/student/attempts/{attempt_id}/resume/",
            **self.tenant_headers,
        )
        self.assertEqual(resume_res.status_code, status.HTTP_200_OK)
        resume_questions = [q for sec in resume_res.data["sections"] for q in sec["questions"]]
        self.assertTrue(any(str(q["id"]) == str(self.q3.id) for q in resume_questions))
        for q in resume_questions:
            self.assertNotIn("numerical_min", q)
            self.assertNotIn("numerical_max", q)

    def test_attempt_start_via_student_generic_endpoint(self):
        url = "/api/v1/student/attempts/start/"
        res = self.client.post(url, {"exam_id": str(self.exam.id)}, format="json", **self.tenant_headers)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("attempt_id", res.data)

    # =========================================================================
    # 2. Server-Authoritative Timer & Heartbeat
    # =========================================================================
    def test_heartbeat_sync_and_validation(self):
        start_res = self.client.post(f"/api/v1/examinations/{self.exam.id}/start/", **self.tenant_headers)
        att_id = start_res.data["attempt_id"]

        # Valid heartbeat
        hb_res = self.client.post(
            f"/api/v1/attempts/{att_id}/heartbeat/",
            {"window_blur_count": 1},
            format="json",
            **self.tenant_headers
        )
        self.assertEqual(hb_res.status_code, status.HTTP_200_OK)
        self.assertEqual(hb_res.data["status"], "SUCCESS")
        self.assertIn("server_time", hb_res.data)
        self.assertFalse(hb_res.data["is_terminated"])
        self.assertEqual(hb_res.data["tab_switch_count"], 1)

        # Negative blur count rejected
        neg_res = self.client.post(
            f"/api/v1/attempts/{att_id}/heartbeat/",
            {"window_blur_count": -2},
            format="json",
            **self.tenant_headers
        )
        self.assertEqual(neg_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(neg_res.data["code"], "INVALID_METRIC")

        # Exceeding threshold marks is_terminated = True
        high_res = self.client.post(
            f"/api/v1/attempts/{att_id}/heartbeat/",
            {"window_blur_count": 5},
            format="json",
            **self.tenant_headers
        )
        self.assertEqual(high_res.status_code, status.HTTP_200_OK)
        self.assertTrue(high_res.data["is_terminated"])

    # =========================================================================
    # 3. Response Persistence & 5-State Question Palette Transitions
    # =========================================================================
    def test_response_persistence_and_palette_transitions(self):
        start_res = self.client.post(f"/api/v1/examinations/{self.exam.id}/start/", **self.tenant_headers)
        att_id = start_res.data["attempt_id"]

        # 1. Answer Q1 (MCQ Single -> Option C)
        r1 = self.client.post(
            f"/api/v1/attempts/{att_id}/save_response/",
            {"question_id": str(self.q1.id), "selected_options": ["C"], "status": "ANSWERED", "time_spent_seconds": 30},
            format="json",
            **self.tenant_headers
        )
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(r1.data["status"], "SUCCESS")

        # 2. Marked for Review Q2
        r2 = self.client.post(
            f"/api/v1/attempts/{att_id}/save_response/",
            {"question_id": str(self.q2.id), "selected_options": [], "status": "MARKED_FOR_REVIEW"},
            format="json",
            **self.tenant_headers
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)

        # 3. Answered & Marked for Review Q3 (Numerical)
        r3 = self.client.post(
            f"/api/v1/attempts/{att_id}/save_response/",
            {"question_id": str(self.q3.id), "numerical_value": "4.0", "status": "ANSWERED_AND_MARKED_FOR_REVIEW"},
            format="json",
            **self.tenant_headers
        )
        self.assertEqual(r3.status_code, status.HTTP_200_OK)

        # Check in DB
        responses = AttemptResponse.objects.filter(attempt_id=att_id)
        self.assertEqual(responses.count(), 3)
        r1_db = responses.get(question=self.q1)
        self.assertEqual(r1_db.selected_options, ["C"])
        self.assertEqual(r1_db.status, ResponseStatus.ANSWERED)

        r2_db = responses.get(question=self.q2)
        self.assertEqual(r2_db.status, ResponseStatus.MARKED_FOR_REVIEW)

        r3_db = responses.get(question=self.q3)
        self.assertEqual(r3_db.numerical_value, "4.0")
        self.assertEqual(r3_db.status, ResponseStatus.ANSWERED_AND_MARKED)

    # =========================================================================
    # 4. Debounced Updates & Refresh Recovery
    # =========================================================================
    def test_debounced_save_and_session_recovery(self):
        start_res = self.client.post(f"/api/v1/examinations/{self.exam.id}/start/", **self.tenant_headers)
        att_id = start_res.data["attempt_id"]

        # Initial selection: A
        self.client.post(
            f"/api/v1/attempts/{att_id}/save_response/",
            {"question_id": str(self.q1.id), "selected_options": ["A"], "time_spent_seconds": 10},
            format="json",
            **self.tenant_headers
        )
        # Updated selection: C
        self.client.post(
            f"/api/v1/attempts/{att_id}/save_response/",
            {"question_id": str(self.q1.id), "selected_options": ["C"], "time_spent_seconds": 25},
            format="json",
            **self.tenant_headers
        )

        # Session refresh (calling start or resume again)
        refresh_res = self.client.post(
            "/api/v1/student/attempts/start/",
            {"exam_id": str(self.exam.id)},
            format="json",
            **self.tenant_headers
        )
        self.assertEqual(refresh_res.status_code, status.HTTP_200_OK)
        self.assertTrue(refresh_res.data["is_recovered"])
        saved = refresh_res.data["existing_responses"]
        self.assertIn(str(self.q1.id), saved)
        self.assertEqual(saved[str(self.q1.id)]["selected_options"], ["C"])

    # =========================================================================
    # 5. Idempotent Submission & Anti-Duplicate Pessimistic Locking
    # =========================================================================
    def test_idempotent_final_submission(self):
        start_res = self.client.post(f"/api/v1/examinations/{self.exam.id}/start/", **self.tenant_headers)
        att_id = start_res.data["attempt_id"]

        # First submit
        sub1 = self.client.post(
            f"/api/v1/attempts/{att_id}/submit/",
            {"submission_reason": "MANUAL_SUBMIT"},
            format="json",
            **self.tenant_headers
        )
        self.assertEqual(sub1.status_code, status.HTTP_200_OK)
        self.assertEqual(sub1.data["submission_status"], "SUBMITTED")
        sub1_time = sub1.data["submitted_at"]

        # Duplicate submit returns 200 ALREADY_SUBMITTED
        sub2 = self.client.post(
            f"/api/v1/attempts/{att_id}/submit/",
            {"submission_reason": "MANUAL_SUBMIT"},
            format="json",
            **self.tenant_headers
        )
        self.assertEqual(sub2.status_code, status.HTTP_200_OK)
        self.assertEqual(sub2.data["code"], "ALREADY_SUBMITTED")
        self.assertEqual(sub2.data["submitted_at"], sub1_time)

        # Saving response after submission must be rejected
        late_save = self.client.post(
            f"/api/v1/attempts/{att_id}/save_response/",
            {"question_id": str(self.q1.id), "selected_options": ["A"]},
            format="json",
            **self.tenant_headers
        )
        self.assertEqual(late_save.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(late_save.data["code"], "ATTEMPT_LOCKED")

    def test_auto_submit_on_timer_expiry(self):
        start_res = self.client.post(f"/api/v1/examinations/{self.exam.id}/start/", **self.tenant_headers)
        att_id = start_res.data["attempt_id"]

        auto_sub = self.client.post(
            f"/api/v1/attempts/{att_id}/submit/",
            {"submission_reason": "AUTO_TIMER_EXPIRY"},
            format="json",
            **self.tenant_headers
        )
        self.assertEqual(auto_sub.status_code, status.HTTP_200_OK)
        self.assertEqual(auto_sub.data["submission_status"], "SUBMITTED")

    def test_manual_submit_after_deadline_rejected(self):
        start_res = self.client.post(f"/api/v1/examinations/{self.exam.id}/start/", **self.tenant_headers)
        att_id = start_res.data["attempt_id"]

        # Set deadline to the past
        att = ExaminationAttempt.objects.get(id=att_id)
        att.server_deadline = timezone.now() - timedelta(minutes=10)
        att.save(update_fields=['server_deadline'])

        res = self.client.post(
            f"/api/v1/attempts/{att_id}/submit/",
            {"submission_reason": "MANUAL_SUBMIT"},
            format="json",
            **self.tenant_headers
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(res.data["code"], "DEADLINE_EXPIRED")

    # =========================================================================
    # 6. Proctoring Events & Tab Switches
    # =========================================================================
    def test_proctoring_tab_switches_and_auto_submission(self):
        start_res = self.client.post(f"/api/v1/examinations/{self.exam.id}/start/", **self.tenant_headers)
        att_id = start_res.data["attempt_id"]

        # Switch 1, 2, 3
        for i in range(1, 4):
            res = self.client.post(
                f"/api/v1/attempts/{att_id}/proctoring_event/",
                {"event_type": "TAB_SWITCH", "details": {"switch_index": i}},
                format="json",
                **self.tenant_headers
            )
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertFalse(res.data["auto_submitted"])

        # Switch 4 (exceeds limit 3) -> auto submitted
        res4 = self.client.post(
            f"/api/v1/attempts/{att_id}/proctoring_event/",
            {"event_type": "TAB_SWITCH", "details": {"switch_index": 4}},
            format="json",
            **self.tenant_headers
        )
        self.assertEqual(res4.status_code, status.HTTP_200_OK)
        self.assertTrue(res4.data["auto_submitted"])

        att = ExaminationAttempt.objects.get(id=att_id)
        self.assertEqual(att.status, AttemptStatus.AUTO_SUBMITTED)
        self.assertIsNotNone(att.submitted_at)
        self.assertEqual(att.proctoring_logs.count(), 4)


class WebSocketRemovalTestCase(TestCase):
    def test_asgi_application_is_http_only_and_rejects_websocket_scope(self):
        from config.asgi import application

        self.assertIsInstance(application, ASGIHandler)
        attempt_id = str(uuid.uuid4())
        scope = {
            "type": "websocket",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "scheme": "ws",
            "path": f"/ws/exam/{attempt_id}/",
            "raw_path": f"/ws/exam/{attempt_id}/".encode("ascii"),
            "query_string": b"",
            "headers": [],
        }
        sent_messages = []

        async def receive():
            return {"type": "websocket.connect"}

        async def send(message):
            sent_messages.append(message)

        with self.assertRaises(ValueError):
            async_to_sync(application)(scope, receive, send)

        self.assertEqual(sent_messages, [])

    def test_websocket_routing_and_consumer_removed(self):
        from apps.engine import consumers, routing

        self.assertEqual(routing.websocket_urlpatterns, [])
        self.assertFalse(hasattr(consumers, "ExamAttemptConsumer"))


class AttemptPartialUniqueConstraintTestCase(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name="Constraint Org",
            slug="constraint-org",
            domain="constraint.ezexam.in",
        )
        self.student = User.objects.create_user(
            username="student_d4@constraint.edu",
            email="student_d4@constraint.edu",
            password="StudentPassword123!",
            role=UserRole.STUDENT,
            organization=self.org,
        )
        self.exam = Examination.objects.create(
            organization=self.org,
            name="D4 Constraint Exam",
            duration_minutes=60,
            total_marks=10.0,
            status=ExaminationStatus.PUBLISHED,
        )

    def test_partial_unique_constraint_blocks_duplicate_in_progress_and_allows_after_finalize(self):
        now = timezone.now()
        first = ExaminationAttempt.objects.create(
            user=self.student,
            examination=self.exam,
            started_at=now,
            server_deadline=now + timedelta(minutes=60),
            status=AttemptStatus.IN_PROGRESS,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ExaminationAttempt.objects.create(
                    user=self.student,
                    examination=self.exam,
                    started_at=now,
                    server_deadline=now + timedelta(minutes=60),
                    status=AttemptStatus.IN_PROGRESS,
                )

        # Finalizing the first attempt permits creating a subsequent IN_PROGRESS attempt
        first.status = AttemptStatus.SUBMITTED
        first.submitted_at = now
        first.save(update_fields=["status", "submitted_at"])

        second = ExaminationAttempt.objects.create(
            user=self.student,
            examination=self.exam,
            started_at=now,
            server_deadline=now + timedelta(minutes=60),
            status=AttemptStatus.IN_PROGRESS,
        )
        self.assertNotEqual(first.id, second.id)

        # Multiple finalized attempts are also permitted by the partial constraint
        second.status = AttemptStatus.AUTO_SUBMITTED
        second.submitted_at = now
        second.save(update_fields=["status", "submitted_at"])
        third = ExaminationAttempt.objects.create(
            user=self.student,
            examination=self.exam,
            started_at=now,
            server_deadline=now + timedelta(minutes=60),
            status=AttemptStatus.SUBMITTED,
            submitted_at=now,
        )
        self.assertEqual(ExaminationAttempt.objects.filter(user=self.student, examination=self.exam).count(), 3)


class AttemptLifecycleServicesTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(
            name="Lifecycle Org",
            slug="lifecycle-org",
            domain="lifecycle.ezexam.in",
        )
        self.student = User.objects.create_user(
            username="student_lc@lifecycle.edu",
            email="student_lc@lifecycle.edu",
            password="StudentPassword123!",
            role=UserRole.STUDENT,
            organization=self.org,
        )
        self.client.force_authenticate(user=self.student)
        self.tenant_headers = {"HTTP_X_TENANT_ID": str(self.org.id)}

        self.paper = QuestionBank.objects.create(
            organization=self.org,
            name="Lifecycle Paper",
            duration_minutes=60,
        )
        self.q1 = Question.objects.create(
            question_bank=self.paper,
            section_name="General",
            question_number=1,
            question_type=QuestionType.MCQ_SINGLE,
            content_text="2 + 2 = ?",
            key="B",
            positive_marks=4.0,
            negative_marks=1.0,
        )
        Option.objects.create(question=self.q1, option_key="A", content_text="3", is_correct=False, order=1)
        Option.objects.create(question=self.q1, option_key="B", content_text="4", is_correct=True, order=2)

        self.exam = Examination.objects.create(
            organization=self.org,
            name="Lifecycle Exam",
            question_paper=self.paper,
            duration_minutes=60,
            total_marks=4.0,
            status=ExaminationStatus.PUBLISHED,
            max_window_switches=3,
        )

    def test_start_attempt_expires_overdue_in_progress_attempt_and_returns_409(self):
        start_res = self.client.post(
            "/api/v1/student/attempts/start/",
            {"exam_id": str(self.exam.id)},
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(start_res.status_code, status.HTTP_200_OK)
        att_id = start_res.data["attempt_id"]

        att = ExaminationAttempt.objects.get(id=att_id)
        att.server_deadline = timezone.now() - timedelta(seconds=40)
        att.save(update_fields=["server_deadline"])

        retry_res = self.client.post(
            "/api/v1/student/attempts/start/",
            {"exam_id": str(self.exam.id)},
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(retry_res.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(retry_res.data["code"], "ALREADY_SUBMITTED")

        att.refresh_from_db()
        self.assertEqual(att.status, AttemptStatus.AUTO_SUBMITTED)
        self.assertIsNotNone(att.submitted_at)

    def test_resume_attempt_expires_overdue_in_progress_attempt_and_returns_409(self):
        start_res = self.client.post(
            "/api/v1/student/attempts/start/",
            {"exam_id": str(self.exam.id)},
            format="json",
            **self.tenant_headers,
        )
        att_id = start_res.data["attempt_id"]

        att = ExaminationAttempt.objects.get(id=att_id)
        att.server_deadline = timezone.now() - timedelta(seconds=40)
        att.save(update_fields=["server_deadline"])

        res = self.client.get(f"/api/v1/student/attempts/{att_id}/resume/", **self.tenant_headers)
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(res.data["code"], "ALREADY_SUBMITTED")

        att.refresh_from_db()
        self.assertEqual(att.status, AttemptStatus.AUTO_SUBMITTED)
        self.assertIsNotNone(att.submitted_at)

    def test_heartbeat_after_submit_does_not_mutate_tab_switch_count_and_returns_zero(self):
        start_res = self.client.post(
            f"/api/v1/examinations/{self.exam.id}/start/",
            **self.tenant_headers,
        )
        att_id = start_res.data["attempt_id"]

        sub_res = self.client.post(
            f"/api/v1/attempts/{att_id}/submit/",
            {"submission_reason": "MANUAL_SUBMIT"},
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(sub_res.status_code, status.HTTP_200_OK)

        hb_res = self.client.post(
            f"/api/v1/attempts/{att_id}/heartbeat/",
            {"window_blur_count": 10},
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(hb_res.status_code, status.HTTP_200_OK)
        self.assertEqual(hb_res.data["remaining_seconds"], 0)
        self.assertTrue(hb_res.data["is_terminated"])
        self.assertEqual(hb_res.data["tab_switch_count"], 0)

        att = ExaminationAttempt.objects.get(id=att_id)
        self.assertEqual(att.tab_switch_count, 0)
        self.assertEqual(att.status, AttemptStatus.SUBMITTED)

    def test_heartbeat_blur_overflow_auto_submits_attempt(self):
        start_res = self.client.post(
            f"/api/v1/examinations/{self.exam.id}/start/",
            **self.tenant_headers,
        )
        att_id = start_res.data["attempt_id"]

        hb_res = self.client.post(
            f"/api/v1/attempts/{att_id}/heartbeat/",
            {"window_blur_count": 4},
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(hb_res.status_code, status.HTTP_200_OK)
        self.assertTrue(hb_res.data["is_terminated"])
        self.assertEqual(hb_res.data["remaining_seconds"], 0)

        att = ExaminationAttempt.objects.get(id=att_id)
        self.assertEqual(att.status, AttemptStatus.AUTO_SUBMITTED)
        self.assertIsNotNone(att.submitted_at)

    def test_start_attempt_exact_end_window_rejected_and_deadline_capped(self):
        from apps.engine import services

        now = timezone.now()
        self.exam.end_window = now
        self.exam.save(update_fields=["end_window"])

        exact_outcome = services.start_attempt(self.student, self.exam.id, tenant=self.org, now=now)
        self.assertFalse(exact_outcome.ok)
        self.assertEqual(exact_outcome.http_status, status.HTTP_403_FORBIDDEN)
        self.assertEqual(exact_outcome.data["code"], "EXAM_EXPIRED")

        self.exam.end_window = now - timedelta(seconds=1)
        self.exam.save(update_fields=["end_window"])

        expired_res = self.client.post(
            f"/api/v1/examinations/{self.exam.id}/start/",
            **self.tenant_headers,
        )
        self.assertEqual(expired_res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(expired_res.data["code"], "EXAM_EXPIRED")

        self.exam.end_window = now + timedelta(minutes=10)
        self.exam.save(update_fields=["end_window"])
        capped_res = self.client.post(
            f"/api/v1/examinations/{self.exam.id}/start/",
            **self.tenant_headers,
        )
        self.assertEqual(capped_res.status_code, status.HTTP_200_OK)
        self.assertLessEqual(capped_res.data["remaining_seconds"], 600)
        att = ExaminationAttempt.objects.get(id=capped_res.data["attempt_id"])
        self.assertEqual(att.server_deadline, self.exam.end_window)

    def test_start_attempt_recovers_on_d4_integrity_error_savepoint(self):
        from unittest.mock import patch
        from apps.engine import services

        real_compute_deadline = services.compute_server_deadline
        created_holder = []

        def inject_concurrent_row(exam, started_at):
            deadline = real_compute_deadline(exam, started_at)
            winning = ExaminationAttempt.objects.create(
                user=self.student,
                examination=exam,
                started_at=started_at,
                server_deadline=deadline,
                status=AttemptStatus.IN_PROGRESS,
                tab_switch_count=0,
            )
            created_holder.append(winning)
            return deadline

        with patch.object(services, "compute_server_deadline", side_effect=inject_concurrent_row):
            res = self.client.post(
                "/api/v1/student/attempts/start/",
                {"exam_id": str(self.exam.id)},
                format="json",
                **self.tenant_headers,
            )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["is_recovered"])
        self.assertEqual(res.data["attempt_id"], str(created_holder[0].id))

    def test_manual_submit_after_deadline_persists_auto_submitted_and_returns_403(self):
        start_res = self.client.post(
            f"/api/v1/examinations/{self.exam.id}/start/",
            **self.tenant_headers,
        )
        att_id = start_res.data["attempt_id"]

        att = ExaminationAttempt.objects.get(id=att_id)
        att.server_deadline = timezone.now() - timedelta(seconds=45)
        att.save(update_fields=["server_deadline"])

        late_manual = self.client.post(
            f"/api/v1/attempts/{att_id}/submit/",
            {"submission_reason": "MANUAL_SUBMIT"},
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(late_manual.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(late_manual.data["code"], "DEADLINE_EXPIRED")

        att.refresh_from_db()
        self.assertEqual(att.status, AttemptStatus.AUTO_SUBMITTED)
        self.assertIsNotNone(att.submitted_at)
        recorded_ts = att.submitted_at.isoformat()

        # Subsequent submit returns idempotent 200 ALREADY_SUBMITTED preserving timestamp
        follow_up = self.client.post(
            f"/api/v1/attempts/{att_id}/submit/",
            {"submission_reason": "AUTO_TIMER_EXPIRY"},
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(follow_up.status_code, status.HTTP_200_OK)
        self.assertEqual(follow_up.data["code"], "ALREADY_SUBMITTED")
        self.assertEqual(follow_up.data["submitted_at"], recorded_ts)

    def test_submit_attempt_rejects_cross_tenant_staff_and_other_student(self):
        start_res = self.client.post(
            f"/api/v1/examinations/{self.exam.id}/start/",
            **self.tenant_headers,
        )
        att_id = start_res.data["attempt_id"]

        other_org = Organization.objects.create(name="Other Org", slug="other-org-submit")
        other_staff = User.objects.create_user(
            username="staff@other.edu",
            password="StaffPassword123!",
            role=UserRole.ORG_ADMIN,
            is_staff=True,
            organization=other_org,
        )
        other_student = User.objects.create_user(
            username="peer@lifecycle.edu",
            password="StudentPassword123!",
            role=UserRole.STUDENT,
            organization=self.org,
        )

        other_client = APIClient()
        other_client.force_authenticate(user=other_staff)
        res_staff = other_client.post(
            f"/api/v1/attempts/{att_id}/submit/",
            {"submission_reason": "MANUAL_SUBMIT"},
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(res_staff.status_code, status.HTTP_403_FORBIDDEN)

        other_client.force_authenticate(user=other_student)
        res_peer = other_client.post(
            f"/api/v1/attempts/{att_id}/submit/",
            {"submission_reason": "MANUAL_SUBMIT"},
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(res_peer.status_code, status.HTTP_403_FORBIDDEN)

        att = ExaminationAttempt.objects.get(id=att_id)
        self.assertEqual(att.status, AttemptStatus.IN_PROGRESS)


class SaveResponseScopingAndValidationTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org_a = Organization.objects.create(
            name="Org Alpha",
            slug="org-alpha-sr",
            domain="alpha-sr.ezexam.in",
        )
        self.org_b = Organization.objects.create(
            name="Org Beta",
            slug="org-beta-sr",
            domain="beta-sr.ezexam.in",
        )

        self.student_a = User.objects.create_user(
            username="stud_a@alpha.edu",
            password="Password123!",
            role=UserRole.STUDENT,
            organization=self.org_a,
        )
        self.student_b = User.objects.create_user(
            username="stud_b@beta.edu",
            password="Password123!",
            role=UserRole.STUDENT,
            organization=self.org_b,
        )
        self.headers_a = {"HTTP_X_TENANT_ID": str(self.org_a.id)}
        self.headers_b = {"HTTP_X_TENANT_ID": str(self.org_b.id)}

        self.paper_a = QuestionBank.objects.create(organization=self.org_a, name="Paper A")
        self.q_a1 = Question.objects.create(
            question_bank=self.paper_a,
            section_name="Maths",
            question_number=1,
            question_type=QuestionType.MCQ_SINGLE,
            content_text="Org A Q1",
            key="A",
            positive_marks=4.0,
            negative_marks=1.0,
        )
        Option.objects.create(question=self.q_a1, option_key="A", content_text="1", is_correct=True, order=1)
        Option.objects.create(question=self.q_a1, option_key="B", content_text="2", is_correct=False, order=2)

        self.q_a_unlinked = Question.objects.create(
            question_bank=self.paper_a,
            section_name="Maths",
            question_number=2,
            question_type=QuestionType.MCQ_SINGLE,
            content_text="Org A Unlinked Q2",
            key="A",
            positive_marks=4.0,
            negative_marks=1.0,
        )
        Option.objects.create(question=self.q_a_unlinked, option_key="A", content_text="Yes", is_correct=True, order=1)

        self.q_a_num = Question.objects.create(
            question_bank=self.paper_a,
            section_name="Chem",
            question_number=3,
            question_type=QuestionType.NUMERICAL,
            content_text="Org A Numerical Q3",
            key="5",
            positive_marks=4.0,
            negative_marks=0.0,
        )

        self.exam_a = Examination.objects.create(
            organization=self.org_a,
            name="Exam A Sectioned",
            question_paper=self.paper_a,
            duration_minutes=60,
            total_marks=8.0,
            status=ExaminationStatus.PUBLISHED,
        )
        sec_a = ExaminationSection.objects.create(exam=self.exam_a, title="Maths", order=1, total_questions=2)
        ExaminationQuestion.objects.create(exam_section=sec_a, question=self.q_a1, order=1)
        ExaminationQuestion.objects.create(exam_section=sec_a, question=self.q_a_num, order=2)

        self.paper_a2 = QuestionBank.objects.create(organization=self.org_a, name="Paper A2")
        self.q_a2 = Question.objects.create(
            question_bank=self.paper_a2,
            section_name="Physics",
            question_number=1,
            question_type=QuestionType.MCQ_SINGLE,
            content_text="Other Exam Q",
            key="A",
        )
        Option.objects.create(question=self.q_a2, option_key="A", content_text="Opt", is_correct=True, order=1)
        self.exam_a2 = Examination.objects.create(
            organization=self.org_a,
            name="Exam A2 Paper Fallback",
            question_paper=self.paper_a2,
            duration_minutes=60,
            total_marks=4.0,
            status=ExaminationStatus.PUBLISHED,
        )

        self.paper_b = QuestionBank.objects.create(organization=self.org_b, name="Paper B")
        self.q_b2 = Question.objects.create(
            question_bank=self.paper_b,
            section_name="Bio",
            question_number=2,
            question_type=QuestionType.MCQ_SINGLE,
            content_text="Org B Q2",
            key="A",
        )
        Option.objects.create(question=self.q_b2, option_key="A", content_text="Cell", is_correct=True, order=1)
        self.exam_b = Examination.objects.create(
            organization=self.org_b,
            name="Exam B",
            question_paper=self.paper_b,
            duration_minutes=60,
            total_marks=4.0,
            status=ExaminationStatus.PUBLISHED,
        )

    def _start_attempt(self, user, exam, headers):
        self.client.force_authenticate(user=user)
        res = self.client.post(f"/api/v1/examinations/{exam.id}/start/", **headers)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        return res.data["attempt_id"]

    def test_save_response_rejects_cross_tenant_question_number_fallback(self):
        att_b = self._start_attempt(self.student_b, self.exam_b, self.headers_b)
        res = self.client.post(
            f"/api/v1/attempts/{att_b}/save_response/",
            {"question_id": 1, "selected_options": ["A"]},
            format="json",
            **self.headers_b,
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["code"], "INVALID_QUESTION_ID")
        self.assertEqual(AttemptResponse.objects.filter(attempt_id=att_b).count(), 0)

    def test_save_response_rejects_cross_tenant_question_uuid(self):
        att_b = self._start_attempt(self.student_b, self.exam_b, self.headers_b)
        res = self.client.post(
            f"/api/v1/attempts/{att_b}/save_response/",
            {"question_id": str(self.q_a1.id), "selected_options": ["A"]},
            format="json",
            **self.headers_b,
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(res.data["code"], "QUESTION_NOT_FOUND")
        self.assertEqual(AttemptResponse.objects.filter(attempt_id=att_b).count(), 0)

    def test_save_response_rejects_same_tenant_other_exam_and_unlinked_paper_questions(self):
        att_a = self._start_attempt(self.student_a, self.exam_a, self.headers_a)
        for foreign_q in (self.q_a2, self.q_a_unlinked):
            res = self.client.post(
                f"/api/v1/attempts/{att_a}/save_response/",
                {"question_id": str(foreign_q.id), "selected_options": ["A"]},
                format="json",
                **self.headers_a,
            )
            self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
            self.assertEqual(res.data["code"], "QUESTION_NOT_FOUND")
        self.assertEqual(AttemptResponse.objects.filter(attempt_id=att_a).count(), 0)

    def test_save_response_allows_paper_fallback_exam_without_sections(self):
        att_a2 = self._start_attempt(self.student_a, self.exam_a2, self.headers_a)
        res = self.client.post(
            f"/api/v1/attempts/{att_a2}/save_response/",
            {"question_id": str(self.q_a2.id), "selected_options": ["A"]},
            format="json",
            **self.headers_a,
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(AttemptResponse.objects.filter(attempt_id=att_a2, question=self.q_a2).count(), 1)

    def test_save_response_rejects_malformed_and_type_mismatched_payloads(self):
        att_a = self._start_attempt(self.student_a, self.exam_a, self.headers_a)
        bad_payloads = [
            {"question_id": str(self.q_a1.id), "selected_options": None},
            {"question_id": str(self.q_a1.id), "selected_options": "A"},
            {"question_id": str(self.q_a1.id), "selected_options": ["Z"]},
            {"question_id": str(self.q_a1.id), "selected_options": ["A", "B"]},
            {"question_id": str(self.q_a1.id), "selected_options": ["A"], "numerical_value": "5"},
            {"question_id": str(self.q_a_num.id), "selected_options": ["A"]},
            {"question_id": str(self.q_a_num.id), "numerical_value": "abc"},
            {"question_id": str(self.q_a_num.id), "numerical_value": "NaN"},
            {"question_id": str(self.q_a_num.id), "numerical_value": "1" * 101},
            {"question_id": str(self.q_a1.id), "selected_options": ["A"], "time_spent_seconds": -1},
            {"question_id": str(self.q_a1.id), "selected_options": ["A"], "time_spent_seconds": "bad"},
            {"question_id": str(self.q_a1.id), "selected_options": ["A"], "time_spent_seconds": True},
            {"question_id": str(self.q_a1.id), "selected_options": ["A"], "status": "BOGUS_STATUS"},
        ]
        for payload in bad_payloads:
            with self.subTest(payload=payload):
                res = self.client.post(
                    f"/api/v1/attempts/{att_a}/save_response/",
                    payload,
                    format="json",
                    **self.headers_a,
                )
                self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(res.data["code"], "INVALID_RESPONSE")
        self.assertEqual(AttemptResponse.objects.filter(attempt_id=att_a).count(), 0)

    def test_save_response_after_deadline_auto_submits_and_rejects(self):
        att_a = self._start_attempt(self.student_a, self.exam_a, self.headers_a)
        att = ExaminationAttempt.objects.get(id=att_a)
        att.server_deadline = timezone.now() - timedelta(seconds=45)
        att.save(update_fields=["server_deadline"])

        res1 = self.client.post(
            f"/api/v1/attempts/{att_a}/save_response/",
            {"question_id": str(self.q_a1.id), "selected_options": ["A"]},
            format="json",
            **self.headers_a,
        )
        self.assertEqual(res1.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(res1.data["code"], "DEADLINE_EXPIRED")

        att.refresh_from_db()
        self.assertEqual(att.status, AttemptStatus.AUTO_SUBMITTED)
        self.assertEqual(AttemptResponse.objects.filter(attempt_id=att_a).count(), 0)

        res2 = self.client.post(
            f"/api/v1/attempts/{att_a}/save_response/",
            {"question_id": str(self.q_a1.id), "selected_options": ["A"]},
            format="json",
            **self.headers_a,
        )
        self.assertEqual(res2.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(res2.data["code"], "ATTEMPT_LOCKED")

    def test_attempt_response_serializer_does_not_expose_unscoped_questions(self):
        from apps.engine.serializers import AttemptResponseSerializer

        unscoped = AttemptResponseSerializer()
        self.assertEqual(unscoped.fields["question_id"].queryset.count(), 0)
        scoped = AttemptResponseSerializer(context={"examination": self.exam_a})
        scoped_ids = set(scoped.fields["question_id"].queryset.values_list("id", flat=True))
        self.assertEqual(scoped_ids, {self.q_a1.id, self.q_a_num.id})


POSTGRES_CONCURRENCY_SKIP_REASON = (
    "Requires PostgreSQL for row-level locking / concurrent constraint enforcement"
)


@unittest.skipUnless(connection.vendor == "postgresql", POSTGRES_CONCURRENCY_SKIP_REASON)
class AttemptConcurrencyPostgresTestCase(TransactionTestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name="PG Concurrency Org",
            slug="pg-conc-org",
            domain="pgconc.ezexam.in",
        )
        self.student = User.objects.create_user(
            username="pg_student@conc.edu",
            email="pg_student@conc.edu",
            password="StudentPassword123!",
            role=UserRole.STUDENT,
            organization=self.org,
        )
        self.paper = QuestionBank.objects.create(
            organization=self.org,
            name="PG Paper",
            duration_minutes=60,
        )
        self.q1 = Question.objects.create(
            question_bank=self.paper,
            section_name="General",
            question_number=1,
            question_type=QuestionType.MCQ_SINGLE,
            content_text="1 + 1 = ?",
            key="A",
            positive_marks=4.0,
            negative_marks=0.0,
        )
        Option.objects.create(question=self.q1, option_key="A", content_text="2", is_correct=True, order=1)
        self.exam = Examination.objects.create(
            organization=self.org,
            name="PG Exam",
            question_paper=self.paper,
            duration_minutes=60,
            total_marks=4.0,
            status=ExaminationStatus.PUBLISHED,
            max_window_switches=3,
        )
        self.tenant_headers = {"HTTP_X_TENANT_ID": str(self.org.id)}

    def test_concurrent_start_attempts_create_single_row(self):
        worker_count = 5
        barrier = threading.Barrier(worker_count)

        def worker():
            try:
                client = APIClient()
                client.force_authenticate(user=self.student)
                barrier.wait(timeout=10)
                return client.post(
                    "/api/v1/student/attempts/start/",
                    {"exam_id": str(self.exam.id)},
                    format="json",
                    **self.tenant_headers,
                )
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            responses = list(pool.map(lambda _: worker(), range(worker_count)))

        self.assertTrue(all(r.status_code == status.HTTP_200_OK for r in responses))
        attempt_ids = {r.data["attempt_id"] for r in responses}
        self.assertEqual(len(attempt_ids), 1)
        self.assertEqual(
            ExaminationAttempt.objects.filter(examination=self.exam, user=self.student).count(),
            1,
        )

    def test_concurrent_submit_attempts_serialize_and_submit_once(self):
        start_client = APIClient()
        start_client.force_authenticate(user=self.student)
        start_res = start_client.post(
            "/api/v1/student/attempts/start/",
            {"exam_id": str(self.exam.id)},
            format="json",
            **self.tenant_headers,
        )
        att_id = start_res.data["attempt_id"]

        worker_count = 5
        barrier = threading.Barrier(worker_count)

        def worker():
            try:
                client = APIClient()
                client.force_authenticate(user=self.student)
                barrier.wait(timeout=10)
                return client.post(
                    f"/api/v1/attempts/{att_id}/submit/",
                    {"submission_reason": "MANUAL_SUBMIT"},
                    format="json",
                    **self.tenant_headers,
                )
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            responses = list(pool.map(lambda _: worker(), range(worker_count)))

        self.assertTrue(all(r.status_code == status.HTTP_200_OK for r in responses))
        already_codes = [r for r in responses if r.data.get("code") == "ALREADY_SUBMITTED"]
        first_submits = [r for r in responses if "code" not in r.data]
        self.assertEqual(len(first_submits), 1)
        self.assertEqual(len(already_codes), worker_count - 1)
        submitted_timestamps = {r.data["submitted_at"] for r in responses}
        self.assertEqual(len(submitted_timestamps), 1)
        att = ExaminationAttempt.objects.get(id=att_id)
        self.assertEqual(att.status, AttemptStatus.SUBMITTED)

    def test_save_response_blocks_behind_submit_lock_and_rejects(self):
        from apps.engine import services

        start_client = APIClient()
        start_client.force_authenticate(user=self.student)
        start_res = start_client.post(
            "/api/v1/student/attempts/start/",
            {"exam_id": str(self.exam.id)},
            format="json",
            **self.tenant_headers,
        )
        att_id = start_res.data["attempt_id"]

        lock_acquired = threading.Event()
        thread_b_result = {}

        def submitter():
            try:
                with transaction.atomic():
                    locked, _ = services.lock_attempt(att_id, user=self.student, tenant=self.org)
                    lock_acquired.set()
                    import time
                    time.sleep(0.2)
                    locked.status = AttemptStatus.SUBMITTED
                    locked.submitted_at = timezone.now()
                    locked.save(update_fields=["status", "submitted_at", "updated_at"])
            finally:
                connections.close_all()

        def saver():
            try:
                lock_acquired.wait(timeout=10)
                client = APIClient()
                client.force_authenticate(user=self.student)
                thread_b_result["res"] = client.post(
                    f"/api/v1/attempts/{att_id}/save_response/",
                    {"question_id": str(self.q1.id), "selected_options": ["A"]},
                    format="json",
                    **self.tenant_headers,
                )
            finally:
                connections.close_all()

        t1 = threading.Thread(target=submitter)
        t2 = threading.Thread(target=saver)
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        res = thread_b_result["res"]
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(res.data["code"], "ATTEMPT_LOCKED")
        self.assertEqual(AttemptResponse.objects.filter(attempt_id=att_id).count(), 0)
