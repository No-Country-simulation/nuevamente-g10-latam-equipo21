# syntax=docker/dockerfile:1

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:${PATH}" \
    HOME=/tmp

WORKDIR /app

RUN groupadd --gid 10001 nuevamente \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin nuevamente \
    && python -m venv /opt/venv

COPY requirements.txt ./requirements.txt

RUN python -m pip install --upgrade pip \
    && python -m pip install --requirement requirements.txt

COPY --chown=10001:10001 app ./app

RUN mkdir -p /app/chroma_db \
    && chown 10001:10001 /app/chroma_db

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
