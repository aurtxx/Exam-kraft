import uuid
from django.db import models
from django.conf import settings
from apps.organizations.models import BaseTenantModel, Organization


class QuestionType(models.TextChoices):
    MCQ_SINGLE = 'MCQ_SINGLE', 'Single Correct MCQ'
    MCQ_MULTI = 'MCQ_MULTI', 'Multiple Correct MCQ'
    NUMERICAL = 'NUMERICAL', 'Numerical Value'
    SINGLE_DIGIT = 'SINGLE_DIGIT', 'Single Digit Integer'
    TRUE_FALSE = 'TRUE_FALSE', 'True / False'
    ONE_WORD = 'ONE_WORD', 'One-Word Answer'
    SUBJECTIVE = 'SUBJECTIVE', 'Descriptive / Subjective'
    CODING = 'CODING', 'Coding Question'


QUESTION_TYPE_ALIASES = {
    '1': QuestionType.MCQ_SINGLE,
    '2': QuestionType.MCQ_MULTI,
    '3': QuestionType.NUMERICAL,
    '30': QuestionType.SINGLE_DIGIT,
    '21': QuestionType.TRUE_FALSE,
    '8': QuestionType.ONE_WORD,
    '71': QuestionType.SUBJECTIVE,
    '721': QuestionType.CODING,
    '722': QuestionType.CODING,
    '723': QuestionType.CODING,
    '724': QuestionType.CODING,
}


def normalize_question_type(val: str) -> str:
    if not val:
        return QuestionType.MCQ_SINGLE
    val_str = str(val).strip().upper()
    if val_str in QUESTION_TYPE_ALIASES:
        return QUESTION_TYPE_ALIASES[val_str]
    for choice in QuestionType.values:
        if choice == val_str:
            return choice
    # Support 'TEXT_SUBJECTIVE' alias
    if val_str in ('TEXT_SUBJECTIVE', 'DESCRIPTIVE'):
        return QuestionType.SUBJECTIVE
    return val_str


class QuestionBank(BaseTenantModel):
    """Catalog repository containing curated examination questions."""
    name = models.CharField(max_length=255)
    exam_type = models.CharField(max_length=100, default='GENERAL')
    description = models.TextField(blank=True, default='')
    instructions = models.TextField(blank=True, default='')
    duration_minutes = models.PositiveIntegerField(default=60)
    is_locked = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='authored_question_banks'
    )

    class Meta:
        db_table = 'questionbank_questionbank'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.exam_type})"


class Section(BaseTenantModel):
    """Academic subjects and paper sections (e.g., Mathematics, Physics, Chemistry)."""
    question_bank = models.ForeignKey(
        QuestionBank,
        on_delete=models.CASCADE,
        related_name='sections',
        null=True,
        blank=True
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30, blank=True, default='')
    order = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = 'questionbank_section'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Tag(BaseTenantModel):
    """Subject topic tags for question classification."""
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, blank=True, default='')

    class Meta:
        db_table = 'questionbank_tag'
        ordering = ['name']

    def __str__(self):
        return self.name


class Question(models.Model):
    """Individual test question supporting multiple question formats and 3-tier marking."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question_bank = models.ForeignKey(
        QuestionBank,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='questions'
    )
    section_name = models.CharField(max_length=100, default='General')
    question_number = models.PositiveIntegerField(default=1)
    question_type = models.CharField(
        max_length=30,
        choices=QuestionType.choices,
        default=QuestionType.MCQ_SINGLE
    )
    content_text = models.TextField()  # LaTeX / Markdown
    content_html = models.TextField(blank=True, default='')
    image_url = models.URLField(max_length=500, null=True, blank=True)
    explanation = models.TextField(blank=True, default='')
    difficulty = models.CharField(max_length=20, default='MEDIUM')
    
    # Answer key
    key = models.CharField(max_length=500, blank=True, default='')
    
    # Marking Scheme
    positive_marks = models.FloatField(default=4.0)  # cmk
    negative_marks = models.FloatField(default=1.0)  # imk
    partial_marks = models.FloatField(default=0.0)   # pmk
    is_cancelled = models.BooleanField(default=False) # canc

    # Numerical range tolerance
    numerical_min = models.FloatField(null=True, blank=True)
    numerical_max = models.FloatField(null=True, blank=True)

    # Coding questions
    coding_language = models.CharField(max_length=50, blank=True, default='')
    code_boilerplate = models.TextField(blank=True, default='')
    test_cases = models.JSONField(default=list, blank=True)

    tags = models.ManyToManyField(Tag, blank=True, related_name='questions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'questionbank_question'
        ordering = ['question_number', 'created_at']

    def __str__(self):
        return f"Q{self.question_number} [{self.question_type}] {self.content_text[:30]}"


class Option(models.Model):
    """Choice options for MCQ questions."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='options'
    )
    option_key = models.CharField(max_length=10)  # A, B, C, D, ...
    content_text = models.TextField()
    content_html = models.TextField(blank=True, default='')
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'questionbank_option'
        ordering = ['order', 'option_key']

    def __str__(self):
        return f"Option {self.option_key}: {self.content_text[:30]}"
