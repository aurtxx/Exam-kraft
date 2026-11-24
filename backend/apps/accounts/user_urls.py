from django.urls import path
from .views import (
    FacultyListCreateView,
    FacultyDetailView,
    StudentListCreateView,
    StudentDetailView,
    StudentBulkImportView,
)

urlpatterns = [
    path('faculty/', FacultyListCreateView.as_view(), name='user-faculty-list-create'),
    path('faculty/<uuid:id>/', FacultyDetailView.as_view(), name='user-faculty-detail'),
    path('students/', StudentListCreateView.as_view(), name='user-student-list-create'),
    path('students/<uuid:id>/', StudentDetailView.as_view(), name='user-student-detail'),
    path('students/bulk-upload/', StudentBulkImportView.as_view(), name='user-student-bulk-upload'),
    path('students/bulk-import/', StudentBulkImportView.as_view(), name='user-student-bulk-import'),
]
