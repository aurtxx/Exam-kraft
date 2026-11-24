from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.organizations.models import Organization, Batch, ExaminationCenter
from apps.accounts.models import User, UserRole


class OrganizationEndpointsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(
            name="Apex Engineering Academy",
            slug="apex-eng",
            domain="apex-eng.ezexam.in",
            settings={"primary_color": "#2d8df1", "logo_url": "https://storage.provider.com/logo.png"}
        )

        self.org_admin = User.objects.create_user(
            username="orgadmin",
            password="SecurePass#2026",
            role=UserRole.ORG_ADMIN,
            organization=self.org
        )
        self.student = User.objects.create_user(
            username="student_user",
            password="SecurePass#2026",
            role=UserRole.STUDENT,
            organization=self.org
        )

        # Create sample batch and center
        Batch.all_objects.create(organization=self.org, name="Class 12 B", code="C12B")
        ExaminationCenter.all_objects.create(organization=self.org, name="North Hall", code="NH01", capacity=80)

    def test_get_current_organization_as_admin(self):
        self.client.force_authenticate(user=self.org_admin)
        url = reverse('org-current')
        response = self.client.get(url, HTTP_X_TENANT_ID=str(self.org.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'SUCCESS')
        self.assertEqual(response.data['organization']['name'], "Apex Engineering Academy")
        self.assertEqual(response.data['organization']['settings']['primary_color'], "#2d8df1")

    def test_patch_branding_as_org_admin_success(self):
        self.client.force_authenticate(user=self.org_admin)
        url = reverse('org-current')

        payload = {
            "name": "Apex National Institute",
            "settings": {
                "primary_color": "#1eaeff",
                "logo_url": "https://storage.provider.com/new-logo.png",
                "allow_student_signup": False
            }
        }
        response = self.client.patch(url, payload, format='json', HTTP_X_TENANT_ID=str(self.org.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'SUCCESS')
        self.assertEqual(response.data['organization']['name'], "Apex National Institute")
        self.assertEqual(response.data['organization']['settings']['primary_color'], "#1eaeff")
        self.assertEqual(response.data['organization']['settings']['allow_student_signup'], False)

        # Verify DB updated
        self.org.refresh_from_db()
        self.assertEqual(self.org.name, "Apex National Institute")
        self.assertEqual(self.org.settings["primary_color"], "#1eaeff")

    def test_patch_branding_as_student_forbidden(self):
        self.client.force_authenticate(user=self.student)
        url = reverse('org-current')

        payload = {
            "name": "Hacked Name"
        }
        response = self.client.patch(url, payload, format='json', HTTP_X_TENANT_ID=str(self.org.id))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['code'], 'PERMISSION_DENIED')

    def test_get_select_fields(self):
        self.client.force_authenticate(user=self.org_admin)
        url = reverse('org-select-fields')
        response = self.client.get(url, HTTP_X_TENANT_ID=str(self.org.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'SUCCESS')
        self.assertIn('classes', response.data)
        self.assertIn('centres', response.data)
        self.assertEqual(len(response.data['classes']), 1)
        self.assertEqual(response.data['classes'][0]['code'], 'C12B')
        self.assertEqual(len(response.data['centres']), 1)
        self.assertEqual(response.data['centres'][0]['code'], 'NH01')

    def test_student_cannot_create_batch(self):
        self.client.force_authenticate(user=self.student)
        url = reverse('org-batches')
        payload = {"name": "Unauthorized Batch", "code": "UB01"}
        response = self.client.post(url, payload, format='json', HTTP_X_TENANT_ID=str(self.org.id))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['code'], 'PERMISSION_DENIED')

    def test_student_cannot_create_center(self):
        self.client.force_authenticate(user=self.student)
        url = reverse('org-centers')
        payload = {"name": "Unauthorized Center", "code": "UC01", "capacity": 100}
        response = self.client.post(url, payload, format='json', HTTP_X_TENANT_ID=str(self.org.id))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['code'], 'PERMISSION_DENIED')

    def test_org_admin_can_create_batch(self):
        self.client.force_authenticate(user=self.org_admin)
        url = reverse('org-batches')
        payload = {"name": "Class 11 A", "code": "C11A", "stream": "JEE_MAIN"}
        response = self.client.post(url, payload, format='json', HTTP_X_TENANT_ID=str(self.org.id))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'C11A')
        self.assertEqual(str(response.data['organization']), str(self.org.id))

    def test_org_admin_can_create_center(self):
        self.client.force_authenticate(user=self.org_admin)
        url = reverse('org-centers')
        payload = {"name": "South Wing Lab", "code": "SW01", "capacity": 120}
        response = self.client.post(url, payload, format='json', HTTP_X_TENANT_ID=str(self.org.id))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'SW01')
        self.assertEqual(str(response.data['organization']), str(self.org.id))

    def test_student_can_read_batches_and_centers(self):
        self.client.force_authenticate(user=self.student)
        url_b = reverse('org-batches')
        res_b = self.client.get(url_b, HTTP_X_TENANT_ID=str(self.org.id))
        self.assertEqual(res_b.status_code, status.HTTP_200_OK)
        self.assertTrue(len(res_b.data) >= 1)

        url_c = reverse('org-centers')
        res_c = self.client.get(url_c, HTTP_X_TENANT_ID=str(self.org.id))
        self.assertEqual(res_c.status_code, status.HTTP_200_OK)
        self.assertTrue(len(res_c.data) >= 1)
