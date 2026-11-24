from django.urls import path
from .views import NoticeListCreateView, NoticeDetailView

urlpatterns = [
    path('', NoticeListCreateView.as_view(), name='notices-list-create'),
    path('<uuid:id>/', NoticeDetailView.as_view(), name='notices-detail'),
]
