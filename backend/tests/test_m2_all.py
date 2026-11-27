import io
import uuid
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from apps.organizations.models import Organization, Batch, ExaminationCenter, StudentBatchEnrollment
from apps.accounts.models import User, UserRole, UserProfile, FacultyProfile
from apps.question_bank.models import QuestionBank, Question, Option, QuestionType
from apps.examinations.models import (
    CandidateAssignment, Examination, ExaminationQuestion, ExaminationSection, ExaminationStatus,
)
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

    def test_referenced_paper_and_question_cannot_be_deleted(self):
        paper = QuestionBank.all_objects.create(organization=self.org, name="Protected paper")
        question = Question.objects.create(
            question_bank=paper, question_type=QuestionType.SUBJECTIVE,
            content_text="Explain your answer.",
        )
        exam = Examination.all_objects.create(organization=self.org, name="Exam", question_paper=paper)
        section = ExaminationSection.objects.create(exam=exam, title="Section")
        ExaminationQuestion.objects.create(exam_section=section, question=question)

        for resource, pk in (("question-papers", paper.pk), ("questions", question.pk)):
            with self.subTest(resource=resource):
                response = self.client.delete(f"/api/v1/{resource}/{pk}/", **self.tenant_headers)
                self.assertEqual(response.status_code, status.HTTP_409_CONFLICT, response.data)

        self.assertTrue(QuestionBank.all_objects.filter(pk=paper.pk).exists())
        self.assertTrue(Question.objects.filter(pk=question.pk).exists())

    def test_roster_creation_rejects_malformed_batch_and_centre_ids(self):
        for resource, invalid_fields in (
            ("students", {"batch_id": "invalid", "centre_id": "invalid"}),
            ("faculty", {"batch_ids": ["invalid"], "centre_ids": ["invalid"]}),
        ):
            for field, value in invalid_fields.items():
                with self.subTest(resource=resource, field=field):
                    response = self.client.post(
                        f"/api/v1/users/{resource}/",
                        {"name": "Invalid assignment", "roll_number": "R1", field: value},
                        format="json", **self.tenant_headers,
                    )
                    self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
                    self.assertIn(field, response.data)
        self.assertFalse(User.objects.filter(organization=self.org).exclude(pk=self.admin_user.pk).exists())

    def test_exam_updates_validate_duration_and_effective_window(self):
        exam = Examination.all_objects.create(
            organization=self.org, name="Exam",
            start_window="2026-11-28T10:00:00Z", end_window="2026-11-28T11:00:00Z",
        )
        url = f"/api/v1/examinations/{exam.pk}/"
        cases = (
            (self.client.put, {"name": "Exam", "duration_minutes": 1441}, "duration_minutes"),
            (self.client.patch, {"duration_minutes": 0}, "duration_minutes"),
            (self.client.patch, {"start_window": "2026-11-28T11:00:00Z"}, "end_window"),
            (self.client.put, {"name": "Exam", "end_window": "2026-11-28T09:00:00Z"}, "end_window"),
        )
        for update, payload, field in cases:
            with self.subTest(payload=payload):
                response = update(url, payload, format="json", **self.tenant_headers)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
                self.assertIn(field, response.data)

        for duration in (1, 1440):
            response = self.client.patch(
                url, {"duration_minutes": duration, "start_window": None},
                format="json", **self.tenant_headers,
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
            self.assertEqual(response.data["duration_minutes"], duration)
            self.assertIsNone(response.data["start_window"])

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

    def test_scoped_batch_and_center_urls_match_active_tenant(self):
        other_org_id = uuid.uuid4()
        for model, resource in ((Batch, "batches"), (ExaminationCenter, "centers")):
            record = model.all_objects.create(organization=self.org, name="Local", code="LOCAL")
            for org_id, expected in (
                (self.org.pk, status.HTTP_200_OK),
                (other_org_id, status.HTTP_403_FORBIDDEN),
            ):
                url = f"/api/v1/organizations/{org_id}/{resource}/"
                for path in (url, f"{url}{record.pk}/"):
                    with self.subTest(path=path):
                        response = self.client.get(path, **self.tenant_headers)
                        self.assertEqual(response.status_code, expected)

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

    def test_normalized_codes_conflict_on_create_and_update(self):
        for model, resource in ((Batch, "batches"), (ExaminationCenter, "centers")):
            with self.subTest(resource=resource):
                model.all_objects.create(organization=self.org, name="First", code=" EXISTING ")
                other = model.all_objects.create(organization=self.org, name="Second", code="SECOND")
                url = f"/api/v1/organizations/{resource}/"
                payload = {"name": "Duplicate", "code": " existing ", "capacity": 50}
                create = self.client.post(url, payload, format="json", **self.tenant_headers)
                update = self.client.patch(
                    f"{url}{other.pk}/", {"code": " existing "}, format="json", **self.tenant_headers,
                )
                for response in (create, update):
                    self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
                    self.assertEqual(response.data["code"], "DUPLICATE_CODE")
                other.refresh_from_db()
                self.assertEqual(other.code, "SECOND")

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

    def test_bulk_csv_rejects_unterminated_quote_before_writing(self):
        Batch.all_objects.create(organization=self.org, name="Existing Batch", code="CSV01")
        response = self.client.post(
            "/api/v1/users/students/bulk-upload/",
            data=b'RollNumber,Name,BatchCode,CentreCode\nA1,First,CSV01,NEWCENTER\nA2,"Unterminated',
            content_type="text/csv",
            **self.tenant_headers,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "MALFORMED_CSV")
        self.assertEqual(response.data["created_count"], 0)
        self.assertFalse(User.objects.filter(organization=self.org, role=UserRole.STUDENT).exists())
        self.assertFalse(ExaminationCenter.all_objects.filter(organization=self.org, code="NEWCENTER").exists())

    def test_bulk_csv_missing_batch_rolls_back_all_rows(self):
        Batch.all_objects.create(organization=self.org, name="Existing Batch", code="CSV01")
        other_org = Organization.objects.create(name="Other Institute", slug="other-institute")
        Batch.all_objects.create(organization=other_org, name="Other Batch", code="MISSING")
        csv_data = (
            "RollNumber,Name,Email,BatchCode,CentreCode\n"
            "A1,First Student,first@apex.edu,CSV01,NEWCENTER\n"
            "A2,Second Student,second@apex.edu,MISSING,NEWCENTER\n"
        )
        response = self.client.post(
            "/api/v1/users/students/bulk-upload/",
            data=csv_data.encode(), content_type="text/csv", **self.tenant_headers,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["created_count"], 0)
        self.assertIn("Row 3", response.data["errors"][0])
        self.assertIn("MISSING", response.data["errors"][0])
        self.assertFalse(User.objects.filter(organization=self.org, role=UserRole.STUDENT).exists())
        self.assertFalse(Batch.all_objects.filter(organization=self.org, code="MISSING").exists())
        self.assertFalse(ExaminationCenter.all_objects.filter(organization=self.org, code="NEWCENTER").exists())

    # ==========================================================================
    # 3. Question Bank: Multi-Type Questions & Marking Schemes
    # ==========================================================================
    def test_empty_question_payload_does_not_create_default_bank(self):
        # The request clears tenant context before these database assertions run.
        banks = QuestionBank.all_objects.filter(organization=self.org)
        self.assertEqual(banks.count(), 0)

        response = self.client.post(
            "/api/v1/questions/",
            {},
            format="json",
            **self.tenant_headers,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(banks.count(), 0)

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

    def test_question_updates_validate_marks_and_mcq_options(self):
        paper = QuestionBank.all_objects.create(organization=self.org, name="Question Validation")
        create_url = f"/api/v1/question-papers/{paper.pk}/questions/"
        options = [{"key": "A", "text": "First"}, {"key": "B", "text": "Second"}]
        payload = {"question_type": "MCQ_SINGLE", "cmk": 4, "imk": 2, "options": options}
        for invalid_options in (options[:1], options):
            response = self.client.post(
                create_url, {**payload, "options": invalid_options}, format="json", **self.tenant_headers,
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        created = self.client.post(create_url, {**payload, "key": "A"}, format="json", **self.tenant_headers)
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        detail_url = f"/api/v1/questions/{created.data['id']}/"
        for invalid_update in ({"imk": 5}, {"cmk": 1}, {"options": options[:1]}, {
            "key": "", "options": options,
        }):
            response = self.client.patch(detail_url, invalid_update, format="json", **self.tenant_headers)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        updated = self.client.patch(
            detail_url, {"key": "B", "options": options}, format="json", **self.tenant_headers,
        )
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual([o["key"] for o in updated.data["options"] if o["is_correct"]], ["B"])

    def test_single_mcq_rejects_invalid_options_on_create_and_update(self):
        paper = QuestionBank.all_objects.create(organization=self.org, name="Single MCQ Validation")
        create_url = f"/api/v1/question-papers/{paper.pk}/questions/"
        options = [{"key": "A", "text": "First"}, {"key": "B", "text": "Second"}]
        payload = {"question_type": 1, "key": "A", "options": options, "content_text": "Choose one."}
        created = self.client.post(create_url, payload, format="json", **self.tenant_headers)
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        detail_url = f"/api/v1/questions/{created.data['id']}/"
        invalid_options = (
            [{"key": "A", "text": " \t"}, options[1]],
            [{"key": "A"}, options[1]],
            [dict(option, is_correct=True) for option in options],
            [dict(option, is_correct=False) for option in options],
        )
        for request, url, fields in (
            (self.client.post, create_url, payload),
            (self.client.put, detail_url, {**payload, "question_bank": str(paper.pk)}),
            (self.client.patch, detail_url, {}),
        ):
            for invalid in invalid_options:
                with self.subTest(method=request.__name__, options=invalid):
                    response = request(url, {**fields, "options": invalid}, format="json", **self.tenant_headers)
                    self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                    if request != self.client.post:
                        self.assertIn("options", response.data)

    def test_single_mcq_syncs_key_and_option_correctness(self):
        paper = QuestionBank.all_objects.create(organization=self.org, name="Single MCQ Key Sync")
        create_url = f"/api/v1/question-papers/{paper.pk}/questions/"
        options = [
            {"key": "A", "text": "First", "is_correct": True},
            {"key": "B", "text": "Second", "is_correct": False},
        ]
        created = self.client.post(
            create_url, {"question_type": 1, "options": options}, format="json", **self.tenant_headers,
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data["question"]["key"], "A")
        detail_url = f"/api/v1/questions/{created.data['id']}/"

        updated = self.client.patch(detail_url, {"key": "B"}, format="json", **self.tenant_headers)
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data["key"], "B")
        self.assertEqual({o["key"]: o["is_correct"] for o in updated.data["options"]}, {"A": False, "B": True})
        self.assertEqual(
            [o["id"] for o in updated.data["options"]],
            [o["id"] for o in created.data["question"]["options"]],
        )

        updated = self.client.patch(detail_url, {"options": options}, format="json", **self.tenant_headers)
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        saved = self.client.get(detail_url, **self.tenant_headers)
        self.assertEqual(saved.data["key"], "A")
        self.assertEqual({o["key"]: o["is_correct"] for o in saved.data["options"]}, {"A": True, "B": False})

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

        direct_update = self.client.patch(
            f"/api/v1/examinations/{eid}/", {"status": "PUBLISHED"}, format="json", **self.tenant_headers,
        )
        self.assertEqual(direct_update.status_code, status.HTTP_200_OK)
        self.assertEqual(direct_update.data["status"], "DRAFT")

        exam = Examination.all_objects.filter(pk=eid)
        boundary = timezone.now()
        exam.update(start_window=boundary, end_window=boundary)
        invalid_window = self.client.post(f"/api/v1/examinations/{eid}/publish/", **self.tenant_headers)
        self.assertEqual(invalid_window.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(invalid_window.data["code"], "INVALID_WINDOW")
        exam.update(start_window=None, end_window=None)

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

        for username in ("student_alpha", "student_beta"):
            User.objects.create_user(username=username, role=UserRole.STUDENT, organization=self.org)

        # 6. Candidate Assignment
        assign_res = self.client.post(
            f"/api/v1/examinations/{eid}/assign-candidates/",
            {"student_ids": ["student_alpha", "student_beta"]},
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(assign_res.status_code, status.HTTP_200_OK)
        self.assertEqual(assign_res.data["assigned_count"], 2)

        repeat = self.client.post(
            f"/api/v1/examinations/{eid}/assign-candidates/",
            {"student_ids": ["student_alpha", "unknown_student"]},
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(repeat.status_code, status.HTTP_200_OK)
        self.assertEqual(repeat.data["assigned_count"], 0)

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

        republish = self.client.post(f"/api/v1/examinations/{eid}/publish/", **self.tenant_headers)
        self.assertEqual(republish.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(republish.data["code"], "INVALID_STATUS")

        paper_url = f"/api/v1/question-papers/{empty_qp.pk}/"
        for update in (self.client.put, self.client.patch):
            response = update(paper_url, {"name": "Renamed"}, format="json", **self.tenant_headers)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data["code"], "LOCKED")

        # Verify paper is now locked (cannot add more questions)
        lock_res = self.client.post(
            f"/api/v1/question-papers/{empty_qp.id}/questions/",
            {"question_type": "MCQ_SINGLE", "key": "A", "options": [{"key": "A", "text": "1"}]},
            format="json",
            **self.tenant_headers,
        )
        self.assertEqual(lock_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(lock_res.data["code"], "LOCKED")

        for field in ("question_paper", "question_paper_id"):
            response = self.client.patch(
                f"/api/v1/examinations/{eid}/", {field: None}, format="json", **self.tenant_headers,
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        empty_qp.refresh_from_db()
        self.assertTrue(empty_qp.is_locked)
        question_url = f"/api/v1/questions/{empty_qp.questions.get().pk}/"
        section_url = f"/api/v1/question-papers/{empty_qp.pk}/sections/"
        for response in (
            self.client.patch(question_url, {"cmk": 5}, format="json", **self.tenant_headers),
            self.client.delete(question_url, **self.tenant_headers),
            self.client.post(section_url, {"name": "Locked Section"}, format="json", **self.tenant_headers),
        ):
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data["code"], "LOCKED")

        # 9. Staff Preview
        preview_res = self.client.get(f"/api/v1/examinations/{eid}/preview/", **self.tenant_headers)
        self.assertEqual(preview_res.status_code, status.HTTP_200_OK)
        self.assertEqual(preview_res.data["status"], "SUCCESS")
        self.assertTrue(len(preview_res.data["questions"]) >= 1)
        for role, expected in (
            (UserRole.SUPERADMIN, status.HTTP_200_OK),
            (UserRole.FACULTY, status.HTTP_200_OK),
            (UserRole.STUDENT, status.HTTP_403_FORBIDDEN),
        ):
            with self.subTest(role=role):
                viewer = User.objects.create_user(username=role, role=role, organization=self.org)
                self.client.force_authenticate(user=viewer)
                response = self.client.get(f"/api/v1/examinations/{eid}/preview/", **self.tenant_headers)
                self.assertEqual(response.status_code, expected)

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

    def test_staff_authoring_and_csv_roster_to_candidate_submission(self):
        def staff_post(path, data=None, format="json", expected=200):
            response = self.client.post(f"/api/v1/{path}", data, format=format, **self.tenant_headers)
            self.assertEqual(response.status_code, expected, response.data)
            return response.data

        batch = staff_post("organizations/batches/", {"name": "Lab", "code": "LAB"}, expected=201)
        center = staff_post("organizations/centers/", {"name": "North", "code": "NORTH", "capacity": 20}, expected=201)
        imported = staff_post("users/students/bulk-upload/", {
            "file": SimpleUploadedFile("candidates.csv", (
                b"RollNumber,Name,Email,BatchCode,CentreCode,Password\n"
                b"100,Candidate One,candidate@example.org,LAB,NORTH,CandidatePassword123!\n"
            ), content_type="text/csv"),
        }, format="multipart")
        self.assertEqual(imported["created_count"], 1)

        student = User.objects.get(email="candidate@example.org")
        other_batch = Batch.all_objects.create(organization=self.org, name="Other", code="OTHER")
        StudentBatchEnrollment.objects.create(student=student, batch=other_batch, roll_number="001")
        roster = self.client.get(
            "/api/v1/users/students/", {"batch_id": batch["id"], "centre_id": center["id"]},
            **self.tenant_headers,
        )
        self.assertEqual(roster.status_code, 200)
        row, = roster.data["students"]
        self.assertEqual((row["roll_number"], row["batch_name"], row["centre_name"]), ("100", "Lab", "North"))

        paper = staff_post("question-papers/", {"name": "Algebra"}, expected=201)
        formula = r"Simplify $\frac{x^2}{x}$"
        question = staff_post(f"question-papers/{paper['id']}/questions/", {
            "section": "Algebra", "question_type": "MCQ_SINGLE", "content_text": formula,
            "key": "A", "positive_marks": 4, "negative_marks": 0,
            "options": [{"key": "A", "text": "$x$", "is_correct": True},
                        {"key": "B", "text": "$x^2$", "is_correct": False}],
        }, expected=201)["question"]
        exam = staff_post("examinations/", {
            "name": "Algebra CBT", "question_paper_id": paper["id"], "duration_minutes": 15,
        }, expected=201)
        exam_id = exam["id"]
        assignments = {"batch_ids": [batch["id"]], "centre_ids": [center["id"]]}
        self.assertEqual(staff_post(f"examinations/{exam_id}/assign-candidates/", assignments)["assigned_count"], 2)
        self.assertEqual(staff_post(f"examinations/{exam_id}/assign-candidates/", assignments)["assigned_count"], 0)

        candidate = APIClient()
        login = candidate.post("/api/v1/auth/login/", {
            "username": "candidate@example.org", "password": "CandidatePassword123!",
        }, format="json")
        self.assertEqual(login.status_code, 200, login.data)
        self.assertEqual(login.data["user"]["role"], "STUDENT")
        candidate.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}", **self.tenant_headers)

        portal_url = "/api/v1/student/examinations/"
        lobby_url = f"{portal_url}{exam_id}/"
        start_url = "/api/v1/student/attempts/start/"
        start_body = {"exam_id": exam_id}
        self.assertEqual(candidate.get(portal_url).data["examinations"], [])
        self.assertEqual(candidate.post(start_url, start_body, format="json").status_code, 404)

        staff_post(f"examinations/{exam_id}/publish/")
        visible, = candidate.get(portal_url).json()["examinations"]
        self.assertEqual(visible["id"], exam_id)
        self.assertEqual(float(visible["total_marks"]), 4)
        lobby = candidate.get(lobby_url)
        self.assertEqual(lobby.status_code, 200)
        self.assertNotIn("questions", lobby.data)
        self.assertEqual(candidate.get(f"/api/v1/examinations/{exam_id}/preview/").status_code, 403)

        outsider = User.objects.create_user(username="unassigned", role=UserRole.STUDENT, organization=self.org)
        unassigned = APIClient()
        unassigned.force_authenticate(outsider)
        self.assertEqual(unassigned.get(lobby_url, **self.tenant_headers).status_code, 404)
        self.assertEqual(unassigned.post(start_url, start_body, format="json", **self.tenant_headers).status_code, 404)

        start = candidate.post(start_url, start_body, format="json")
        self.assertEqual(start.status_code, 200, start.data)
        self.assertGreater(start.data["remaining_seconds"], 0)
        delivered, = start.data["sections"][0]["questions"]
        self.assertEqual(delivered["id"], question["id"])
        self.assertEqual(delivered["content_text"], formula)
        self.assertEqual([opt["key"] for opt in delivered["options"]], ["A", "B"])
        self.assertNotIn("key", delivered)
        self.assertNotIn("is_correct", delivered["options"][0])
        attempt_url = f"/api/v1/student/attempts/{start.data['attempt_id']}/"
        heartbeat = candidate.post(f"{attempt_url}heartbeat/", {}, format="json")
        self.assertEqual(heartbeat.status_code, 200)
        self.assertGreater(heartbeat.data["remaining_seconds"], 0)

        for options in (["A"], [], ["B"]):
            saved = candidate.post(f"{attempt_url}responses/", {
                "question_id": question["id"], "selected_options": options,
            }, format="json")
            self.assertEqual(saved.status_code, 200, saved.data)
            resume = candidate.get(f"{attempt_url}resume/")
            self.assertEqual(resume.data["existing_responses"][question["id"]]["selected_options"], options)

        submit = candidate.post(f"{attempt_url}submit/", {"submission_reason": "MANUAL_SUBMIT"}, format="json")
        self.assertEqual(submit.status_code, 200, submit.data)
        self.assertEqual(submit.data["submission_status"], "SUBMITTED")
