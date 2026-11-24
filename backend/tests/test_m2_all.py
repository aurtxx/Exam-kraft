import io
import uuid
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.organizations.models import Organization, Batch, ExaminationCenter, StudentBatchEnrollment
from apps.accounts.models import User, UserRole, UserProfile, FacultyProfile
from apps.question_bank.models import QuestionBank, Question, Option, QuestionType
from apps.examinations.models import Examination, ExaminationStatus, CandidateAssignment
from apps.notices.models import Notice


class MilestoneM2ComprehensiveTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(
            name="Apex Institute of Technology",
            slug="apex-tech",
            domain="apex-tech.ezexam.in",
        )
        self.admin_user = User.objects.create_user(
            username="admin@apex.edu",
            email="admin@apex.edu",
            password="SecurePassword123!",
            role=UserRole.ORG_ADMIN,
            organization=self.org,
        )
        UserProfile.objects.create(user=self.admin_user, full_name="System Administrator")
        self.client.force_authenticate(user=self.admin_user)
        self.tenant_headers = {"HTTP_X_TENANT_ID": str(self.org.id)}

    # ==========================================================================
    # 1. Master Data: Batch & Center CRUD with Tenant Isolation
    # ==========================================================================
    def test_batch_crud_and_duplicate_code(self):
        # Create Batch
        payload = {"name": "JEE Elite 2026", "code": "JEE26", "stream": "JEE_ADVANCED"}
        res = self.client.post("/api/v1/organizations/batches/", payload, format="json", **self.tenant_headers)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        batch_id = res.data["id"]

        # Duplicate code returns 409
        dup_res = self.client.post("/api/v1/organizations/batches/", payload, format="json", **self.tenant_headers)
        self.assertEqual(dup_res.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(dup_res.data["code"], "DUPLICATE_CODE")

        # List batches
        list_res = self.client.get("/api/v1/organizations/batches/", **self.tenant_headers)
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertTrue(any(b["id"] == batch_id for b in list_res.data["batches"]))

    def test_center_capacity_validation(self):
        # Capacity <= 0 returns 400
        res = self.client.post(
            "/api/v1/organizations/centers/",
            {"name": "Zero Center", "code": "ZC01", "capacity": 0},
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["code"], "INVALID_CAPACITY")

        # Valid center creation
        valid_res = self.client.post(
            "/api/v1/organizations/centers/",
            {"name": "North Center Lab", "code": "NCL01", "capacity": 120},
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(valid_res.status_code, status.HTTP_201_CREATED)

    # ==========================================================================
    # 2. Accounts: Faculty, Students & Bulk CSV Import with Rollback
    # ==========================================================================
    def test_faculty_roster_management(self):
        payload = {
            "name": "Dr. Richard Feynman",
            "email": "feynman@apex.edu",
            "department": "Physics",
            "subjects": ["Quantum Mechanics", "Electrodynamics"],
        }
        res = self.client.post("/api/v1/users/faculty/", payload, format="json", **self.tenant_headers)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", res.data)

        # Retrieve faculty list
        list_res = self.client.get("/api/v1/users/faculty/", **self.tenant_headers)
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertTrue(any(f["name"] == "Dr. Richard Feynman" for f in list_res.data["faculties"]))

    def test_student_roster_and_pagination(self):
        batch = Batch.all_objects.create(organization=self.org, name="Batch A", code="BA01")
        payload = {
            "roll_number": "2026101",
            "name": "Aryabhata Sharma",
            "email": "aryabhata@apex.edu",
            "batch_id": str(batch.id),
        }
        res = self.client.post("/api/v1/users/students/", payload, format="json", **self.tenant_headers)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Duplicate roll number returns 409
        dup_res = self.client.post("/api/v1/users/students/", payload, format="json", **self.tenant_headers)
        self.assertEqual(dup_res.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(dup_res.data["code"], "DUPLICATE_ROLL")

        # Pagination: page_size <= 0 returns 400
        inv_res = self.client.get("/api/v1/users/students/?page_size=0", **self.tenant_headers)
        self.assertEqual(inv_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(inv_res.data["code"], "INVALID_PAGE_SIZE")

    def test_bulk_csv_import_valid_and_rollback(self):
        batch = Batch.all_objects.create(organization=self.org, name="Batch CSV", code="CSV01")

        # 1. Valid bulk CSV
        csv_data = (
            "RollNumber,Name,Email,BatchCode\n"
            "2026901,Student One,s1@apex.edu,CSV01\n"
            "2026902,Student Two,s2@apex.edu,CSV01\n"
        )
        res = self.client.post(
            "/api/v1/users/students/bulk-upload/",
            data=csv_data.encode("utf-8"),
            content_type="text/csv",
            **self.tenant_headers,
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["created_count"], 2)

        # 2. Invalid bulk CSV with duplicate roll numbers inside -> rollback!
        bad_csv = (
            "RollNumber,Name,Email,BatchCode\n"
            "2026903,Student Three,s3@apex.edu,CSV01\n"
            "2026903,Duplicate Student,s3dup@apex.edu,CSV01\n"
        )
        bad_res = self.client.post(
            "/api/v1/users/students/bulk-upload/",
            data=bad_csv.encode("utf-8"),
            content_type="text/csv",
            **self.tenant_headers,
        )
        self.assertEqual(bad_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(bad_res.data["created_count"], 0)
        self.assertTrue(len(bad_res.data["errors"]) > 0)
        # Ensure 2026903 was NOT committed to DB (transaction rolled back)
        self.assertFalse(StudentBatchEnrollment.objects.filter(roll_number="2026903").exists())

    # ==========================================================================
    # 3. Question Bank: Multi-Type Questions & Marking Schemes
    # ==========================================================================
    def test_question_authoring_and_validations(self):
        qp_res = self.client.post(
            "/api/v1/question-papers/",
            {"name": "Comprehensive Science Test", "exam_type": "JEE-Main"},
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(qp_res.status_code, status.HTTP_201_CREATED)
        qpid = qp_res.data["id"]

        # MCQ Single
        q1_res = self.client.post(
            f"/api/v1/question-papers/{qpid}/questions/",
            {
                "question_type": "MCQ_SINGLE",
                "section": "Physics",
                "content_text": "What is the speed of light in vacuum?",
                "key": "C",
                "positive_marks": 4.0,
                "negative_marks": 1.0,
                "options": [
                    {"key": "A", "text": "3e6 m/s"},
                    {"key": "B", "text": "3e7 m/s"},
                    {"key": "C", "text": "3e8 m/s"},
                    {"key": "D", "text": "3e9 m/s"},
                ],
            },
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(q1_res.status_code, status.HTTP_201_CREATED)

        # Numerical with tolerance
        q2_res = self.client.post(
            f"/api/v1/question-papers/{qpid}/questions/",
            {
                "question_type": "NUMERICAL",
                "section": "Maths",
                "content_text": "Compute $2^{10}$.",
                "key": "1024",
                "positive_marks": 4.0,
                "negative_marks": 0.0,
            },
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(q2_res.status_code, status.HTTP_201_CREATED)

        # True/False (type 21)
        q3_res = self.client.post(
            f"/api/v1/question-papers/{qpid}/questions/",
            {
                "question_type": "21",
                "section": "Physics",
                "content_text": "Energy is conserved in an isolated system.",
                "key": "A",
                "positive_marks": 2.0,
                "negative_marks": 0.5,
                "options": [{"key": "A", "text": "True"}, {"key": "B", "text": "False"}],
            },
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(q3_res.status_code, status.HTTP_201_CREATED)

        # Coding question (type 721)
        q4_res = self.client.post(
            f"/api/v1/question-papers/{qpid}/questions/",
            {
                "question_type": "721",
                "section": "Computer Science",
                "content_text": "Write a function to return fibonacci sequence.",
                "coding_language": "python",
                "positive_marks": 10.0,
                "negative_marks": 0.0,
            },
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(q4_res.status_code, status.HTTP_201_CREATED)

        # Validation: Negative marks > Positive marks returns 400
        bad_marking = self.client.post(
            f"/api/v1/question-papers/{qpid}/questions/",
            {
                "question_type": "MCQ_SINGLE",
                "content_text": "Invalid Marking Q",
                "key": "A",
                "positive_marks": 2.0,
                "negative_marks": 5.0,
                "options": [{"key": "A", "text": "1"}],
            },
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(bad_marking.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(bad_marking.data["code"], "INVALID_MARKING")

        # Validation: MCQ without options returns 400
        no_options = self.client.post(
            f"/api/v1/question-papers/{qpid}/questions/",
            {
                "question_type": "MCQ_SINGLE",
                "content_text": "No Options Q",
                "key": "A",
                "options": [],
            },
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(no_options.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(no_options.data["code"], "MISSING_OPTIONS")

    # ==========================================================================
    # 4. Examinations: Lifecycle, Assignment, Publishing & Staff Preview
    # ==========================================================================
    def test_examination_lifecycle_and_publishing(self):
        # Empty question paper
        empty_qp = QuestionBank.all_objects.create(organization=self.org, name="Empty Paper")

        # 1. Create Exam with zero duration returns 400
        zero_dur = self.client.post(
            "/api/v1/examinations/",
            {"name": "Zero Exam", "duration_minutes": 0},
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(zero_dur.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(zero_dur.data["code"], "INVALID_DURATION")

        # 2. Inverted time window returns 400
        inv_win = self.client.post(
            "/api/v1/examinations/",
            {
                "name": "Time Travel Exam",
                "duration_minutes": 60,
                "start_window": "2026-12-31T12:00:00Z",
                "end_window": "2026-12-01T12:00:00Z",
            },
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(inv_win.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(inv_win.data["code"], "INVALID_WINDOW")

        # 3. Create Valid Exam linked to empty paper
        exam_res = self.client.post(
            "/api/v1/examinations/",
            {"name": "Annual Final Exam", "question_paper_id": str(empty_qp.id), "duration_minutes": 180},
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(exam_res.status_code, status.HTTP_201_CREATED)
        eid = exam_res.data["id"]

        # 4. Publishing empty exam returns 400 EMPTY_EXAM
        pub_fail = self.client.post(f"/api/v1/examinations/{eid}/publish/", **self.tenant_headers)
        self.assertEqual(pub_fail.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(pub_fail.data["code"], "EMPTY_EXAM")

        # 5. Add a question to the paper
        Question.objects.create(
            question_bank=empty_qp,
            question_number=1,
            question_type=QuestionType.MCQ_SINGLE,
            content_text="Sample Q",
            key="A",
            positive_marks=4.0,
            negative_marks=1.0,
        )

        # 6. Candidate Assignment
        assign_res = self.client.post(
            f"/api/v1/examinations/{eid}/assign-candidates/",
            {"student_ids": ["student_alpha", "student_beta"]},
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(assign_res.status_code, status.HTTP_200_OK)
        self.assertEqual(assign_res.data["assigned_count"], 2)

        # 7. Assignment to nonexistent exam returns 404
        nonexist_res = self.client.post(
            f"/api/v1/examinations/{uuid.uuid4()}/assign-candidates/",
            {"student_ids": ["student_alpha"]},
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(nonexist_res.status_code, status.HTTP_404_NOT_FOUND)

        # 8. Publish Exam successfully
        pub_success = self.client.post(f"/api/v1/examinations/{eid}/publish/", **self.tenant_headers)
        self.assertEqual(pub_success.status_code, status.HTTP_200_OK)
        self.assertEqual(pub_success.data["status"], "PUBLISHED")

        # Verify paper is now locked (cannot add more questions)
        lock_res = self.client.post(
            f"/api/v1/question-papers/{empty_qp.id}/questions/",
            {"question_type": "MCQ_SINGLE", "key": "A", "options": [{"key": "A", "text": "1"}]},
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(lock_res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(lock_res.data["code"], "LOCKED")

        # 9. Staff Preview
        preview_res = self.client.get(f"/api/v1/examinations/{eid}/preview/", **self.tenant_headers)
        self.assertEqual(preview_res.status_code, status.HTTP_200_OK)
        self.assertEqual(preview_res.data["status"], "SUCCESS")
        self.assertTrue(len(preview_res.data["questions"]) >= 1)

    # ==========================================================================
    # 5. Notices: Broadcast & Active Filtering
    # ==========================================================================
    def test_notices_creation_and_filtering(self):
        batch = Batch.all_objects.create(organization=self.org, name="Notice Batch", code="NB01")
        res = self.client.post(
            "/api/v1/notices/",
            {
                "title": "Admit Cards Released",
                "content": "Please download your admit card before Friday.",
                "target_batch_ids": [str(batch.id)],
                "is_active": True,
            },
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        notice_id = res.data["id"]

        # List active notices
        list_res = self.client.get("/api/v1/notices/?active=true", **self.tenant_headers)
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertTrue(any(n["id"] == notice_id for n in list_res.data["notices"]))
