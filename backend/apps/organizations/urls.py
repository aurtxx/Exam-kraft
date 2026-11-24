from django.urls import path
from .views import (
    CurrentOrganizationView,
    ExaminationCenterListCreateView,
    ExaminationCenterDetailView,
    BatchListCreateView,
    BatchDetailView,
    SelectFieldsView,
)
from apps.accounts.views import (
    FacultyListCreateView,
    FacultyDetailView,
    StudentListCreateView,
    StudentDetailView,
    StudentBulkImportView,
)

urlpatterns = [
    path('current/', CurrentOrganizationView.as_view(), name='org-current'),
    path('centers/', ExaminationCenterListCreateView.as_view(), name='org-centers'),
    path('centers/<uuid:id>/', ExaminationCenterDetailView.as_view(), name='org-centers-detail'),
    path('<uuid:org_id>/centers/', ExaminationCenterListCreateView.as_view(), name='org-centers-scoped'),
    path('<uuid:org_id>/centers/<uuid:id>/', ExaminationCenterDetailView.as_view(), name='org-centers-scoped-detail'),
    path('batches/', BatchListCreateView.as_view(), name='org-batches'),
    path('batches/<uuid:id>/', BatchDetailView.as_view(), name='org-batches-detail'),
    path('<uuid:org_id>/batches/', BatchListCreateView.as_view(), name='org-batches-scoped'),
    path('<uuid:org_id>/batches/<uuid:id>/', BatchDetailView.as_view(), name='org-batches-scoped-detail'),
    path('select-fields/', SelectFieldsView.as_view(), name='org-select-fields'),
    # Faculty & Student endpoints scoped by organization ID
    path('<uuid:org_id>/faculty/', FacultyListCreateView.as_view(), name='org-faculty-list-create'),
    path('<uuid:org_id>/faculty/<uuid:id>/', FacultyDetailView.as_view(), name='org-faculty-detail'),
    path('<uuid:org_id>/students/', StudentListCreateView.as_view(), name='org-student-list-create'),
    path('<uuid:org_id>/students/<uuid:id>/', StudentDetailView.as_view(), name='org-student-detail'),
    path('<uuid:org_id>/students/bulk-import/', StudentBulkImportView.as_view(), name='org-student-bulk-import'),
    path('<uuid:org_id>/students/bulk-upload/', StudentBulkImportView.as_view(), name='org-student-bulk-upload'),
]
