# COGNEXA production image.
#
#   docker build -t cognexa .
#   docker run --env-file .env.production -p 8000:8000 cognexa
#
# Migrations are a separate, explicit step (never run implicitly on
# start-up, so a rollback is a deliberate decision):
#   docker run --rm --env-file .env.production cognexa flask --app wsgi db upgrade
#
# See docs/DEPLOYMENT.md for the full procedure.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_ENV=production \
    PORT=8000 \
    WAITRESS_THREADS=8

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Run as an unprivileged user. /app/instance is the only place the app
# may write (and only in development); /data is for a SQLite database
# volume when DATABASE_URL points there.
RUN useradd --create-home --uid 10001 cognexa \
    && mkdir -p /app/instance /data \
    && chown -R cognexa:cognexa /app/instance /data
USER cognexa

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT', '8000'), timeout=4)" || exit 1

CMD ["sh", "-c", "exec waitress-serve --listen=0.0.0.0:${PORT} --threads=${WAITRESS_THREADS} --ident=cognexa wsgi:app"]
