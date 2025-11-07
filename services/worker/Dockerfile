# Dockerfile для Worker Service
FROM python:3.12-slim

WORKDIR /app

# Установка uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Копирование файлов проекта
COPY pyproject.toml uv.lock ./
COPY shared/ ./shared/
COPY services/worker/ ./services/worker/
COPY config.yaml ./

# Установка зависимостей
RUN uv sync --frozen

# Запуск Celery worker
CMD ["uv", "run", "celery", "-A", "services.worker.src.tasks.meeting_summary", "worker", "--loglevel=info"]

