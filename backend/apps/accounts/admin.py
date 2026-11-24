from django.contrib import admin
from .models import User, UserProfile, FacultyProfile


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'organization', 'is_active', 'date_joined')
    search_fields = ('username', 'email', 'phone')
    list_filter = ('role', 'is_active', 'organization')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'parent_name', 'parent_phone')
    search_fields = ('full_name', 'user__username')


@admin.register(FacultyProfile)
class FacultyProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'department')
    search_fields = ('user__username', 'department')
