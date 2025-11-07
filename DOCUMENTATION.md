# Документация Telegram AI Platform

## Основные документы

### Для начала работы
- **[README.md](README.md)** - Основная документация проекта
- **[QUICKSTART.md](QUICKSTART.md)** - Быстрый старт за 5 минут
- **[PROJECT_STATUS.md](PROJECT_STATUS.md)** - Текущий статус всех компонентов

### Для миграции
- **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** - Руководство по миграции с предыдущей версии

### Техническая документация
- **[TESTING_REPORT.md](TESTING_REPORT.md)** - Полный отчет о тестировании
- **[RATE_LIMITS_GUIDE.md](RATE_LIMITS_GUIDE.md)** - Руководство по rate limiting

### История изменений
- **[CHANGELOG.md](CHANGELOG.md)** - История версий и изменений

### Новые возможности (v0.7.0)
- **Система уверенности** - умное извлечение данных с confidence scores
- **Fit-score система** - автоматическая квалификация лидов
- **Событийная система** - EventBus для гибкого управления
- **Предбронь встреч** - tentative events с автоматической отменой
- **PDPA согласия** - управление согласиями пользователей

> **Примечание**: Информация об исправлениях ошибок и статусе голосовых сообщений теперь в [PROJECT_STATUS.md](PROJECT_STATUS.md)

## Структура документации

```
docs/
├── README.md              # Главная документация
├── QUICKSTART.md          # Быстрый старт
├── PROJECT_STATUS.md      # Статус проекта
├── MIGRATION_GUIDE.md     # Миграция
├── TESTING_REPORT.md      # Тестирование
├── VOICE_MESSAGES_STATUS.md # Голосовые сообщения
├── FIXES.md               # Исправления
└── RATE_LIMITS_GUIDE.md   # Rate limiting
```

## Быстрые ссылки

- **Запуск бота**: `uv run python scripts/start_telegram_bot.py`
- **Запуск API**: `uv run python scripts/start_api_gateway.py`
- **Тесты**: `uv run pytest tests/ -v`
- **Конфигурация**: `config.yaml`

## Вопросы?

1. Проверьте [PROJECT_STATUS.md](PROJECT_STATUS.md) - статус компонентов
2. Проверьте [FIXES.md](FIXES.md) - известные проблемы и решения
3. Проверьте логи в `logs/` директории
