import uuid
from django.db import models
from django.conf import settings
from .context import get_current_tenant


class Organization(models.Model):
    """Tenant Organization entity supporting multi-tenant isolation."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    domain = models.CharField(max_length=255, null=True, blank=True, unique=True)
    is_active = models.BooleanField(default=True)
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_organization'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.slug})"


class TenantManager(models.Manager):
    """Manager that automatically filters querysets by the active tenant context."""
    def get_queryset(self):
        qs = super().get_queryset()
        tenant = get_current_tenant()
        if tenant:
            return qs.filter(organization=tenant)
        return qs


class BaseTenantModel(models.Model):
    """Abstract base model enforcing multi-tenant isolation via Organization FK."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='%(class)ss',
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Auto-assign active tenant if not set
        if not self.organization_id:
            tenant = get_current_tenant()
            if tenant:
                self.organization = tenant
        super().save(*args, **kwargs)


class ExaminationCenter(BaseTenantModel):
    """Physical or regional examination venues."""
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)
    address = models.TextField(null=True, blank=True)
    capacity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'organizations_examinationcenter'
        unique_together = ('organization', 'code')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} [{self.code}]"


class BatchStream(models.TextChoices):
    JEE_MAIN = 'JEE_MAIN', 'JEE Main'
    JEE_ADVANCED = 'JEE_ADVANCED', 'JEE Advanced'
    NEET = 'NEET', 'NEET'
    OTHER = 'OTHER', 'Other'


class Batch(BaseTenantModel):
    """Academic batches, cohorts, or class sections."""
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)
    stream = models.CharField(
        max_length=50,
        choices=BatchStream.choices,
        default=BatchStream.OTHER
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'organizations_batch'
        unique_together = ('organization', 'code')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} [{self.code}]"


class StudentBatchEnrollment(models.Model):
    """Maps candidate students to batches, examination centers, and institutional roll numbers."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    center = models.ForeignKey(
        ExaminationCenter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enrollments'
    )
    roll_number = models.CharField(max_length=100)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'organizations_studentbatchenrollment'
        unique_together = ('batch', 'roll_number')
        ordering = ['roll_number']

    def __str__(self):
        return f"{self.roll_number} - {self.student_id} ({self.batch.name})"
