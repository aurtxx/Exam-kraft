from django.contrib import admin
from .models import QuestionBank, Section, Tag, Question, Option


class OptionInline(admin.TabularInline):
    model = Option
    extra = 4


@admin.register(QuestionBank)
class QuestionBankAdmin(admin.ModelAdmin):
    list_display = ('name', 'exam_type', 'duration_minutes', 'is_locked', 'organization', 'created_at')
    search_fields = ('name', 'exam_type')
    list_filter = ('is_locked', 'exam_type', 'organization')


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'question_bank', 'order')
    search_fields = ('name', 'code')


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'organization')
    search_fields = ('name', 'slug')


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('question_number', 'section_name', 'question_type', 'positive_marks', 'negative_marks', 'is_cancelled')
    search_fields = ('content_text', 'key')
    list_filter = ('question_type', 'difficulty', 'is_cancelled')
    inlines = [OptionInline]


@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):
    list_display = ('option_key', 'question', 'is_correct', 'order')
    list_filter = ('is_correct',)
