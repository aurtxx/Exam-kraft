import uuid
from django.db import models
from django.conf import settings
from apps.organizations.models import BaseTenantModel


class ExaminationStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    PUBLISHED = 'PUBLISHED', 'Published'
    SCHEDULED = 'SCHEDULED', 'Scheduled'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    CLOSED = 'CLOSED', 'Closed'
    EVALUATED = 'EVALUATED', 'Evaluated'


class Examination(BaseTenantModel):
    """Authoritative examination entity defining schedules, questions, and security parameters."""
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True, default='')
    slug = models.SlugField(max_length=100, blank=True, default='')
    question_paper = models.ForeignKey(
        'question_bank.QuestionBank',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='examinations'
    )
    instructions = models.TextField(blank=True, default='')
    duration_minutes = models.PositiveIntegerField(default=60)
    total_marks = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    passing_marks = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ExaminationStatus.choices,
        default=ExaminationStatus.DRAFT
    )
    start_window = models.DateTimeField(null=True, blank=True)
    end_window = models.DateTimeField(null=True, blank=True)
    shuffle_questions = models.BooleanField(default=False)
    shuffle_options = models.BooleanField(default=False)
    camera_proctoring = models.BooleanField(default=False)
    max_window_switches = models.PositiveIntegerField(default=5)
    allow_section_skip = models.BooleanField(default=True)
    practice_mode = models.BooleanField(default=False)
    pc_only = models.BooleanField(default=False)
    hide_results = models.BooleanField(default=False)
    hide_rank = models.BooleanField(default=False)
    hide_analytics = models.BooleanField(default=False)
    short_url = models.CharField(max_length=255, blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='authored_examinations'
    )

    class Meta:
        db_table = 'examinations_examination'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} [{self.status}]"


class ExaminationSection(models.Model):
    """Section partitioned within an examination (e.g. Physics, Chemistry, Maths)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exam = models.ForeignKey(
        Examination,
        on_delete=models.CASCADE,
        related_name='sections'
    )
    title = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=1)
    total_questions = models.PositiveIntegerField(default=0)
    marks_per_question = models.DecimalField(max_digits=5, decimal_places=2, default=4.00)
    negative_marks = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)
    partial_marks = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    class Meta:
        db_table = 'examinations_examinationsection'
        ordering = ['order', 'title']

    def __str__(self):
        return f"{self.exam.name} - Section {self.title}"


class ExaminationQuestion(models.Model):
    """Links questions into an examination section with specific question marking overrides."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exam_section = models.ForeignKey(
        ExaminationSection,
        on_delete=models.CASCADE,
        related_name='exam_questions'
    )
    question = models.ForeignKey(
        'question_bank.Question',
        on_delete=models.PROTECT,
        related_name='exam_instances'
    )
    order = models.PositiveIntegerField(default=1)
    marks = models.DecimalField(max_digits=5, decimal_places=2, default=4.00)
    negative_marks = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)
    partial_marks = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    class Meta:
        db_table = 'examinations_examinationquestion'
        ordering = ['order']

    def __str__(self):
        return f"{self.exam_section.title} Q#{self.order}"


class CandidateAssignment(models.Model):
    """Enrollment mapping students, batches, or test centers to scheduled examinations."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exam = models.ForeignKey(
        Examination,
        on_delete=models.CASCADE,
        related_name='candidate_assignments'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='candidate_exam_assignments'
    )
    batch = models.ForeignKey(
        'organizations.Batch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='candidate_exam_assignments'
    )
    center = models.ForeignKey(
        'organizations.ExaminationCenter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='candidate_exam_assignments'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'examinations_candidateassignment'
        ordering = ['-assigned_at']

    def __str__(self):
        return f"Assignment for {self.exam.name} -> {self.student or self.batch or self.center}"
