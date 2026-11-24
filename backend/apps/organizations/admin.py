from django.contrib import admin
from .models import Organization, ExaminationCenter, Batch, StudentBatchEnrollment


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'domain', 'is_active', 'created_at')
    search_fields = ('name', 'slug', 'domain')
    list_filter = ('is_active',)


@admin.register(ExaminationCenter)
class ExaminationCenterAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'organization', 'capacity', 'is_active')
    search_fields = ('name', 'code')
    list_filter = ('is_active', 'organization')


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'organization', 'stream', 'is_active')
    search_fields = ('name', 'code')
    list_filter = ('is_active', 'stream', 'organization')


@admin.register(StudentBatchEnrollment)
class StudentBatchEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('roll_number', 'student', 'batch', 'center', 'is_active', 'enrolled_at')
    search_fields = ('roll_number', 'student__username')
    list_filter = ('is_active', 'batch', 'center')
