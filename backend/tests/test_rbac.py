from django.test import TestCase, RequestFactory
from apps.organizations.models import Organization
from apps.accounts.models import User, UserRole
from apps.accounts.permissions import (
    IsSuperAdmin,
    IsOrgAdmin,
    IsFaculty,
    IsStudent,
    IsTenantMember,
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
