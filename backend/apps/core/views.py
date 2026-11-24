from django.conf import settings
from django.db import DatabaseError, connection
from django.http import JsonResponse


def health(request):
    return JsonResponse({"status": "ok"})


def readiness(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        if settings.CELERY_BROKER_URL and not settings.DEBUG:
            from redis import Redis
            from redis.exceptions import RedisError

            with Redis.from_url(settings.CELERY_BROKER_URL, socket_timeout=2, socket_connect_timeout=2) as redis:
                try:
                    redis.ping()
                except RedisError:
                    return JsonResponse({"status": "unavailable"}, status=503)
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return health(request)
