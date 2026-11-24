from django.urls import path

from . import views


app_name = 'analytics'
urlpatterns = [
    path('results/', views.StudentResultsView.as_view(), name='results'),
    path('results/<uuid:pk>/', views.StudentResultView.as_view(), name='result'),
    path('results/<uuid:pk>/scorecard/', views.StudentScorecardView.as_view(), name='scorecard'),
    path('results/<uuid:pk>/scorecard/download/', views.ScorecardDownloadView.as_view(), name='scorecard-download'),
    path('examinations/<uuid:exam_id>/evaluate/', views.EvaluateExaminationView.as_view(), name='evaluate'),
    path('examinations/<uuid:exam_id>/publish/', views.PublishResultsView.as_view(), name='publish'),
    path('examinations/<uuid:exam_id>/rank-list/', views.RankListView.as_view(), name='rank-list'),
    path('examinations/<uuid:exam_id>/report/', views.ExaminationReportView.as_view(), name='report'),
]
