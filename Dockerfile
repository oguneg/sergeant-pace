# Sergeant Pace: one image serving the web app and its API.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SP_PUBLIC=1 \
    SP_STATE_DIR=/data/sessions \
    SP_TTS_CACHE_DIR=/data/tts_cache

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN useradd --create-home app && mkdir -p /data/sessions /data/tts_cache && chown -R app:app /data
USER app
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"

# One worker on purpose: conversations and spending limits live in memory. Threads give concurrency while the model thinks.
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--timeout", "120", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "server:app"]
