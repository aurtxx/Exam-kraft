import uuid
from django.test import TestCase
from django.db import IntegrityError, transaction
from apps.organizations.models import Organization, ExaminationCenter, Batch, StudentBatchEnrollment, BatchStream
from apps.accounts.models import User, UserProfile, UserRole


class DataModelsTestCase(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name="Apex Academy",
            slug="apex-academy",
            domain="apex.ezexam.in",
            settings={"primary_color": "#2d8df1", "logo_url": "https://example.com/logo.png"}
        )

    def test_organization_creation(self):
        self.assertIsInstance(self.org.id, uuid.UUID)
        self.assertEqual(self.org.name, "Apex Academy")
        self.assertEqual(self.org.slug, "apex-academy")
        self.assertEqual(self.org.settings["primary_color"], "#2d8df1")
        self.assertTrue(self.org.is_active)

    def test_organization_unique_slug(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Organization.objects.create(name="Another Org", slug="apex-academy")

    def test_user_creation_and_password_hashing(self):
        user = User.objects.create_user(
            username="faculty1",
            password="SecurePass#2026",
            email="faculty1@apex.edu",
            phone="+919876500001",
            role=UserRole.FACULTY,
            organization=self.org
        )
        self.assertIsInstance(user.id, uuid.UUID)
        self.assertNotEqual(user.password, "SecurePass#2026")
        self.assertTrue(user.check_password("SecurePass#2026"))
        self.assertFalse(user.check_password("WrongPassword"))
        self.assertEqual(user.role, UserRole.FACULTY)
        self.assertTrue(user.is_faculty)
        self.assertFalse(user.is_superadmin)

    def test_user_unique_username(self):
        User.objects.create_user(username="unique_user", password="password123")
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                User.objects.create_user(username="unique_user", password="password456")

    def test_user_profile_creation(self):
        user = User.objects.create_user(
            username="student_alan",
            password="password123",
            role=UserRole.STUDENT,
            organization=self.org
        )
        profile = UserProfile.objects.create(
            user=user,
            full_name="Alan Turing",
            parent_name="Julius Turing",
            parent_phone="+919999988888",
            metadata={"grade": "12", "section": "A"}
        )
        self.assertEqual(user.profile.full_name, "Alan Turing")
        self.assertEqual(user.profile.metadata["grade"], "12")
        self.assertEqual(profile.user, user)

    def test_examination_center_unique_composite(self):
        ExaminationCenter.objects.create(
            organization=self.org,
            name="Main Hall",
            code="MH01",
            capacity=100
        )
        # Duplicate code in same org should fail
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ExaminationCenter.objects.create(
                    organization=self.org,
                    name="Secondary Hall",
                    code="MH01",
                    capacity=50
                )

        # Same code in different org should succeed
        org2 = Organization.objects.create(name="Second Org", slug="second-org")
        center2 = ExaminationCenter.objects.create(
            organization=org2,
            name="Main Hall",
            code="MH01",
            capacity=50
        )
        self.assertEqual(center2.code, "MH01")

    def test_batch_unique_composite(self):
        Batch.objects.create(
            organization=self.org,
            name="JEE Elite 2026",
            code="JEE-ELITE",
            stream=BatchStream.JEE_ADVANCED
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Batch.objects.create(
                    organization=self.org,
                    name="JEE Duplicate",
                    code="JEE-ELITE",
                    stream=BatchStream.JEE_MAIN
                )

    def test_student_enrollment_unique_roll_number(self):
        batch = Batch.objects.create(
            organization=self.org,
            name="Batch A",
            code="BATCH-A"
        )
        student1 = User.objects.create_user(
            username="stud1",
            password="password123",
            role=UserRole.STUDENT,
            organization=self.org
        )
        student2 = User.objects.create_user(
            username="stud2",
            password="password123",
            role=UserRole.STUDENT,
            organization=self.org
        )

        StudentBatchEnrollment.objects.create(
            student=student1,
            batch=batch,
            roll_number="ROLL-001"
        )

        # Duplicate roll number in same batch must fail
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                StudentBatchEnrollment.objects.create(
                    student=student2,
                    batch=batch,
                    roll_number="ROLL-001"
                )

