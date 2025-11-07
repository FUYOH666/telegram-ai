# Быстрый старт новой архитектуры

## Предварительные требования

- Python 3.12
- uv (менеджер пакетов)
- Docker и Docker Compose (для PostgreSQL и Redis)
- Существующие серверы:
  - vLLM: `http://100.93.82.48:8000`
  - ASR: `http://100.93.82.48:8001`

## Шаг 1: Установка зависимостей

```bash
cd /Users/aleksandrmordvinov/development/TelegramAI
uv sync
```

## Шаг 2: Настройка окружения

Создайте `.env` файл:

```env
# Telegram
TELEGRAM_API_ID=ваш_api_id
TELEGRAM_API_HASH=ваш_api_hash
TELEGRAM_PHONE=+7XXXXXXXXXX

# Database (опционально, по умолчанию SQLite)
# DATABASE_URL=postgresql://user:password@localhost:5432/telegram_ai

# Redis
REDIS_URL=redis://localhost:6379/0

# AI Server (существующий)
AI_SERVER_BASE_URL=http://100.93.82.48:8000
AI_SERVER_MODEL=models/Qwen3-30B-A3B-Instruct-2507-AWQ-4bit

# ASR Server (существующий)
ASR_SERVER_BASE_URL=http://100.93.82.48:8001
```

## Шаг 3: Запуск инфраструктуры

```bash
docker-compose -f infrastructure/docker-compose.yml up -d
```

Это запустит PostgreSQL и Redis.

## Шаг 4: Миграции БД (если используете PostgreSQL)

```bash
# Если используете PostgreSQL, раскомментируйте DATABASE_URL в .env
# Затем выполните миграции:
alembic upgrade head
```

## Шаг 5: Запуск сервисов

### Telegram Bot Service

```bash
uv run python scripts/start_telegram_bot.py
```

### API Gateway (в отдельном терминале)

```bash
uv run python scripts/start_api_gateway.py
```

Сервер запустится на `http://localhost:8000`

### Worker Service (опционально, в отдельном терминале)

```bash
uv run python scripts/start_worker.py
```

Или через Celery напрямую:
```bash
uv run celery -A services.worker.src.tasks.meeting_summary worker --loglevel=info
```

## Проверка работы

1. **Telegram Bot**: Отправьте сообщение в личный чат - должен прийти ответ
2. **API Gateway**: Откройте `http://localhost:8000/health` - должен вернуться `{"status": "ok"}`
3. **API Endpoints**: `http://localhost:8000/api/v1/leads` - список лидов (пока пустой)

## Структура проекта

```
telegram-ai-platform/
├── services/              # Микросервисы
│   ├── telegram-bot/     # Telegram бот (основной сервис)
│   ├── api-gateway/       # REST API
│   ├── analytics/        # Аналитика
│   └── worker/           # Celery workers
├── shared/                # Общие модули
│   ├── database/         # Модели БД, миграции
│   ├── cache/            # Redis клиент
│   ├── config/           # Конфигурация
│   └── events/           # Event schemas
├── infrastructure/        # Docker Compose, K8s
└── config.yaml           # Основная конфигурация
```

## Важные замечания

- ✅ Telethon сессия сохранена в `services/telegram-bot/sessions/scanovichai.session`
- ✅ Существующие серверы (vLLM, ASR) используются без изменений
- ✅ SQLite продолжает работать (можно мигрировать в PostgreSQL позже)
- ✅ Старый код в `src/telegram_ai/` сохранен для обратной совместимости

## Следующие шаги

1. Реализовать полную интеграцию LangChain/LangGraph
2. Добавить реализацию API endpoints (сейчас заглушки)
3. Настроить экспорт в Google Sheets/ClickUp
4. Добавить мониторинг (Prometheus, Grafana)

