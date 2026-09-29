"""Production settings for a TLS-terminating host; select via DJANGO_SETTINGS_MODULE."""
from django.core.exceptions import ImproperlyConfigured
from .settings import *  # noqa: F403

DEBUG = False
if not SECRET_KEY or SECRET_KEY == 'change-me-in-production' or len(SECRET_KEY) < 40:
    raise ImproperlyConfigured('Production requires a strong SECRET_KEY of at least 40 characters.')
if env.bool('USE_SQLITE', default=False):
    raise ImproperlyConfigured('Production requires DATABASE_URL for PostgreSQL.')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS')
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_CONTENT_TYPE_NOSNIFF = True
# Enable only when the hosting proxy strips incoming forwarding headers.
if env.bool('TRUST_HTTPS_PROXY', default=False):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_URL = '/static/'
MIDDLEWARE = list(MIDDLEWARE)
MIDDLEWARE.insert(MIDDLEWARE.index('django.middleware.security.SecurityMiddleware') + 1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
# Uploaded images require persistent storage and a host/CDN serving MEDIA_URL.
MEDIA_ROOT = env('MEDIA_ROOT', default=str(BASE_DIR / 'media'))
MEDIA_URL = env('MEDIA_URL', default='/media/')
