
from datetime import timedelta
from pathlib import Path
import os
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize django-environ — read .env file
env = environ.Env(
    DEBUG=(bool, False)
)
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# Required: no fallback, so a missing value fails at startup instead of running with a known key.
SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool('DEBUG', default=False)

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])
# Render provides the service's own hostname; trust it without listing it by hand.
RENDER_EXTERNAL_HOSTNAME = env('RENDER_EXTERNAL_HOSTNAME', default='')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f'https://{RENDER_EXTERNAL_HOSTNAME}')
# The hosting proxy terminates TLS and forwards the original scheme.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = not DEBUG
# HSTS is only sent on HTTPS responses, so it is harmless locally and in tests.
SECURE_HSTS_SECONDS = 0 if DEBUG else env.int('SECURE_HSTS_SECONDS', default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False)
# Render already redirects HTTP at its edge; this is defence in depth. The health
# check is exempt because Render probes the instance directly over plain HTTP.
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=False)
SECURE_REDIRECT_EXEMPT = [r'^healthz/$']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party packages
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',  # Required for logout token invalidation
    'drf_spectacular',
    'corsheaders',
    'django_filters',

    # Local apps
    'apps.accounts',
    'apps.common',
    'apps.destinations',
    'apps.faq',
    'apps.trips',
    'apps.bookings',
    'apps.payments',
    'apps.inquiries',
    'apps.emails',
    'apps.b2b',
    'apps.content_cms',
    'apps.search',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',      # Serves admin/static files in production
    'corsheaders.middleware.CorsMiddleware',           # Must be before CommonMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.common.throttling.InternalRequestMiddleware',
]

# Shared secret the Next.js server sends as X-Internal-Token (see apps/common/throttling.py).
INTERNAL_API_TOKEN = env('INTERNAL_API_TOKEN', default='')

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    'default': env.db(
        'DATABASE_URL',
        default=f"postgres://{env('DB_USER', default='postgres')}:{env('DB_PASSWORD', default='')}@{env('DB_HOST', default='localhost')}:{env('DB_PORT', default='5432')}/{env('DB_NAME', default='dreamscape_db')}"
    )
}
# Reuse connections in production; close them per-request in development to avoid connection exhaustion with runserver.
DATABASES['default']['CONN_MAX_AGE'] = env.int('CONN_MAX_AGE', default=0 if DEBUG else 60)
DATABASES['default']['CONN_HEALTH_CHECKS'] = True

# Shared cache — throttle counters live here, so it must be shared across workers
# and survive restarts in production. Use `dbcache://django_cache` (needs
# `manage.py createcachetable`) or `redis://...`; local dev defaults to memory.
CACHES = {'default': env.cache('CACHE_URL', default='locmemcache://')}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
# Without a separate Celery worker, uploads are served by Django itself (see config/urls.py).
SERVE_MEDIA = env.bool('SERVE_MEDIA', default=False)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Backblaze B2 (S3-compatible) for uploaded media. The bucket is private, so
# file URLs are signed and expire after B2_URL_EXPIRE seconds.
USE_B2 = env.bool('USE_B2', default=False)
B2_URL_EXPIRE = env.int('B2_URL_EXPIRE', default=3600)
# Public origin of this backend; stored image URLs are MEDIA_PUBLIC_BASE_URL + /media/<key>.
MEDIA_PUBLIC_BASE_URL = env('MEDIA_PUBLIC_BASE_URL', default='http://127.0.0.1:8000').rstrip('/')
if USE_B2:
    B2_ENDPOINT = env('B2_ENDPOINT', default='s3.eu-central-003.backblazeb2.com')
    STORAGES['default'] = {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'OPTIONS': {
            'access_key': env('B2_KEY_ID'),
            'secret_key': env('B2_APPLICATION_KEY'),
            'bucket_name': env('B2_BUCKET_NAME', default='dreamscape-trek-images'),
            'endpoint_url': f'https://{B2_ENDPOINT}',
            'region_name': env('B2_REGION', default='eu-central-003'),
            'signature_version': 's3v4',
            'default_acl': None,
            'file_overwrite': False,
            'querystring_auth': True,
            'querystring_expire': B2_URL_EXPIRE,
        },
    }

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    # Authentication
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    # Default: public read, authenticated write — overridden per-view as needed
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    # Envelope renderer — wraps all responses in { success, data, message }
    'DEFAULT_RENDERER_CLASSES': [
        'apps.common.renderers.DreamscapeJSONRenderer',
    ],
    # Pagination — 20 items/page, max 100
    'DEFAULT_PAGINATION_CLASS': 'apps.common.pagination.StandardResultsPagination',
    'PAGE_SIZE': 20,
    # Throttling
    'DEFAULT_THROTTLE_CLASSES': [
        'apps.common.throttling.DreamscapeAnonThrottle',
        'apps.common.throttling.DreamscapeUserThrottle',
    ],
    # Render's proxy appends the caller's IP to X-Forwarded-For; trust only that last hop.
    'NUM_PROXIES': env.int('NUM_PROXIES', default=0) or None,
    'DEFAULT_THROTTLE_RATES': {
        'anon': '200/day',
        'user': '2000/day',
        'registration': '5/hour',
        'login': '10/hour',
        'password_reset': '3/hour',
        'inquiry_submit': '10/hour',
        'public_write': '30/hour',
        'payment_initiate': '10/minute',
        'search': '60/minute',
    },
    # Exception handler — maps all errors to { success, error: { code, message, details } }
    'EXCEPTION_HANDLER': 'apps.common.exceptions.custom_exception_handler',
    # OpenAPI / Swagger schema generation
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # Filter backend
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

# ---------------------------------------------------------------------------
# JWT (djangorestframework-simplejwt)
# ---------------------------------------------------------------------------
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=14),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# ---------------------------------------------------------------------------
# drf-spectacular (OpenAPI 3.0 / Swagger)
# ---------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    'TITLE': 'Dreamscape Treks™ API',
    'DESCRIPTION': (
        'Multi-Destination Travel, Trekking & Mountaineering Expedition Platform API.\n\n'
        'Regions: Nepal, Tibet, Bhutan, India & Cross-Border Combined Circuits.'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'CONTACT': {'email': 'dev@dreamscapetreks.com'},
    'LICENSE': {'name': 'Proprietary'},
    'SCHEMA_PATH_PREFIX': '/api/v1/',
    'COMPONENT_SPLIT_REQUEST': True,
    'SORT_OPERATIONS': False,
    'ENUM_NAME_OVERRIDES': {
        'AgencyTierEnum': 'apps.b2b.models.AgencyTier.choices',
        'GuideCategoryEnum': 'apps.content_cms.models.GuideCategory.choices',
        'FAQCategoryEnum': 'apps.faq.models.FAQCategory.choices',
    },
}

# ---------------------------------------------------------------------------
# CORS (django-cors-headers)
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list(
    'CORS_ALLOWED_ORIGINS',
    default=[
        'http://localhost:3000',   # Next.js dev server
        'http://127.0.0.1:3000',
    ],
)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-khalti-signature',  # Khalti webhook signature header
]

# Partner portal infrastructure. Private files must never be served as public media.
# With USE_B2 they go to the bucket's b2b-private/ prefix; this root is the local fallback.
B2B_PRIVATE_ROOT = env('B2B_PRIVATE_ROOT', default=str(BASE_DIR / 'private_media'))
B2B_DOWNLOAD_TTL = env.int('B2B_DOWNLOAD_TTL', default=300)
RESEND_API_KEY = env('RESEND_API_KEY', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='no-reply@dreamscapetreks.com')
B2B_ADMIN_EMAIL = env('B2B_ADMIN_EMAIL', default='')
# Svix signing secret ("whsec_...") of the Resend webhook that reports delivery status.
RESEND_WEBHOOK_SECRET = env('RESEND_WEBHOOK_SECRET', default='')
# Team inbox alerted on every new inquiry; leave unset to send nothing.
INQUIRY_NOTIFY_EMAIL = env('INQUIRY_NOTIFY_EMAIL', default='')
PUBLIC_SITE_URL = env('PUBLIC_SITE_URL', default='https://dreamscape-treks.com').rstrip('/')
# Django's own mail (e.g. password reset) goes through Resend when a key is set;
# without one, local dev prints mail to the console. Tests always use locmem.
if RESEND_API_KEY:
    EMAIL_BACKEND = 'apps.common.email.ResendEmailBackend'
elif DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_IGNORE_RESULT = True
CELERY_BROKER_CONNECTION_TIMEOUT = 2
CELERY_TASK_PUBLISH_RETRY = False
# With no worker running (e.g. Render free plan), run tasks inline so emails still send.
CELERY_TASK_ALWAYS_EAGER = env.bool('CELERY_TASK_ALWAYS_EAGER', default=False)
CRM_SLA_HOURS = env.int('CRM_SLA_HOURS', default=4)

# Hours a waitlisted traveller has to claim an offered seat before the offer
# lapses and the next entry in the queue is served.
WAITLIST_OFFER_TTL_HOURS = env.int('WAITLIST_OFFER_TTL_HOURS', default=48)

CELERY_BEAT_SCHEDULE = {
    'deliver-partner-email-outbox': {
        'task': 'apps.b2b.tasks.dispatch_pending_partner_emails',
        'schedule': 5.0,
    },
    'crm-check-sla-breaches': {
        'task': 'apps.inquiries.tasks.check_sla_breaches',
        'schedule': 1800.0,  # every 30 minutes
    },
    'crm-send-task-reminders': {
        'task': 'apps.inquiries.tasks.send_task_reminders',
        'schedule': 900.0,  # every 15 minutes
    },
    'crm-advance-travel-statuses': {
        'task': 'apps.inquiries.tasks.advance_travel_statuses',
        'schedule': 3600.0,  # hourly
    },
    'crm-nightly-customer-rollup': {
        'task': 'apps.inquiries.tasks.nightly_customer_rollup',
        'schedule': 86400.0,  # daily
    },
    'bookings-expire-waitlist-offers': {
        'task': 'apps.bookings.tasks.expire_waitlist_offers',
        'schedule': 900.0,  # every 15 minutes
    },
}

# Administrative security: Django admin session expires when browser closes
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 3600  # 1 hour max session

# Log to stdout so Render's log stream captures app warnings and request errors.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'plain': {'format': '%(asctime)s %(levelname)s %(name)s: %(message)s'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'plain'},
    },
    'root': {'handlers': ['console'], 'level': env('LOG_LEVEL', default='INFO')},
    'loggers': {
        'django.request': {'level': 'ERROR'},
    },
}
