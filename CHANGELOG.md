# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2025-11-05

### Added

- Базовая функциональность Telegram AI-ассистента для личного аккаунта
- Интеграция с локальным AI-сервером (OpenAI-compatible API)
- Память и контекст диалогов через SQLite
- Интеграция с Google Calendar (опционально)
- Конфигурация через YAML и ENV переменные
- Автоматические ответы на сообщения в личных чатах
- Команды для управления календарем (`/calendar`, `/events`, `/create_event`)

### Technical

- Python 3.12
- Telethon для работы с личным аккаунтом Telegram
- SQLAlchemy для работы с БД
- Pydantic Settings для конфигурации
- Tenacity для ретраев
- httpx для HTTP запросов

