"""Конфигурация приложения через pydantic-settings."""

import logging
import os
from pathlib import Path
from typing import List, Optional

import yaml
from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Загружаем .env файл
load_dotenv()

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
        default="Qwen/Qwen2.5-14B-Instruct-AWQ",
        description="Название модели",
    )
    timeout: int = Field(default=30, description="Таймаут запроса в секундах")
    max_retries: int = Field(
        default=3, description="Максимальное количество повторных попыток"
    )
    max_tokens: int = Field(
        default=4096, description="Максимальное количество токенов в ответе"
    )
    system_prompt: Optional[str] = Field(
        default=None, description="Системный промпт для настройки поведения модели"
    )
    temperature: float = Field(
        default=0.7, description="Температура генерации (0.0-1.0)"
    )
    timezone: str = Field(
        default="Europe/Moscow", description="Часовой пояс для конвертации UTC"
    )
    date_format: Optional[str] = Field(
        default=None, description="Формат даты (опционально, используется дефолтный если None)"
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

    enabled: bool = Field(
        default=False,
        description="Включить интеграцию",
        json_schema_extra={"env_parse": lambda v: v.lower() in ("true", "1", "yes") if isinstance(v, str) else bool(v)},
    )
    credentials_path: str = Field(
        default="./credentials/google-calendar.json",
        description="Путь к credentials файлу",
    )
    token_path: str = Field(
        default="./credentials/token.json", description="Путь к token файлу"
    )
    auto_create_consultations: bool = Field(
        default=True, description="Автоматически создавать встречи при запросах"
    )
    default_consultation_duration_minutes: int = Field(
        default=60, description="Длительность консультации по умолчанию (минуты)"
    )
    available_slots: List[str] = Field(
        default_factory=lambda: ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00"],
        description="Доступные слоты времени для встреч",
    )

    model_config = SettingsConfigDict(env_prefix="GOOGLE_CALENDAR_")


class SpamDetectionConfig(BaseSettings):
    """Конфигурация детекции спама."""

    max_repeated_messages: int = Field(
        default=3, description="Максимальное количество повторяющихся сообщений подряд"
    )
    min_message_length: int = Field(
        default=2, description="Минимальная длина сообщения (символов)"
    )
    max_message_length: int = Field(
        default=5000, description="Максимальная длина сообщения (символов)"
    )


class RateLimitingConfig(BaseSettings):
    """Конфигурация rate limiting."""

    enabled: bool = Field(
        default=True, description="Включить rate limiting"
    )
    messages_per_minute: int = Field(
        default=10, description="Максимальное количество сообщений в минуту"
    )
    messages_per_hour: int = Field(
        default=50, description="Максимальное количество сообщений в час"
    )
    min_interval_seconds: int = Field(
        default=2, description="Минимальный интервал между сообщениями (секунды)"
    )
    block_duration_minutes: int = Field(
        default=10, description="Длительность блокировки при превышении лимита (минуты)"
    )
    spam_detection: SpamDetectionConfig = Field(
        default_factory=SpamDetectionConfig, description="Настройки детекции спама"
    )

    model_config = SettingsConfigDict(env_prefix="RATE_LIMITING_")


class ASRServerConfig(BaseSettings):
    """Конфигурация ASR сервера."""

    base_url: str = Field(
        default="http://100.93.82.48:8001", description="Базовый URL ASR сервера"
    )
    timeout: int = Field(default=60, description="Таймаут запроса в секундах")
    enabled: bool = Field(default=True, description="Включить обработку голосовых сообщений")

    model_config = SettingsConfigDict(env_prefix="ASR_SERVER_")


class SalesFlowConfig(BaseSettings):
    """Конфигурация скрипта продаж."""

    enabled: bool = Field(default=True, description="Включить скрипт продаж")

    model_config = SettingsConfigDict(env_prefix="SALES_FLOW_")


class Config(BaseSettings):
    """Основная конфигурация приложения."""

    telegram: TelegramConfig
    ai_server: AIServerConfig
    memory: MemoryConfig
    google_calendar: GoogleCalendarConfig
    rate_limiting: RateLimitingConfig
    asr_server: ASRServerConfig
    sales_flow: SalesFlowConfig

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
        
        # Парсим enabled как boolean если это строка
        google_cal_data = yaml_data.get("google_calendar", {})
        enabled_val = google_cal_data.get("enabled", False)
        if isinstance(enabled_val, str):
            google_cal_data["enabled"] = enabled_val.lower() in ("true", "1", "yes")
        elif not isinstance(enabled_val, bool):
            google_cal_data["enabled"] = bool(enabled_val)
        google_calendar = GoogleCalendarConfig(**google_cal_data)

        # Rate limiting конфигурация
        rate_limiting_data = yaml_data.get("rate_limiting", {})
        spam_detection_data = rate_limiting_data.get("spam_detection", {})
        rate_limiting_data["spam_detection"] = SpamDetectionConfig(**spam_detection_data)
        rate_limiting = RateLimitingConfig(**rate_limiting_data)

        # ASR server конфигурация
        asr_server = ASRServerConfig(**yaml_data.get("asr_server", {}))

        # Sales flow конфигурация
        sales_flow = SalesFlowConfig(**yaml_data.get("sales_flow", {}))

        return cls(
            telegram=telegram,
            ai_server=ai_server,
            memory=memory,
            google_calendar=google_calendar,
            rate_limiting=rate_limiting,
            asr_server=asr_server,
            sales_flow=sales_flow,
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
                    f"Google Calendar credentials file not found: {creds_path}. "
                    "Either disable Google Calendar (GOOGLE_CALENDAR_ENABLED=false) "
                    "or create OAuth 2.0 credentials (Desktop app type) in Google Cloud Console."
                )

        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(
                f"  - {error}" for error in errors
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info("Configuration validated successfully")

