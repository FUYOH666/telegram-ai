"""Конфигурация приложения через pydantic-settings."""

import logging
from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class TelegramConfig(BaseSettings):
    """Конфигурация Telegram."""

    api_id: int = Field(..., description="API ID из my.telegram.org")
    api_hash: str = Field(..., description="API Hash из my.telegram.org")
    phone: str = Field(..., description="Номер телефона в формате +7XXXXXXXXXX")
    session_path: str = Field(
        default="./sessions/scanovichai.session",
        description="Путь к файлу сессии Telethon",
    )
    handle_private_chats: bool = Field(
        default=True, description="Обрабатывать личные чаты"
    )
    handle_groups: bool = Field(default=False, description="Обрабатывать группы")
    handle_channels: bool = Field(default=False, description="Обрабатывать каналы")

    model_config = SettingsConfigDict(env_prefix="TELEGRAM_")


class AIServerConfig(BaseSettings):
    """Конфигурация AI-сервера."""

    base_url: str = Field(
        default="http://100.93.82.48:8000", description="Базовый URL AI-сервера"
    )
    api_key: Optional[str] = Field(
        default=None, description="API ключ (опционально)"
    )
    model: str = Field(
        default="Qwen3-30B-A3B-Instruct-2507-AWQ-4bit",
        description="Название модели",
    )
    timeout: int = Field(default=30, description="Таймаут запроса в секундах")
    max_retries: int = Field(
        default=3, description="Максимальное количество повторных попыток"
    )
    max_tokens: int = Field(
        default=4096, description="Максимальное количество токенов в ответе"
    )

    model_config = SettingsConfigDict(env_prefix="AI_SERVER_")


class MemoryConfig(BaseSettings):
    """Конфигурация памяти."""

    db_path: str = Field(
        default="./data/conversations.db", description="Путь к файлу SQLite БД"
    )
    context_window: int = Field(
        default=10, description="Количество последних сообщений для контекста"
    )
    max_history_days: int = Field(
        default=30, description="Максимальный возраст истории в днях"
    )

    model_config = SettingsConfigDict(env_prefix="MEMORY_")


class GoogleCalendarConfig(BaseSettings):
    """Конфигурация Google Calendar."""

    enabled: bool = Field(default=False, description="Включить интеграцию")
    credentials_path: str = Field(
        default="./credentials/google-calendar.json",
        description="Путь к credentials файлу",
    )
    token_path: str = Field(
        default="./credentials/token.json", description="Путь к token файлу"
    )

    model_config = SettingsConfigDict(env_prefix="GOOGLE_CALENDAR_")


class Config(BaseSettings):
    """Основная конфигурация приложения."""

    telegram: TelegramConfig
    ai_server: AIServerConfig
    memory: MemoryConfig
    google_calendar: GoogleCalendarConfig

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "Config":
        """
        Загрузить конфигурацию из YAML файла.

        Args:
            yaml_path: Путь к YAML файлу

        Returns:
            Config объект
        """
        yaml_file = Path(yaml_path)

        if not yaml_file.exists():
            raise FileNotFoundError(f"Config file not found: {yaml_path}")

        with open(yaml_file, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)

        # Заменяем переменные окружения в YAML
        yaml_data = cls._substitute_env_vars(yaml_data)

        # Создаем конфигурацию
        telegram = TelegramConfig(**yaml_data.get("telegram", {}))
        ai_server = AIServerConfig(**yaml_data.get("ai_server", {}))
        memory = MemoryConfig(**yaml_data.get("memory", {}))
        google_calendar = GoogleCalendarConfig(**yaml_data.get("google_calendar", {}))

        return cls(
            telegram=telegram,
            ai_server=ai_server,
            memory=memory,
            google_calendar=google_calendar,
        )

    @staticmethod
    def _substitute_env_vars(data: dict) -> dict:
        """
        Заменить переменные окружения в значениях.

        Пример: ${TELEGRAM_API_ID} -> значение из ENV
        """
        import os

        if isinstance(data, dict):
            return {
                key: Config._substitute_env_vars(value) for key, value in data.items()
            }
        elif isinstance(data, list):
            return [Config._substitute_env_vars(item) for item in data]
        elif isinstance(data, str) and data.startswith("${") and data.endswith("}"):
            # Извлекаем имя переменной: ${VAR_NAME} или ${VAR_NAME:default}
            var_expr = data[2:-1]
            if ":" in var_expr:
                var_name, default = var_expr.split(":", 1)
                return os.getenv(var_name.strip(), default.strip())
            else:
                var_name = var_expr.strip()
                value = os.getenv(var_name)
                if value is None:
                    raise ValueError(
                        f"Environment variable {var_name} is not set (used in config)"
                    )
                return value
        else:
            return data

    def validate(self) -> None:
        """
        Валидация конфигурации при старте.

        Raises:
            ValueError: При ошибке валидации
        """
        errors = []

        # Проверка Telegram credentials
        if not self.telegram.api_id or not self.telegram.api_hash:
            errors.append("TELEGRAM_API_ID and TELEGRAM_API_HASH must be set")

        if not self.telegram.phone:
            errors.append("TELEGRAM_PHONE must be set")

        # Проверка AI сервера
        if not self.ai_server.base_url:
            errors.append("AI_SERVER base_url must be set")

        if not self.ai_server.model:
            errors.append("AI_SERVER model must be set")

        # Проверка сессии путь
        session_path = Path(self.telegram.session_path)
        session_path.parent.mkdir(parents=True, exist_ok=True)

        # Проверка Google Calendar если включен
        if self.google_calendar.enabled:
            creds_path = Path(self.google_calendar.credentials_path)
            if not creds_path.exists():
                errors.append(
                    f"Google Calendar credentials file not found: {creds_path}"
                )

        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(
                f"  - {error}" for error in errors
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info("Configuration validated successfully")

