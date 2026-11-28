from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from apps.core.views import health, readiness, detailed_health_check
from apps.examinations.views import CandidateExaminationView

urlpatterns = [
    path("healthz/", health),
    path("readyz/", readiness),
    path("api/health/", detailed_health_check),
    path("api/v1/health/", detailed_health_check),
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/users/', include('apps.accounts.user_urls')),
    path('api/v1/organizations/', include('apps.organizations.urls')),
    path('api/v1/question-papers/', include('apps.question_bank.urls')),
    path('api/v1/question-banks/', include('apps.question_bank.urls')),
    path('api/v1/questions/', include('apps.question_bank.question_urls')),
    path('api/v1/examinations/', include('apps.examinations.urls')),
    path('api/v1/notices/', include('apps.notices.urls')),
    path('api/v1/analytics/', include('apps.analytics.urls')),
    path('api/v1/attempts/', include('apps.engine.urls')),
    path('api/v1/student/examinations/', CandidateExaminationView.as_view()),
    path('api/v1/student/examinations/<uuid:id>/', CandidateExaminationView.as_view()),
    path('api/v1/student/attempts/', include('apps.engine.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

