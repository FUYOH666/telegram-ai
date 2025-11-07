# Dockerfile для API Gateway Service
FROM python:3.12-slim

WORKDIR /app

# Установка uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Копирование файлов проекта
COPY pyproject.toml uv.lock ./
COPY shared/ ./shared/
COPY services/api-gateway/ ./services/api-gateway/
COPY config.yaml ./

# Установка зависимостей
RUN uv sync --frozen

# Запуск сервиса
CMD ["uv", "run", "uvicorn", "services.api_gateway.src.main:create_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]

