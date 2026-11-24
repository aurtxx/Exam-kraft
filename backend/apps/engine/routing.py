from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"^ws/exam/(?P<attempt_id>[0-9a-f-]+)/?$", consumers.ExamAttemptConsumer.as_asgi()),
]
