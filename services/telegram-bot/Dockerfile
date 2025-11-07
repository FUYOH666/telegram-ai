# Dockerfile для Telegram Bot Service
FROM python:3.12-slim

WORKDIR /app

# Установка uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Копирование файлов проекта
COPY pyproject.toml uv.lock ./
COPY shared/ ./shared/
COPY services/telegram-bot/ ./services/telegram-bot/
COPY config.yaml ./

# Установка зависимостей
RUN uv sync --frozen

# Копирование сессий и credentials
COPY sessions/ ./sessions/
COPY credentials/ ./credentials/
COPY knowledge_base/ ./knowledge_base/

# Запуск сервиса
CMD ["uv", "run", "python", "-m", "services.telegram_bot.src.main"]

