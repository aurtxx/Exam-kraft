from django.test import TestCase, RequestFactory
from rest_framework import status
from rest_framework.test import APIClient
from apps.organizations.models import Organization
from apps.accounts.models import User, UserRole
from apps.question_bank.models import Option, Question, QuestionBank, QuestionType, Section, Tag
from apps.accounts.permissions import (
    IsSuperAdmin,
    IsOrgAdmin,
    IsFaculty,
    IsStudent,
    IsTenantMember,
    IsOrgAdminOrReadOnly,
)


class RBACPermissionsTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.org1 = Organization.objects.create(name="Org One", slug="org1")
        self.org2 = Organization.objects.create(name="Org Two", slug="org2")

        self.superadmin = User.objects.create_superuser(
            username="super", password="password123"
        )
        self.orgadmin = User.objects.create_user(
            username="orgadmin", password="password123", role=UserRole.ORG_ADMIN, organization=self.org1
        )
        self.faculty = User.objects.create_user(
            username="faculty", password="password123", role=UserRole.FACULTY, organization=self.org1
        )
        self.student = User.objects.create_user(
            username="student", password="password123", role=UserRole.STUDENT, organization=self.org1
        )
        self.student_other_org = User.objects.create_user(
            username="student2", password="password123", role=UserRole.STUDENT, organization=self.org2
        )

    def _make_request(self, user, tenant=None):
        request = self.factory.get('/')
        request.user = user
        request.tenant = tenant or getattr(user, 'organization', None)
        return request

    def test_is_superadmin_permission(self):
        perm = IsSuperAdmin()
        self.assertTrue(perm.has_permission(self._make_request(self.superadmin), None))
        self.assertFalse(perm.has_permission(self._make_request(self.orgadmin), None))
        self.assertFalse(perm.has_permission(self._make_request(self.faculty), None))
        self.assertFalse(perm.has_permission(self._make_request(self.student), None))

    def test_is_orgadmin_permission(self):
        perm = IsOrgAdmin()
        self.assertTrue(perm.has_permission(self._make_request(self.superadmin), None))
        self.assertTrue(perm.has_permission(self._make_request(self.orgadmin), None))
        self.assertFalse(perm.has_permission(self._make_request(self.faculty), None))
        self.assertFalse(perm.has_permission(self._make_request(self.student), None))

    def test_is_faculty_permission(self):
        perm = IsFaculty()
        self.assertTrue(perm.has_permission(self._make_request(self.superadmin), None))
        self.assertTrue(perm.has_permission(self._make_request(self.orgadmin), None))
        self.assertTrue(perm.has_permission(self._make_request(self.faculty), None))
        self.assertFalse(perm.has_permission(self._make_request(self.student), None))

    def test_is_student_permission(self):
        perm = IsStudent()
        self.assertFalse(perm.has_permission(self._make_request(self.superadmin), None))
        self.assertFalse(perm.has_permission(self._make_request(self.orgadmin), None))
        self.assertFalse(perm.has_permission(self._make_request(self.faculty), None))
        self.assertTrue(perm.has_permission(self._make_request(self.student), None))

    def test_is_tenant_member_permission(self):
        perm = IsTenantMember()

        # Superadmin can access any tenant
        req_super = self._make_request(self.superadmin, tenant=self.org1)
        self.assertTrue(perm.has_permission(req_super, None))

        # OrgAdmin of org1 accessing org1
        req_org1 = self._make_request(self.orgadmin, tenant=self.org1)
        self.assertTrue(perm.has_permission(req_org1, None))

        # OrgAdmin of org1 attempting to access org2 tenant
        req_cross = self._make_request(self.orgadmin, tenant=self.org2)
        self.assertFalse(perm.has_permission(req_cross, None))

    def test_is_tenant_member_resolves_when_tenant_is_none(self):
        perm = IsTenantMember()
        # Request with tenant explicitly None on request object
        req = self.factory.get('/')
        req.user = self.student
        req.tenant = None

        self.assertTrue(perm.has_permission(req, None))
        self.assertEqual(req.tenant, self.org1)

    def test_is_tenant_member_fails_when_user_has_no_org(self):
        perm = IsTenantMember()
        user_no_org = User.objects.create_user(
            username="no_org_user", password="password123", role=UserRole.STUDENT, organization=None
        )
        req = self.factory.get('/')
        req.user = user_no_org
        req.tenant = None

        self.assertFalse(perm.has_permission(req, None))

    def test_is_orgadmin_or_read_only_permission(self):
        perm = IsOrgAdminOrReadOnly()

        # GET requests (safe methods) allowed for all roles
        for user in [self.student, self.faculty, self.orgadmin, self.superadmin]:
            req_get = self.factory.get('/')
            req_get.user = user
            self.assertTrue(perm.has_permission(req_get, None))

        # Write requests denied for Student and Faculty
        for method in ['post', 'put', 'patch', 'delete']:
            req_student = getattr(self.factory, method)('/')
            req_student.user = self.student
            self.assertFalse(perm.has_permission(req_student, None))

            req_faculty = getattr(self.factory, method)('/')
            req_faculty.user = self.faculty
            self.assertFalse(perm.has_permission(req_faculty, None))

        # Write requests allowed for OrgAdmin and SuperAdmin
        for method in ['post', 'put', 'patch', 'delete']:
            req_admin = getattr(self.factory, method)('/')
            req_admin.user = self.orgadmin
            self.assertTrue(perm.has_permission(req_admin, None))

            req_super = getattr(self.factory, method)('/')
            req_super.user = self.superadmin
            self.assertTrue(perm.has_permission(req_super, None))


class QuestionBankAccessControlTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(
            name="Apex Institute",
            slug="apex-inst",
            domain="apex.ezexam.in",
        )
        self.other_org = Organization.objects.create(
            name="Other Institute",
            slug="other-inst",
            domain="other.ezexam.in",
        )
        self.tenant_headers = {"HTTP_X_TENANT_ID": str(self.org.id)}

        self.student = User.objects.create_user(
            username="student_qb",
            password="Password123!",
            role=UserRole.STUDENT,
            organization=self.org,
        )
        self.faculty = User.objects.create_user(
            username="faculty_qb",
            password="Password123!",
            role=UserRole.FACULTY,
            organization=self.org,
        )
        self.org_admin = User.objects.create_user(
            username="admin_qb",
            password="Password123!",
            role=UserRole.ORG_ADMIN,
            organization=self.org,
        )
        self.outsider_faculty = User.objects.create_user(
            username="outsider_faculty_qb",
            password="Password123!",
            role=UserRole.FACULTY,
            organization=self.other_org,
        )

        self.paper = QuestionBank.all_objects.create(
            organization=self.org,
            name="Confidential Mock Paper",
            exam_type="JEE-Main",
        )
        self.section = Section.all_objects.create(
            organization=self.org,
            question_bank=self.paper,
            name="Physics",
            code="PHY",
            order=1,
        )
        self.tag = Tag.all_objects.create(
            organization=self.org,
            name="Mechanics",
            slug="mechanics",
        )
        self.question = Question.objects.create(
            question_bank=self.paper,
            section=self.section,
            section_name="Physics",
            question_number=1,
            question_type=QuestionType.MCQ_SINGLE,
            content_text="Acceleration due to gravity on Earth?",
            key="B",
            explanation="Approximately 9.8 m/s^2.",
            positive_marks=4.0,
            negative_marks=1.0,
        )
        Option.objects.create(
            question=self.question,
            option_key="A",
            content_text="5.0 m/s^2",
            is_correct=False,
            order=1,
        )
        Option.objects.create(
            question=self.question,
            option_key="B",
            content_text="9.8 m/s^2",
            is_correct=True,
            order=2,
        )

    def test_student_denied_read_on_question_bank_and_question_endpoints(self):
        self.client.force_authenticate(user=self.student)
        endpoints = [
            "/api/v1/question-papers/",
            "/api/v1/question-banks/",
            f"/api/v1/question-papers/{self.paper.id}/",
            f"/api/v1/question-papers/{self.paper.id}/questions/",
            f"/api/v1/question-papers/{self.paper.id}/sections/",
            "/api/v1/question-papers/tags/",
            "/api/v1/questions/",
            f"/api/v1/questions/{self.question.id}/",
        ]
        for url in endpoints:
            with self.subTest(url=url):
                res = self.client.get(url, **self.tenant_headers)
                self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_read_question_bank_and_questions_with_keys(self):
        endpoints = [
            "/api/v1/question-papers/",
            f"/api/v1/question-papers/{self.paper.id}/",
            f"/api/v1/question-papers/{self.paper.id}/questions/",
            f"/api/v1/question-papers/{self.paper.id}/sections/",
            "/api/v1/question-papers/tags/",
            "/api/v1/questions/",
            f"/api/v1/questions/{self.question.id}/",
        ]
        for staff_user in (self.org_admin, self.faculty):
            self.client.force_authenticate(user=staff_user)
            for url in endpoints:
                with self.subTest(role=staff_user.role, url=url):
                    res = self.client.get(url, **self.tenant_headers)
                    self.assertEqual(res.status_code, status.HTTP_200_OK)

            q_res = self.client.get(
                f"/api/v1/question-papers/{self.paper.id}/questions/",
                **self.tenant_headers,
            )
            self.assertEqual(q_res.status_code, status.HTTP_200_OK)
            q_data = q_res.data["questions"][0]
            self.assertEqual(q_data["key"], "B")
            self.assertEqual(q_data["explanation"], "Approximately 9.8 m/s^2.")
            self.assertTrue(any(opt["is_correct"] for opt in q_data["options"]))

    def test_outsider_faculty_denied_on_other_tenant_question_bank(self):
        self.client.force_authenticate(user=self.outsider_faculty)
        res = self.client.get(f"/api/v1/question-papers/{self.paper.id}/questions/", **self.tenant_headers)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
