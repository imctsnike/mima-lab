FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/app \
    XDG_CACHE_HOME=/home/app/.cache \
    MIMA_DATA_DIR=/app/data

WORKDIR /app

COPY mima/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=10001:10001 mima/ .
RUN mkdir -p /app/data /home/app/.cache && chown -R 10001:10001 /app /home/app

USER 10001:10001
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:3000/health', timeout=3)"

CMD ["gunicorn", "--bind", "0.0.0.0:3000", "--workers", "1", "--threads", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:create_flask_app()"]
