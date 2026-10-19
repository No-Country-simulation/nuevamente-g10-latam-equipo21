# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp

WORKDIR /app

RUN groupadd --gid 10003 nuevamente-auth \
    && useradd --uid 10003 --gid 10003 --no-create-home --shell /usr/sbin/nologin nuevamente-auth

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --requirement requirements.txt
COPY --chown=10003:10003 app.py login.html ./

USER 10003:10003
EXPOSE 8080

CMD ["uvicorn", "app:create_from_env", "--factory", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
