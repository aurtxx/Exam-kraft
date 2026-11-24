import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django_asgi_app = get_asgi_application()

# WebSocket routing removed per Decision D1 (CX-001); HTTP-only ASGI application.
application = django_asgi_app
