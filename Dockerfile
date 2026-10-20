FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# collectstatic only needs a SECRET_KEY to import settings; the real one comes at runtime.
RUN SECRET_KEY=build-only python manage.py collectstatic --noinput

EXPOSE 8000

# Migrations run from docker-compose.yml's command so they use the live database.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]
