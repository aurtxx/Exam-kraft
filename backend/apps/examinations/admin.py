from django.contrib import admin
from .models import (
    Examination,
    ExaminationSection,
    ExaminationQuestion,
    CandidateAssignment,
)


class ExaminationSectionInline(admin.TabularInline):
    model = ExaminationSection
    extra = 1


class CandidateAssignmentInline(admin.TabularInline):
    model = CandidateAssignment
    extra = 0


@admin.register(Examination)
class ExaminationAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'status', 'duration_minutes', 'organization', 'start_window', 'end_window', 'created_at')
    search_fields = ('name', 'code')
    list_filter = ('status', 'organization')
    inlines = [ExaminationSectionInline, CandidateAssignmentInline]


@admin.register(ExaminationSection)
class ExaminationSectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'exam', 'order', 'total_questions', 'marks_per_question')
    list_filter = ('exam',)


@admin.register(ExaminationQuestion)
class ExaminationQuestionAdmin(admin.ModelAdmin):
    list_display = ('exam_section', 'question', 'order', 'marks')


@admin.register(CandidateAssignment)
class CandidateAssignmentAdmin(admin.ModelAdmin):
    list_display = ('exam', 'student', 'batch', 'center', 'assigned_at')
    list_filter = ('exam', 'batch', 'center')
