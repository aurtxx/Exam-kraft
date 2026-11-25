import uuid
from datetime import timedelta
from django.db import models
from django.db.models import Q
from django.conf import settings
from django.utils import timezone


class AttemptStatus(models.TextChoices):
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    SUBMITTED = 'SUBMITTED', 'Submitted'
    AUTO_SUBMITTED = 'AUTO_SUBMITTED', 'Auto Submitted'


class ResponseStatus(models.TextChoices):
    NOT_VISITED = 'NOT_VISITED', 'Not Visited'
    UNANSWERED = 'UNANSWERED', 'Not Answered'
    ANSWERED = 'ANSWERED', 'Answered'
    MARKED_FOR_REVIEW = 'MARKED_FOR_REVIEW', 'Marked for Review'
    ANSWERED_AND_MARKED = 'ANSWERED_AND_MARKED', 'Answered and Marked for Review'


def normalize_response_status(status_str: str) -> str:
    """Normalize input status variations to canonical ResponseStatus choice."""
    if not status_str:
        return ResponseStatus.NOT_VISITED
    s = str(status_str).strip().upper()
    if s in ('ANSWERED_AND_MARKED_FOR_REVIEW', 'ANSWERED_AND_MARKED', 'ANSWERED_MARKED'):
        return ResponseStatus.ANSWERED_AND_MARKED
    if s in ('MARKED_FOR_REVIEW', 'MARKED'):
        return ResponseStatus.MARKED_FOR_REVIEW
    if s in ('ANSWERED', 'ATTEMPTED'):
        return ResponseStatus.ANSWERED
    if s in ('UNANSWERED', 'NOT_ANSWERED'):
        return ResponseStatus.UNANSWERED
    if s in ('NOT_VISITED', 'UNVISITED'):
        return ResponseStatus.NOT_VISITED
    return ResponseStatus.NOT_VISITED


class ProctoringEventType(models.TextChoices):
    TAB_SWITCH = 'TAB_SWITCH', 'Tab Switch'
    FULLSCREEN_EXIT = 'FULLSCREEN_EXIT', 'Fullscreen Exit'
    WINDOW_BLUR = 'WINDOW_BLUR', 'Window Blur'


class ExaminationAttempt(models.Model):
    """Candidate examination session record with server-authoritative timer and submission lock."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='examination_attempts'
    )
    examination = models.ForeignKey(
        'examinations.Examination',
        on_delete=models.CASCADE,
        related_name='attempts'
    )
    started_at = models.DateTimeField(default=timezone.now)
    server_deadline = models.DateTimeField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=AttemptStatus.choices,
        default=AttemptStatus.IN_PROGRESS
    )
    tab_switch_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'engine_examinationattempt'
        ordering = ['-started_at']
        constraints = [
            models.UniqueConstraint(
                fields=['examination', 'user'],
                condition=Q(status='IN_PROGRESS'),
                name='uq_active_candidate_attempt',
            ),
        ]

    def __str__(self):
        return f"Attempt {self.id} - User {self.user_id} - Exam {self.examination_id} [{self.status}]"

    @property
    def remaining_seconds(self) -> int:
        now = timezone.now()
        if now >= self.server_deadline or self.status in (AttemptStatus.SUBMITTED, AttemptStatus.AUTO_SUBMITTED):
            return 0
        return max(0, int((self.server_deadline - now).total_seconds()))

    @property
    def is_expired(self) -> bool:
        return timezone.now() > (self.server_deadline + timedelta(seconds=30))


class AttemptResponse(models.Model):
    """Granular response for a single examination question within an attempt."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(
        ExaminationAttempt,
        on_delete=models.CASCADE,
        related_name='responses'
    )
    question = models.ForeignKey(
        'question_bank.Question',
        on_delete=models.CASCADE,
        related_name='attempt_responses'
    )
    selected_options = models.JSONField(default=list, blank=True)
    numerical_value = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(
        max_length=40,
        choices=ResponseStatus.choices,
        default=ResponseStatus.NOT_VISITED
    )
    saved_at = models.DateTimeField(auto_now=True)
    time_spent_seconds = models.IntegerField(default=0)

    class Meta:
        db_table = 'engine_attemptresponse'
        unique_together = ('attempt', 'question')
        ordering = ['saved_at']

    def __str__(self):
        return f"Response {self.attempt_id} - Q:{self.question_id} [{self.status}]"


class ProctoringLog(models.Model):
    """Audit log of candidate proctoring events during an examination attempt."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(
        ExaminationAttempt,
        on_delete=models.CASCADE,
        related_name='proctoring_logs'
    )
    event_type = models.CharField(
        max_length=30,
        choices=ProctoringEventType.choices
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'engine_proctoringlog'
        ordering = ['-timestamp']

    def __str__(self):
        return f"ProctoringLog {self.attempt_id} - {self.event_type} at {self.timestamp}"
