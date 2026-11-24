from django.contrib import admin
from .models import Notice


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'organization', 'is_active', 'start_time', 'end_time', 'created_at')
    search_fields = ('title', 'content')
    list_filter = ('is_active', 'organization')
