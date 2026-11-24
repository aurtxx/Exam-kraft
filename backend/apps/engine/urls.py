from django.urls import path
from .views import (
    StartAttemptView,
    HeartbeatView,
    SaveResponseView,
    SubmitAttemptView,
    ResumeAttemptView,
    ProctoringEventView,
)
from apps.analytics.views import AttemptReportView

urlpatterns = [
    # Start attempt
    path('start/', StartAttemptView.as_view(), name='attempt-start-generic'),
    path('<uuid:id>/start/', StartAttemptView.as_view(), name='attempt-start-by-id'),
    
    # Heartbeat
    path('<uuid:id>/heartbeat/', HeartbeatView.as_view(), name='attempt-heartbeat'),
    
    # Save response
    path('<uuid:id>/save_response/', SaveResponseView.as_view(), name='attempt-save-response'),
    path('<uuid:id>/responses/', SaveResponseView.as_view(), name='attempt-responses-alias'),
    
    # Submit
    path('<uuid:id>/submit/', SubmitAttemptView.as_view(), name='attempt-submit'),
    
    # Resume
    path('<uuid:id>/resume/', ResumeAttemptView.as_view(), name='attempt-resume'),
    
    # Proctoring
    path('<uuid:id>/proctoring_event/', ProctoringEventView.as_view(), name='attempt-proctoring-event'),
    
    # Reports & Results
    path('<uuid:id>/report/', AttemptReportView.as_view(), name='attempt-report'),
    path('<uuid:id>/results/', AttemptReportView.as_view(), name='attempt-results'),
]
