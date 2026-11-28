from django.urls import path
from .views import (
    QuestionBankListCreateView,
    QuestionBankDetailView,
    QuestionListCreateView,
    SectionListCreateView,
    TagListCreateView,
    BulkZipUploadView,
    BulkQuestionCurateView,
)

urlpatterns = [
    path('', QuestionBankListCreateView.as_view(), name='qbank-list-create'),
    path('<uuid:id>/', QuestionBankDetailView.as_view(), name='qbank-detail'),
    path('<uuid:paper_id>/questions/', QuestionListCreateView.as_view(), name='qbank-paper-questions'),
    path('<uuid:paper_id>/sections/', SectionListCreateView.as_view(), name='qbank-paper-sections'),
    path('<uuid:paper_id>/upload-zip/', BulkZipUploadView.as_view(), name='qbank-upload-zip'),
    path('<uuid:paper_id>/curate/', BulkQuestionCurateView.as_view(), name='qbank-curate'),
    path('tags/', TagListCreateView.as_view(), name='qbank-tags'),
]
