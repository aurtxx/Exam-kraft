import os
from pathlib import Path
from datetime import timedelta
from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get('DEBUG', 'False') == 'True'

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError('SECRET_KEY is required when DEBUG=False')
    SECRET_KEY = 'django-insecure-ezexam-dev-secret-key-m1-2026'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*' if DEBUG else 'localhost').split(',')
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get('CSRF_TRUSTED_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000').split(',')
    if origin.strip()
]
HTTPS_ENABLED = os.environ.get('HTTPS_ENABLED') == '1'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = HTTPS_ENABLED
CSRF_COOKIE_SECURE = HTTPS_ENABLED

CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 1800

# Optional Daphne / Channels support
try:
    import daphne  # noqa
    import channels  # noqa
    HAS_CHANNELS = True
except ImportError:
    HAS_CHANNELS = False

# Application definition
INSTALLED_APPS = [
    *(['daphne'] if HAS_CHANNELS else []),
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    *(['channels'] if HAS_CHANNELS else []),
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    # Project Apps
    'apps.accounts',
    'apps.core',
    'apps.organizations',
    'apps.question_bank',
    'apps.examinations',
    'apps.notices',
    'apps.engine',
    'apps.analytics',
]

AUTH_USER_MODEL = 'accounts.User'

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.organizations.middleware.TenantMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

if not DEBUG:
    MIDDLEWARE.insert(2, 'whitenoise.middleware.WhiteNoiseMiddleware')

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Channel Layers Configuration for ASGI & WebSockets
if HAS_CHANNELS:
    if os.environ.get('REDIS_URL'):
        CHANNEL_LAYERS = {
            'default': {
                'BACKEND': 'channels_redis.core.RedisChannelLayer',
                'CONFIG': {
                    'hosts': [os.environ.get('REDIS_URL', 'redis://localhost:6379/0')],
                    'capacity': 1500,
                    'expiry': 10,
                },
            },
        }
    else:
        CHANNEL_LAYERS = {
            'default': {
                'BACKEND': 'channels.layers.InMemoryChannelLayer',
            },
        }

# Database Configuration with Connection Pooling
CONN_MAX_AGE = int(os.environ.get('CONN_MAX_AGE', 600))

if os.environ.get('USE_POSTGRES') == '1' or os.environ.get('DB_NAME'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'ezexam'),
            'USER': os.environ.get('DB_USER', 'postgres'),
            'PASSWORD': os.environ.get('DB_PASSWORD', 'postgres'),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
            'CONN_MAX_AGE': CONN_MAX_AGE,
            'CONN_HEALTH_CHECKS': True,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'CONN_MAX_AGE': CONN_MAX_AGE,
        }
    }

if not DEBUG and 'sqlite' in DATABASES['default']['ENGINE']:
    raise RuntimeError('SQLite is not allowed in production (DEBUG=False). Configure PostgreSQL.')

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 6},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/minute',
        'user': '600/minute',
    },
}

# SimpleJWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        'CORS_ALLOWED_ORIGINS',
        'http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000',
    ).split(',')
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = list(default_headers) + [
    'x-tenant-id',
    'x-csrftoken',
]
