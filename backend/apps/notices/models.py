import uuid
from django.db import models
from django.conf import settings
from apps.organizations.models import BaseTenantModel


class Notice(BaseTenantModel):
    """Broadcast announcements directed to specific cohorts, centers, or institution-wide."""
    title = models.CharField(max_length=255)
    content = models.TextField()
    target_batches = models.ManyToManyField(
        'organizations.Batch',
        blank=True,
        related_name='targeted_notices'
    )
    target_centers = models.ManyToManyField(
        'organizations.ExaminationCenter',
        blank=True,
        related_name='targeted_notices'
    )
    is_active = models.BooleanField(default=True)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_notices'
    )

    class Meta:
        db_table = 'notices_notice'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} (Active: {self.is_active})"
