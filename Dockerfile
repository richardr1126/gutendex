FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# The catalog updater shells out to tar (with bzip2) and rsync.
RUN apt-get update && apt-get install -y --no-install-recommends \
    bzip2 \
    rsync \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Settings read their database from the environment at import time, so
# collectstatic needs placeholders. Nothing here connects to a database.
RUN SECRET_KEY=build DATABASE_NAME=build DATABASE_USER=build DATABASE_PASSWORD=build \
    DATABASE_HOST=build DATABASE_PORT=5432 \
    python manage.py collectstatic --noinput

EXPOSE 8000

# Migrations are not run here: with more than one replica they would race.
# The Helm chart runs them once in an init container instead.
CMD ["sh", "-c", "exec gunicorn gutendex.wsgi --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-3} --timeout 120 --access-logfile -"]
