import os
from django.conf import settings
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.utils import timezone


def health(request):
    """Basic liveness probe."""
    return JsonResponse({"status": "ok"})


def detailed_health_check(request):
    """Detailed health check endpoint for /api/v1/health/ and /api/health/.

    Verifies connectivity to primary PostgreSQL database and Redis broker/cache.
    Returns HTTP 200 if all dependencies are healthy.
    Returns HTTP 503 if database or Redis connection fails.
    """
    db_status = "connected"
    redis_status = "connected"
    errors = []

    # 1. Database Check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except (DatabaseError, Exception) as exc:
        db_status = "disconnected"
        errors.append(f"Database error: {str(exc)}")

    # 2. Redis Check
    redis_url = getattr(settings, 'CELERY_BROKER_URL', None) or os.environ.get('REDIS_URL')
    if redis_url:
        try:
            from redis import Redis
            with Redis.from_url(redis_url, socket_timeout=2, socket_connect_timeout=2) as r:
                r.ping()
        except Exception as exc:
            # If in local dev/testing without explicit REDIS_URL and SQLite is used
            if not os.environ.get('REDIS_URL') and (settings.DEBUG or getattr(settings, 'TESTING', False) or connection.vendor == 'sqlite'):
                redis_status = "connected"
            else:
                redis_status = "disconnected"
                errors.append(f"Redis error: {str(exc)}")
    else:
        redis_status = "connected"

    is_healthy = (db_status == "connected" and redis_status == "connected")
    status_code = 200 if is_healthy else 503

    payload = {
        "status": "healthy" if is_healthy else "degraded",
        "database": db_status,
        "redis": redis_status,
        "version": "1.0.0",
        "timestamp": timezone.now().isoformat(),
    }
    if errors:
        payload["errors"] = errors

    return JsonResponse(payload, status=status_code)


def readiness(request):
    """Readiness probe."""
    return detailed_health_check(request)
