import uuid

from django.db import models


class Result(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.OneToOneField('engine.ExaminationAttempt', on_delete=models.CASCADE, related_name='result')
    total_score = models.DecimalField(max_digits=10, decimal_places=2)
    maximum_score = models.DecimalField(max_digits=10, decimal_places=2)
    penalty = models.DecimalField(max_digits=10, decimal_places=2)
    rank = models.PositiveIntegerField(null=True)
    percentile = models.DecimalField(max_digits=6, decimal_places=3, null=True)
    evaluated_at = models.DateTimeField(auto_now_add=True)
    is_published = models.BooleanField(default=False)


class Scorecard(models.Model):
    result = models.OneToOneField(Result, on_delete=models.CASCADE, related_name='scorecard')
    score_percentage = models.DecimalField(max_digits=12, decimal_places=2)
    passed = models.BooleanField(null=True)


class SectionScore(models.Model):
    scorecard = models.ForeignKey(Scorecard, on_delete=models.CASCADE, related_name='sections')
    title = models.CharField(max_length=100)
    order = models.PositiveIntegerField()
    score = models.DecimalField(max_digits=10, decimal_places=2)
    maximum_score = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ['order', 'pk']


class QuestionResponseReview(models.Model):
    class Outcome(models.TextChoices):
        CORRECT = 'CORRECT'
        PARTIAL = 'PARTIAL'
        INCORRECT = 'INCORRECT'
        UNANSWERED = 'UNANSWERED'
        CANCELLED = 'CANCELLED'
        PENDING = 'PENDING'

    section = models.ForeignKey(SectionScore, on_delete=models.CASCADE, related_name='reviews')
    question = models.ForeignKey('question_bank.Question', on_delete=models.SET_NULL, null=True)
    selected_options = models.JSONField(default=list)
    submitted_value = models.CharField(max_length=100, blank=True)
    answer = models.JSONField(default=list)
    explanation = models.TextField(blank=True)
    outcome = models.CharField(max_length=10, choices=Outcome.choices)
    marks = models.DecimalField(max_digits=10, decimal_places=2)
    time_spent_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['pk']
