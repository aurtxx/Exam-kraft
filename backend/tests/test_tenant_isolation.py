from django.test import TestCase, RequestFactory
from apps.organizations.models import Organization, Batch, ExaminationCenter
from apps.organizations.context import set_current_tenant, clear_current_tenant
from apps.organizations.middleware import TenantMiddleware
from apps.accounts.models import User, UserRole


class TenantIsolationTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = TenantMiddleware(lambda req: None)

        self.org_a = Organization.objects.create(name="Tenant Alpha", slug="alpha", domain="alpha.ezexam.in")
        self.org_b = Organization.objects.create(name="Tenant Beta", slug="beta", domain="beta.ezexam.in")

        # Create batches for Org A
        self.batch_a1 = Batch.all_objects.create(organization=self.org_a, name="Batch Alpha 1", code="BA01")
        self.batch_a2 = Batch.all_objects.create(organization=self.org_a, name="Batch Alpha 2", code="BA02")

        # Create batches for Org B
        self.batch_b1 = Batch.all_objects.create(organization=self.org_b, name="Batch Beta 1", code="BB01")

        # Create centers
        self.center_a = ExaminationCenter.all_objects.create(
            organization=self.org_a, name="Alpha Lab", code="AL01", capacity=50
        )
        self.center_b = ExaminationCenter.all_objects.create(
            organization=self.org_b, name="Beta Lab", code="BL01", capacity=100
        )

    def tearDown(self):
        clear_current_tenant()

    def test_tenant_manager_scoping_alpha(self):
        set_current_tenant(self.org_a)
        batches = list(Batch.objects.all())
        centers = list(ExaminationCenter.objects.all())

        self.assertEqual(len(batches), 2)
        self.assertIn(self.batch_a1, batches)
        self.assertIn(self.batch_a2, batches)
        self.assertNotIn(self.batch_b1, batches)

        self.assertEqual(len(centers), 1)
        self.assertIn(self.center_a, centers)
        self.assertNotIn(self.center_b, centers)

    def test_tenant_manager_scoping_beta(self):
        set_current_tenant(self.org_b)
        batches = list(Batch.objects.all())
        centers = list(ExaminationCenter.objects.all())

        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0], self.batch_b1)
        self.assertNotIn(self.batch_a1, batches)

        self.assertEqual(len(centers), 1)
        self.assertEqual(centers[0], self.center_b)
        self.assertNotIn(self.center_a, centers)

    def test_tenant_manager_no_active_tenant_returns_all(self):
        clear_current_tenant()
        batches = list(Batch.objects.all())
        self.assertEqual(len(batches), 3)

    def test_all_objects_manager_bypasses_filter(self):
        set_current_tenant(self.org_a)
        all_batches = list(Batch.all_objects.all())
        self.assertEqual(len(all_batches), 3)

    def test_middleware_resolves_tenant_from_header_slug(self):
        request = self.factory.get('/', HTTP_X_TENANT_ID='beta')
        self.middleware.process_request(request)
        self.assertEqual(request.tenant, self.org_b)
        # Verify context is set
        batches = list(Batch.objects.all())
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0].code, "BB01")

        # Cleanup
        self.middleware.process_response(request, None)

    def test_middleware_resolves_tenant_from_header_uuid(self):
        request = self.factory.get('/', HTTP_X_TENANT_ID=str(self.org_a.id))
        self.middleware.process_request(request)
        self.assertEqual(request.tenant, self.org_a)

        batches = list(Batch.objects.all())
        self.assertEqual(len(batches), 2)

        self.middleware.process_response(request, None)

    def test_middleware_resolves_tenant_from_subdomain(self):
        request = self.factory.get('/', HTTP_HOST='alpha.ezexam.in')
        self.middleware.process_request(request)
        self.assertEqual(request.tenant, self.org_a)

        self.middleware.process_response(request, None)
