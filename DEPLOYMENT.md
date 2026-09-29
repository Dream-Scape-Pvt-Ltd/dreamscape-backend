# Deploying the backend from Git

The frontend and backend are separate repositories. Deploy this repository as a Python/Linux web service; do not use `runserver` in production.

## Configuration
Install `requirements-production.txt`. Set `DJANGO_SETTINGS_MODULE=config.production`, `DEBUG=False`, a random secret of at least 40 characters, and a PostgreSQL `DATABASE_URL`. `USE_SQLITE` must be false.

Set:
- `ALLOWED_HOSTS`: backend hostnames, comma separated, without schemes.
- `CORS_ALLOWED_ORIGINS`: exact HTTPS frontend origins.
- `CSRF_TRUSTED_ORIGINS`: exact HTTPS frontend and backend origins used for administration.
- `PUBLIC_SITE_URL`: final frontend origin.
- `TRUST_HTTPS_PROXY=True` only if your hosting proxy strips untrusted forwarded headers and supplies `X-Forwarded-Proto` itself.
- `MEDIA_ROOT`: persistent upload directory; configure the host/CDN to serve public `MEDIA_URL` from it. WhiteNoise serves static files, not uploaded media. Never expose `private_media` / `B2B_PRIVATE_ROOT` publicly.
- `CELERY_BROKER_URL`: hosted Redis URL. Configure email credentials and run the existing Celery worker/beat when enabling notifications.

## Release commands
```sh
pip install -r requirements-production.txt
python manage.py check --deploy
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py createsuperuser
```
Create/verify a user with the application ADMIN role for the frontend `/admin` dashboard; Django `is_superuser` and the application role are separate concepts. Do not put credentials in Git.

The Procfile starts Gunicorn and provides a worker command. A generic Linux start command is:
```sh
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --access-logfile - --error-logfile -
```

For a new database, import the existing photo stories and Nepal regions once:
```sh
python manage.py import_website_content --asset-base-url https://YOUR-FRONTEND-DOMAIN --publish
```
Existing CMS rows are preserved. Imported image URLs reference the frontend's Git-managed `/images` files; set the final domain before import. Publish verified trips and departures through the CMS separately.

## Before turning on traffic
Check login/logout, anonymous write rejection, enquiries, CMS updates, uploaded media after a redeploy, and the frontend's real API calls over HTTPS. Back up PostgreSQL and media. Configure and test the payment gateway with the backend team before enabling card checkout.

This configuration is prepared but not deployed. A host, domain, PostgreSQL service and persistent media setup still need to be selected. The production profile has not been exercised against a live hosting environment.

References: [Gunicorn deployment](https://gunicorn.org/deploy/) and [WhiteNoise Django setup](https://whitenoise.readthedocs.io/en/stable/django.html).
