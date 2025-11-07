# Руководство по миграции на новую архитектуру

## Что изменилось

Проект был полностью реорганизован в микросервисную архитектуру:

### Новая структура

- `services/` - микросервисы (telegram-bot, api-gateway, analytics, worker)
- `shared/` - общие модули (database, cache, events, config, utils)
- `infrastructure/` - инфраструктура (docker-compose, kubernetes)
- `alembic/` - миграции БД

### Сохранено

- ✅ Telethon сессия: `./sessions/scanovichai.session` → `./services/telegram-bot/sessions/scanovichai.session`
- ✅ База данных SQLite: продолжает работать (опционально можно мигрировать в PostgreSQL)
- ✅ Все существующие подключения (vLLM, ASR серверы)
- ✅ Конфигурация: `config.yaml` обновлен с поддержкой PostgreSQL и Redis

## Миграция данных

### 1. Telethon сессия

Сессия уже скопирована в новое расположение. Если нужно скопировать вручную:

```bash
cp ./sessions/scanovichai.session ./services/telegram-bot/sessions/scanovichai.session
```

### 2. База данных

**Вариант A: Продолжить использовать SQLite (по умолчанию)**

Ничего делать не нужно - SQLite продолжит работать.

**Вариант B: Мигрировать в PostgreSQL**

1. Создайте PostgreSQL базу данных
2. Установите `DATABASE_URL` в `.env`:
   ```env
   DATABASE_URL=postgresql://user:password@localhost:5432/telegram_ai
   ```
3. Выполните миграции:
   ```bash
   alembic upgrade head
   ```
4. (Опционально) Экспортируйте данные из SQLite в PostgreSQL

### 3. Redis

1. Запустите Redis через Docker Compose:
   ```bash
   docker-compose -f infrastructure/docker-compose.yml up -d redis
   ```
2. Или установите `REDIS_URL` в `.env`:
   ```env
   REDIS_URL=redis://localhost:6379/0
   ```

## Запуск новой архитектуры

### Локальная разработка

1. Запустите инфраструктуру:
   ```bash
   docker-compose -f infrastructure/docker-compose.yml up -d
   ```

2. Запустите Telegram Bot:
   ```bash
   uv run python -m services.telegram_bot.src.main
   ```

3. Запустите API Gateway (в отдельном терминале):
   ```bash
   uv run uvicorn services.api_gateway.src.main:create_app --reload --factory
   ```

### Production

Используйте Docker Compose или Kubernetes для развертывания всех сервисов.

## Обратная совместимость

Старый код в `src/telegram_ai/` сохранен для обратной совместимости, но рекомендуется использовать новую структуру.

## Вопросы и поддержка

При возникновении проблем проверьте:
1. Правильность путей к сессии в `config.yaml`
2. Доступность существующих серверов (vLLM, ASR)
3. Настройки БД и Redis в `.env`

