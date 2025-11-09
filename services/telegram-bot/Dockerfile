# Dockerfile для Telegram Bot Service
# Multi-stage build для оптимизации размера образа

# Stage 1: Build stage - установка зависимостей
FROM python:3.12-slim AS builder

WORKDIR /app

# Установка uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Копирование файлов проекта для установки зависимостей
COPY pyproject.toml uv.lock ./
COPY shared/ ./shared/
COPY services/telegram-bot/ ./services/telegram-bot/

# Установка зависимостей
RUN uv sync --frozen

# Stage 2: Runtime stage - минимальный образ
FROM python:3.12-slim

WORKDIR /app

# Установка uv в runtime образ
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Создание non-root пользователя
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Копирование зависимостей из builder stage
COPY --from=builder /app/.venv /app/.venv

# Копирование файлов проекта
COPY pyproject.toml uv.lock ./
COPY shared/ ./shared/
COPY services/telegram-bot/ ./services/telegram-bot/
COPY config.yaml ./

# Копирование сессий и credentials
COPY sessions/ ./sessions/
COPY credentials/ ./credentials/
COPY knowledge_base/ ./knowledge_base/

# Создание директорий для данных и логов с правильными правами
RUN mkdir -p /app/data /app/logs && \
    chown -R appuser:appuser /app

# Переключение на non-root пользователя
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Запуск сервиса
CMD ["uv", "run", "python", "-m", "services.telegram_bot.src.main"]

