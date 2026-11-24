from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken
from apps.organizations.models import Organization
from apps.accounts.models import User, UserProfile, UserRole


class AuthEndpointsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(
            name="Apex Academy",
            slug="apex",
            settings={"primary_color": "#2d8df1"}
        )
        self.user = User.objects.create_user(
            username="admin_user",
            password="SecurePassword123!",
            email="admin@apex.edu",
            phone="+919876543210",
            role=UserRole.ORG_ADMIN,
            organization=self.org
        )
        UserProfile.objects.create(
            user=self.user,
            full_name="Prof. Admin"
        )

    def test_login_with_username_success(self):
        url = reverse('auth-login')
        response = self.client.post(url, {
            'username': 'admin_user',
            'password': 'SecurePassword123!'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'SUCCESS')
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['username'], 'admin_user')
        self.assertEqual(response.data['user']['role'], UserRole.ORG_ADMIN)
        self.assertEqual(response.data['organization']['slug'], 'apex')

        # Check JWT claims
        token = AccessToken(response.data['access'])
        self.assertEqual(token['username'], 'admin_user')
        self.assertEqual(token['role'], UserRole.ORG_ADMIN)
        self.assertEqual(token['org_id'], str(self.org.id))

    def test_login_with_email_success(self):
        url = reverse('auth-login')
        response = self.client.post(url, {
            'username': 'admin@apex.edu',
            'password': 'SecurePassword123!'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'SUCCESS')
        self.assertEqual(response.data['user']['username'], 'admin_user')

    def test_login_with_phone_success(self):
        url = reverse('auth-login')
        response = self.client.post(url, {
            'username': '+919876543210',
            'password': 'SecurePassword123!'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'SUCCESS')
        self.assertEqual(response.data['user']['username'], 'admin_user')

    def test_login_invalid_password(self):
        url = reverse('auth-login')
        response = self.client.post(url, {
            'username': 'admin_user',
            'password': 'WrongPassword!'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['code'], 'INVALID_CREDENTIALS')

    def test_login_disabled_account(self):
        self.user.is_active = False
        self.user.save()

        url = reverse('auth-login')
        response = self.client.post(url, {
            'username': 'admin_user',
            'password': 'SecurePassword123!'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh(self):
        login_res = self.client.post(reverse('auth-login'), {
            'username': 'admin_user',
            'password': 'SecurePassword123!'
        }, format='json')

        refresh_token = login_res.data['refresh']

        refresh_url = reverse('token-refresh')
        response = self.client.post(refresh_url, {
            'refresh': refresh_token
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_me_authenticated(self):
        login_res = self.client.post(reverse('auth-login'), {
            'username': 'admin_user',
            'password': 'SecurePassword123!'
        }, format='json')
        access_token = login_res.data['access']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.get(reverse('auth-me'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'SUCCESS')
        self.assertEqual(response.data['user']['username'], 'admin_user')
        self.assertEqual(response.data['user']['profile']['full_name'], 'Prof. Admin')
        self.assertEqual(response.data['organization']['name'], 'Apex Academy')

    def test_me_unauthenticated_fails(self):
        response = self.client.get(reverse('auth-me'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_blacklists_token(self):
        login_res = self.client.post(reverse('auth-login'), {
            'username': 'admin_user',
            'password': 'SecurePassword123!'
        }, format='json')
        access_token = login_res.data['access']
        refresh_token = login_res.data['refresh']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        logout_res = self.client.post(reverse('auth-logout'), {
            'refresh': refresh_token
        }, format='json')

        self.assertEqual(logout_res.status_code, status.HTTP_200_OK)
        self.assertEqual(logout_res.data['status'], 'SUCCESS')

        # Using blacklisted refresh token should now fail
        refresh_res = self.client.post(reverse('token-refresh'), {
            'refresh': refresh_token
        }, format='json')
        self.assertEqual(refresh_res.status_code, status.HTTP_401_UNAUTHORIZED)
