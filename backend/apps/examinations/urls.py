from django.urls import path
from .views import (
    ExaminationListCreateView,
    ExaminationDetailView,
    AssignCandidatesView,
    PublishExaminationView,
    StaffPreviewView,
)

urlpatterns = [
    path('', ExaminationListCreateView.as_view(), name='examinations-list-create'),
    path('<uuid:id>/', ExaminationDetailView.as_view(), name='examinations-detail'),
    path('<uuid:id>/assign-candidates/', AssignCandidatesView.as_view(), name='examinations-assign-candidates'),
    path('<uuid:id>/publish/', PublishExaminationView.as_view(), name='examinations-publish'),
    path('<uuid:id>/preview/', StaffPreviewView.as_view(), name='examinations-preview'),
]
