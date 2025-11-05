# Telegram AI Assistant

Персональный AI-ассистент для личного Telegram аккаунта с интеграцией локального AI-сервера, памятью контекста и Google Calendar.

## Требования

- Python 3.12
- uv (менеджер пакетов)
- Локальный AI-сервер с OpenAI-compatible API (vLLM)
- Telegram аккаунт
- (Опционально) Google Calendar API credentials

## Установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd TelegramAI
```

2. Установите зависимости:
```bash
uv sync
```

3. Создайте `.env` файл из шаблона:
```bash
cp .env.example .env
```

## Конфигурация

### 1. Получение Telegram API credentials

1. Перейдите на [my.telegram.org](https://my.telegram.org)
2. Войдите используя ваш номер телефона
3. Перейдите в раздел "API development tools"
4. Создайте новое приложение, указав:
   - App title: любое название
   - Short name: короткое название
   - Platform: Desktop
5. Скопируйте `api_id` и `api_hash`

### 2. Настройка .env файла

Отредактируйте `.env` файл и добавьте:

```env
TELEGRAM_API_ID=ваш_api_id
TELEGRAM_API_HASH=ваш_api_hash
TELEGRAM_PHONE=+7XXXXXXXXXX

# Опционально, если AI-сервер требует API ключ
AI_SERVER_API_KEY=

# Google Calendar (опционально)
GOOGLE_CALENDAR_ENABLED=false
```

### 3. Настройка config.yaml

Базовые настройки уже настроены в `config.yaml`. При необходимости можно изменить:

- `ai_server.base_url` - URL вашего AI-сервера
- `ai_server.model` - название модели
- `memory.context_window` - количество последних сообщений для контекста
- `telegram.handle_private_chats` - обрабатывать личные чаты
- `telegram.handle_groups` - обрабатывать группы
- `telegram.handle_channels` - обрабатывать каналы

### 4. Google Calendar (опционально)

Если хотите использовать интеграцию с Google Calendar:

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект
3. Включите Google Calendar API
4. Создайте OAuth 2.0 credentials (Desktop app)
5. Скачайте `credentials.json` и поместите в `credentials/google-calendar.json`
6. Установите `GOOGLE_CALENDAR_ENABLED=true` в `.env`

## Запуск

### Первая авторизация

При первом запуске потребуется:

1. Запустите приложение:
```bash
uv run telegram-ai
```

2. Введите код подтверждения, который придет в Telegram
3. Если включена 2FA, введите пароль

Сессия сохранится в `sessions/scanovichai.session` и повторная авторизация не потребуется.

### Последующие запуски

Просто запустите:
```bash
uv run telegram-ai
```

## Использование

### Автоматические ответы

Ассистент автоматически отвечает на сообщения в личных чатах (если включено в `config.yaml`).

### Команды Google Calendar

Если интеграция включена:

- `/calendar` или `/events` - показать предстоящие события
- `/create_event Название события | Описание` - создать событие

## Структура проекта

```
TelegramAI/
├── src/telegram_ai/      # Исходный код
├── tests/                # Тесты
├── data/                 # SQLite база данных (создается автоматически)
├── sessions/             # Telethon сессии (создаются автоматически)
├── credentials/          # Google Calendar credentials (если используется)
├── config.yaml           # Конфигурация
├── .env                  # Секреты (не коммитится)
└── README.md
```

## Разработка

### Установка dev зависимостей

```bash
uv sync --dev
```

### Запуск тестов

```bash
uv run pytest
```

### Линтинг

```bash
uv run ruff check .
uv run pyright
```

## Безопасность

⚠️ **Важно:**

- Никогда не коммитьте `.env` файл
- Не коммитьте `sessions/` директорию (сессии содержат токены)
- Не коммитьте `credentials/` директорию (OAuth credentials)
- Не коммитьте `data/` директорию (база данных может содержать личные данные)

Все эти директории уже добавлены в `.gitignore`.

## Устранение проблем

### Ошибка "Configuration validation failed"

Убедитесь, что все переменные окружения установлены в `.env`:
- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `TELEGRAM_PHONE`

### Ошибка подключения к AI-серверу

Проверьте:
1. AI-сервер запущен и доступен
2. `ai_server.base_url` в `config.yaml` правильный
3. Нет блокировки файрвола

### Ошибка авторизации Telegram

1. Убедитесь, что credentials правильные
2. Удалите `sessions/scanovichai.session` и попробуйте снова
3. Проверьте, что номер телефона в формате `+7XXXXXXXXXX`

## Лицензия

MIT

## Автор

FUYOH666 (iamfuyoh@gmail.com)

