import unittest
import uuid
from datetime import timedelta
from asgiref.sync import async_to_sync
from django.core.handlers.asgi import ASGIHandler
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
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
