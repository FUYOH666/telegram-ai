# Dockerfile для Analytics Service
FROM python:3.12-slim

WORKDIR /app

# Установка uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Копирование файлов проекта
COPY pyproject.toml uv.lock ./
COPY shared/ ./shared/
COPY services/analytics/ ./services/analytics/
COPY config.yaml ./

# Установка зависимостей
RUN uv sync --frozen

# Запуск сервиса
CMD ["uv", "run", "python", "-m", "services.analytics.src.main"]

