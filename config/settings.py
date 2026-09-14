
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

SECRET_KEY = env('SECRET_KEY', default='django-insecure-%+g^!r@2ek!snk&md*4yoj_6$o7(!nec(6(6%g4c%)bnnnm@8-')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool('DEBUG', default=True)

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])



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
    'apps.b2b',
    'apps.content_cms',
    'apps.search',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',           # Must be before CommonMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

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
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '200/day',
        'user': '2000/day',
        'registration': '5/hour',
        'login': '10/hour',
        'password_reset': '3/hour',
        'inquiry_submit': '10/hour',
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
B2B_PRIVATE_ROOT = env('B2B_PRIVATE_ROOT', default=str(BASE_DIR / 'private_media'))
B2B_DOWNLOAD_TTL = env.int('B2B_DOWNLOAD_TTL', default=300)
RESEND_API_KEY = env('RESEND_API_KEY', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='no-reply@dreamscapetreks.com')
B2B_ADMIN_EMAIL = env('B2B_ADMIN_EMAIL', default='')
PUBLIC_SITE_URL = env('PUBLIC_SITE_URL', default='https://dreamscape-treks.com').rstrip('/')
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_IGNORE_RESULT = True
CELERY_BROKER_CONNECTION_TIMEOUT = 2
CELERY_TASK_PUBLISH_RETRY = False
CELERY_BEAT_SCHEDULE = {
    'deliver-partner-email-outbox': {
        'task': 'apps.b2b.tasks.dispatch_pending_partner_emails',
        'schedule': 5.0,
    },
}
