from django.urls import path
from .views import QuestionListCreateView, QuestionDetailView

urlpatterns = [
    path('', QuestionListCreateView.as_view(), name='questions-list-create'),
    path('<uuid:id>/', QuestionDetailView.as_view(), name='questions-detail'),
]
