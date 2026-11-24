from django.urls import path
from .views import (
    QuestionBankListCreateView,
    QuestionBankDetailView,
    QuestionListCreateView,
    SectionListCreateView,
    TagListCreateView,
)

urlpatterns = [
    path('', QuestionBankListCreateView.as_view(), name='qbank-list-create'),
    path('<uuid:id>/', QuestionBankDetailView.as_view(), name='qbank-detail'),
    path('<uuid:paper_id>/questions/', QuestionListCreateView.as_view(), name='qbank-paper-questions'),
    path('<uuid:paper_id>/sections/', SectionListCreateView.as_view(), name='qbank-paper-sections'),
    path('tags/', TagListCreateView.as_view(), name='qbank-tags'),
]
