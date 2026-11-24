from django.urls import path
from .views import (
    CurrentOrganizationView,
    ExaminationCenterListCreateView,
    BatchListCreateView,
    SelectFieldsView,
)

urlpatterns = [
    path('current/', CurrentOrganizationView.as_view(), name='org-current'),
    path('centers/', ExaminationCenterListCreateView.as_view(), name='org-centers'),
    path('batches/', BatchListCreateView.as_view(), name='org-batches'),
    path('select-fields/', SelectFieldsView.as_view(), name='org-select-fields'),
]
