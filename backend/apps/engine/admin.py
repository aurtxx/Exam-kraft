from django.contrib import admin
from .models import ExaminationAttempt, AttemptResponse, ProctoringLog


@admin.register(ExaminationAttempt)
class ExaminationAttemptAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'examination', 'status', 'started_at', 'server_deadline', 'submitted_at', 'tab_switch_count')
    list_filter = ('status', 'started_at')
    search_fields = ('user__username', 'examination__name', 'attempt_token')


@admin.register(AttemptResponse)
class AttemptResponseAdmin(admin.ModelAdmin):
    list_display = ('id', 'attempt', 'question', 'status', 'time_spent_seconds', 'saved_at')
    list_filter = ('status',)
    search_fields = ('attempt__id', 'question__content_text')


@admin.register(ProctoringLog)
class ProctoringLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'attempt', 'event_type', 'timestamp')
    list_filter = ('event_type',)
