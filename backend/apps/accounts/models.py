import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone


class UserRole(models.TextChoices):
    SUPERADMIN = 'SUPERADMIN', 'Platform Super Admin'
    ORG_ADMIN = 'ORG_ADMIN', 'Organization Administrator'
    FACULTY = 'FACULTY', 'Faculty'
    STUDENT = 'STUDENT', 'Student'


class CustomUserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('The Username field must be set')
        username = username.strip()
        user = self.model(username=username, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', UserRole.SUPERADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Unified custom user model for Platform Admins, Org Admins, Faculty, and Students.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='users',
        db_index=True
    )
    username = models.CharField(max_length=150, unique=True, db_index=True)
    email = models.EmailField(max_length=254, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True, db_index=True)
    role = models.CharField(
        max_length=30,
        choices=UserRole.choices,
        default=UserRole.STUDENT,
        db_index=True
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = CustomUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'accounts_user'
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['organization', 'role'], name='idx_user_org_role'),
        ]

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def is_superadmin(self) -> bool:
        return self.role == UserRole.SUPERADMIN or self.is_superuser

    @property
    def is_orgadmin(self) -> bool:
        return self.role in (UserRole.SUPERADMIN, UserRole.ORG_ADMIN)

    @property
    def is_faculty(self) -> bool:
        return self.role in (UserRole.SUPERADMIN, UserRole.ORG_ADMIN, UserRole.FACULTY)

    @property
    def is_student(self) -> bool:
        return self.role == UserRole.STUDENT

    def get_full_name(self) -> str:
        profile = getattr(self, 'profile', None)
        return (profile.full_name if profile and profile.full_name else self.username)


class UserProfile(models.Model):
    """Profile attributes linked 1-to-1 with User."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    full_name = models.CharField(max_length=255)
    avatar_url = models.URLField(max_length=500, null=True, blank=True)
    parent_name = models.CharField(max_length=255, null=True, blank=True)
    parent_phone = models.CharField(max_length=20, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'accounts_userprofile'

    def __str__(self):
        return f"Profile of {self.full_name} ({self.user.username})"


class FacultyProfile(models.Model):
    """Faculty profile attributes, subjects, departments, and assigned batches/centers."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='faculty_profile')
    department = models.CharField(max_length=150, blank=True, default='')
    subjects = models.JSONField(default=list, blank=True)
    assigned_batches = models.ManyToManyField('organizations.Batch', blank=True, related_name='faculty_members')
    assigned_centers = models.ManyToManyField('organizations.ExaminationCenter', blank=True, related_name='faculty_members')

    class Meta:
        db_table = 'accounts_facultyprofile'

    def __str__(self):
        return f"Faculty Profile of {self.user.username}"

