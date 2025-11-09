"""Конфигурация приложения через pydantic-settings с поддержкой PostgreSQL и Redis."""

import logging
from pathlib import Path
from typing import List, Optional

import yaml
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Загружаем .env файл
load_dotenv()

logger = logging.getLogger(__name__)


class DatabaseConfig(BaseSettings):
    """Конфигурация базы данных."""

    # Поддержка PostgreSQL и SQLite
    url: Optional[str] = Field(
        default=None,
        description="Database URL (PostgreSQL или SQLite). Если не указан, используется SQLite по умолчанию",
    )
    # Для обратной совместимости с SQLite
    db_path: str = Field(
        default="./data/conversations.db",
        description="Путь к файлу SQLite БД (используется если url не указан)",
    )
    pool_size: int = Field(default=20, description="Размер пула соединений (PostgreSQL)")
    max_overflow: int = Field(default=10, description="Максимальное переполнение пула (PostgreSQL)")
    echo: bool = Field(default=False, description="Логировать SQL запросы")

    model_config = SettingsConfigDict(env_prefix="DATABASE_")


class RedisConfig(BaseSettings):
    """Конфигурация Redis."""

    url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL",
    )
    db: int = Field(default=0, description="Redis database number")
    decode_responses: bool = Field(default=True, description="Декодировать ответы как строки")

    model_config = SettingsConfigDict(env_prefix="REDIS_")


class TelegramConfig(BaseSettings):
    """Конфигурация Telegram."""

    api_id: int = Field(..., description="API ID из my.telegram.org")
    api_hash: str = Field(..., description="API Hash из my.telegram.org")
    phone: str = Field(..., description="Номер телефона в формате +7XXXXXXXXXX")
    session_path: str = Field(
        default="./sessions/your_bot.session",
        description="Путь к файлу сессии Telethon",
    )
    handle_private_chats: bool = Field(
        default=True, description="Обрабатывать личные чаты"
    )
    handle_groups: bool = Field(default=False, description="Обрабатывать группы")
    handle_channels: bool = Field(default=False, description="Обрабатывать каналы")

    model_config = SettingsConfigDict(env_prefix="TELEGRAM_")


class AIServerConfig(BaseSettings):
    """Конфигурация AI-сервера (vLLM)."""

    base_url: str = Field(
        default="http://localhost:8000",
        description="Базовый URL AI-сервера (vLLM или OpenAI-compatible API)",
    )
    api_key: Optional[str] = Field(
        default=None, description="API ключ (опционально)"
    )
    model: str = Field(
        default="models/Qwen3-30B-A3B-Instruct-2507-AWQ-4bit",
        description="Название модели",
    )
    timeout: int = Field(default=30, description="Таймаут запроса в секундах")
    max_retries: int = Field(
        default=3, description="Максимальное количество повторных попыток"
    )
    max_tokens: int = Field(
        default=8192, description="Максимальное количество токенов в ответе"
    )
    system_prompt: Optional[str] = Field(
        default=None, description="Системный промпт для настройки поведения модели"
    )
    temperature: float = Field(
        default=0.8, description="Температура генерации (0.0-1.0)"
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

    # Для обратной совместимости со старым кодом
    db_path: str = Field(
        default="./data/conversations.db",
        description="Путь к файлу SQLite БД (для обратной совместимости, рекомендуется использовать database.db_path)",
    )
    context_window: int = Field(
        default=10, description="Количество последних сообщений для контекста"
    )
    max_history_days: int = Field(
        default=30, description="Максимальный возраст истории в днях"
    )
    auto_summarize: bool = Field(
        default=True, description="Автоматически создавать summary для старых сообщений"
    )
    summary_threshold: int = Field(
        default=15, description="Минимальное количество сообщений для создания summary"
    )
    vector_search_enabled: bool = Field(
        default=False, description="Включить векторный поиск в истории диалогов"
    )
    vector_db_path: str = Field(
        default="./data/chroma_db", description="Путь к директории ChromaDB"
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


class ASRServerConfig(BaseSettings):
    """Конфигурация ASR сервера (существующий сервер)."""

    base_url: str = Field(
        default="http://localhost:8001",
        description="Базовый URL ASR сервера для транскрибации голосовых сообщений",
    )
    timeout: int = Field(default=180, description="Таймаут запроса в секундах (для длинных аудио)")
    enabled: bool = Field(default=True, description="Включить обработку голосовых сообщений")

    model_config = SettingsConfigDict(env_prefix="ASR_SERVER_")


# Импортируем остальные конфигурации из старого config.py для совместимости
# (SpamDetectionConfig, RateLimitingConfig и т.д. остаются без изменений)

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


class GlobalRateLimitingConfig(BaseSettings):
    """Конфигурация глобального rate limiting на уровне аккаунта."""

    enabled: bool = Field(
        default=True, description="Включить глобальный rate limiting"
    )
    messages_per_minute: int = Field(
        default=25, description="Максимальное количество сообщений в минуту на весь аккаунт"
    )
    messages_per_hour: int = Field(
        default=500, description="Максимальное количество сообщений в час на весь аккаунт"
    )


class AdaptiveRateLimitingConfig(BaseSettings):
    """Конфигурация адаптивного rate limiting."""

    enabled: bool = Field(
        default=True, description="Включить адаптивные лимиты"
    )
    reduction_on_floodwait_percent: int = Field(
        default=20, description="Снижение лимитов на X% при получении FloodWait"
    )
    recovery_period_minutes: int = Field(
        default=10, description="Период проверки восстановления лимитов (минуты)"
    )
    recovery_increment_percent: int = Field(
        default=5, description="Восстановление лимитов на X% за период без FloodWait"
    )


class ChatTypeRateLimitsConfig(BaseSettings):
    """Конфигурация лимитов по типам чатов."""

    private: int = Field(
        default=20, description="Сообщений в минуту для личных чатов"
    )
    group: int = Field(
        default=10, description="Сообщений в минуту для групп"
    )
    channel: int = Field(
        default=5, description="Сообщений в минуту для каналов"
    )


class SmartDistributionConfig(BaseSettings):
    """Конфигурация умного распределения сообщений и typing indicator."""

    enabled: bool = Field(
        default=True, description="Включить умное распределение сообщений"
    )
    typing_indicator_enabled: bool = Field(
        default=True, description="Включить показ typing indicator во время обработки"
    )

    model_config = SettingsConfigDict(
        env_prefix="RATE_LIMITING_SMART_DISTRIBUTION_"
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
    global_limits: GlobalRateLimitingConfig = Field(
        default_factory=GlobalRateLimitingConfig, description="Глобальные лимиты на уровне аккаунта"
    )
    adaptive: AdaptiveRateLimitingConfig = Field(
        default_factory=AdaptiveRateLimitingConfig, description="Адаптивные лимиты"
    )
    chat_type_limits: ChatTypeRateLimitsConfig = Field(
        default_factory=ChatTypeRateLimitsConfig, description="Лимиты по типам чатов"
    )
    smart_distribution: Optional[SmartDistributionConfig] = Field(
        default=None, description="Настройки умного распределения сообщений"
    )

    model_config = SettingsConfigDict(env_prefix="RATE_LIMITING_")


class SalesFlowConfig(BaseSettings):
    """Конфигурация скрипта продаж."""

    enabled: bool = Field(
        default=True,
        description="Включить скрипт продаж",
        json_schema_extra={"env_parse": lambda v: v.lower() in ("true", "1", "yes") if isinstance(v, str) else bool(v)},
    )
    use_langgraph: bool = Field(
        default=True,
        description="Использовать LangGraph state machine вместо простой state machine",
        json_schema_extra={"env_parse": lambda v: v.lower() in ("true", "1", "yes") if isinstance(v, str) else bool(v)},
    )

    model_config = SettingsConfigDict(env_prefix="SALES_FLOW_")


class SlotExtractionConfig(BaseSettings):
    """Конфигурация автоматического извлечения слотов."""

    enabled: bool = Field(
        default=True, description="Включить автоматическое извлечение слотов через LLM"
    )

    model_config = SettingsConfigDict(env_prefix="SLOT_EXTRACTION_")


class WebSearchConfig(BaseSettings):
    """Конфигурация Web Search MCP."""

    enabled: bool = Field(
        default=False,
        description="Включить интеграцию с Web Search MCP",
        json_schema_extra={"env_parse": lambda v: v.lower() in ("true", "1", "yes") if isinstance(v, str) else bool(v)},
    )
    mcp_server_url: str = Field(
        default="http://localhost:8080",
        description="URL MCP Web Search сервера",
    )
    max_results: int = Field(
        default=3, description="Максимальное количество результатов поиска"
    )
    max_queries_per_conversation: int = Field(
        default=2, description="Максимальное количество запросов за диалог"
    )
    timeout: int = Field(default=10, description="Таймаут запроса в секундах")

    model_config = SettingsConfigDict(env_prefix="WEB_SEARCH_")


class URLParsingConfig(BaseSettings):
    """Конфигурация парсинга URL в сообщениях."""

    enabled: bool = Field(
        default=True,
        description="Включить автоматический парсинг URL в сообщениях",
        json_schema_extra={"env_parse": lambda v: v.lower() in ("true", "1", "yes") if isinstance(v, str) else bool(v)},
    )
    max_content_length: int = Field(
        default=10000,
        description="Максимальная длина извлеченного текста (символов)",
    )
    timeout: int = Field(
        default=10, description="Таймаут запроса в секундах"
    )
    max_urls_per_message: int = Field(
        default=3, description="Максимальное количество URL для парсинга в одном сообщении"
    )

    model_config = SettingsConfigDict(env_prefix="URL_PARSING_")


class IntentClassifierConfig(BaseSettings):
    """Конфигурация классификатора намерений."""

    use_llm: bool = Field(
        default=True, description="Использовать LLM для классификации намерений"
    )
    confidence_threshold: float = Field(
        default=0.7,
        description="Минимальный порог уверенности для LLM классификации (0.0-1.0)",
    )

    model_config = SettingsConfigDict(env_prefix="INTENT_CLASSIFIER_")


class RAGConfig(BaseSettings):
    """Конфигурация RAG системы для базы знаний компании."""

    enabled: bool = Field(
        default=False,
        description="Включить RAG систему для поиска информации о компании/услугах",
        json_schema_extra={"env_parse": lambda v: v.lower() in ("true", "1", "yes") if isinstance(v, str) else bool(v)},
    )
    knowledge_base_path: Optional[str] = Field(
        default=None,
        description="Путь к директории с документацией компании (текстовые файлы .txt, .md)",
    )
    max_results: int = Field(
        default=3, description="Максимальное количество результатов поиска"
    )
    min_score: float = Field(
        default=0.7,
        description="Минимальный score для включения результата в контекст (0.0-1.0)",
    )
    auto_load_on_startup: bool = Field(
        default=True,
        description="Автоматически загружать базу знаний при старте приложения",
    )
    log_stats_interval: int = Field(
        default=100,
        description="Интервал для логирования статистики использования RAG (количество запросов)",
    )

    model_config = SettingsConfigDict(env_prefix="RAG_")


class MeetingSummaryConfig(BaseSettings):
    """Конфигурация генерации summary для встреч."""

    send_to_owner: bool = Field(
        default=True,
        description="Отправлять summary владельцу при создании встречи",
        json_schema_extra={"env_parse": lambda v: v.lower() in ("true", "1", "yes") if isinstance(v, str) else bool(v)},
    )
    owner_username: str = Field(
        default="@your_username",
        description="Username владельца для отправки summary (например, @your_username)",
    )

    model_config = SettingsConfigDict(env_prefix="MEETING_SUMMARY_")


class Config(BaseSettings):
    """Основная конфигурация приложения."""

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    telegram: TelegramConfig
    ai_server: AIServerConfig
    memory: MemoryConfig
    google_calendar: GoogleCalendarConfig
    rate_limiting: RateLimitingConfig
    asr_server: ASRServerConfig
    sales_flow: SalesFlowConfig
    slot_extraction: SlotExtractionConfig
    web_search: WebSearchConfig
    url_parsing: URLParsingConfig
    intent_classifier: IntentClassifierConfig
    rag: RAGConfig
    meeting_summary: MeetingSummaryConfig = Field(
        default_factory=MeetingSummaryConfig, description="Конфигурация summary для встреч"
    )

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

        # Database конфигурация
        database_data = yaml_data.get("database", {})
        database = DatabaseConfig(**database_data)

        # Redis конфигурация
        redis_data = yaml_data.get("redis", {})
        redis = RedisConfig(**redis_data)

        # Telegram конфигурация
        telegram = TelegramConfig(**yaml_data.get("telegram", {}))

        # AI Server конфигурация
        ai_server = AIServerConfig(**yaml_data.get("ai_server", {}))

        # Memory конфигурация
        memory = MemoryConfig(**yaml_data.get("memory", {}))

        # Google Calendar конфигурация
        google_cal_data = yaml_data.get("google_calendar", {})
        enabled_val = google_cal_data.get("enabled", False)
        if isinstance(enabled_val, str):
            google_cal_data["enabled"] = enabled_val.lower() in ("true", "1", "yes")
        elif not isinstance(enabled_val, bool):
            google_cal_data["enabled"] = bool(enabled_val)
        google_calendar = GoogleCalendarConfig(**google_cal_data)

        # Rate limiting конфигурация
        rate_limiting_data = yaml_data.get("rate_limiting", {}).copy()
        spam_detection_data = rate_limiting_data.pop("spam_detection", {})
        rate_limiting_data["spam_detection"] = SpamDetectionConfig(**spam_detection_data)

        global_limits_data = rate_limiting_data.pop("global", {})
        rate_limiting_data["global_limits"] = GlobalRateLimitingConfig(**global_limits_data)

        adaptive_data = rate_limiting_data.pop("adaptive", {})
        rate_limiting_data["adaptive"] = AdaptiveRateLimitingConfig(**adaptive_data)

        chat_type_limits_data = rate_limiting_data.pop("chat_type_limits", {})
        rate_limiting_data["chat_type_limits"] = ChatTypeRateLimitsConfig(**chat_type_limits_data)

        smart_distribution_data = rate_limiting_data.pop("smart_distribution", {})
        if smart_distribution_data:
            rate_limiting_data["smart_distribution"] = SmartDistributionConfig(**smart_distribution_data)
        else:
            rate_limiting_data["smart_distribution"] = None

        rate_limiting = RateLimitingConfig(**rate_limiting_data)

        # ASR server конфигурация
        asr_server = ASRServerConfig(**yaml_data.get("asr_server", {}))

        # Sales flow конфигурация
        sales_flow = SalesFlowConfig(**yaml_data.get("sales_flow", {}))

        # Slot extraction конфигурация
        slot_extraction = SlotExtractionConfig(**yaml_data.get("slot_extraction", {}))

        # Web Search конфигурация
        web_search_data = yaml_data.get("web_search", {})
        enabled_val = web_search_data.get("enabled", False)
        if isinstance(enabled_val, str):
            web_search_data["enabled"] = enabled_val.lower() in ("true", "1", "yes")
        elif not isinstance(enabled_val, bool):
            web_search_data["enabled"] = bool(enabled_val)
        web_search = WebSearchConfig(**web_search_data)

        # URL Parsing конфигурация
        url_parsing_data = yaml_data.get("url_parsing", {})
        enabled_val = url_parsing_data.get("enabled", True)
        if isinstance(enabled_val, str):
            url_parsing_data["enabled"] = enabled_val.lower() in ("true", "1", "yes")
        elif not isinstance(enabled_val, bool):
            url_parsing_data["enabled"] = bool(enabled_val)
        url_parsing = URLParsingConfig(**url_parsing_data)

        # Intent Classifier конфигурация
        intent_classifier = IntentClassifierConfig(**yaml_data.get("intent_classifier", {}))

        # RAG конфигурация
        rag_data = yaml_data.get("rag", {})
        enabled_val = rag_data.get("enabled", False)
        if isinstance(enabled_val, str):
            rag_data["enabled"] = enabled_val.lower() in ("true", "1", "yes")
        elif not isinstance(enabled_val, bool):
            rag_data["enabled"] = bool(enabled_val)
        rag = RAGConfig(**rag_data)

        # Meeting Summary конфигурация
        meeting_summary_data = yaml_data.get("meeting_summary", {})
        enabled_val = meeting_summary_data.get("send_to_owner", True)
        if isinstance(enabled_val, str):
            meeting_summary_data["send_to_owner"] = enabled_val.lower() in ("true", "1", "yes")
        elif not isinstance(enabled_val, bool):
            meeting_summary_data["send_to_owner"] = bool(enabled_val)
        meeting_summary = MeetingSummaryConfig(**meeting_summary_data)

        return cls(
            database=database,
            redis=redis,
            telegram=telegram,
            ai_server=ai_server,
            memory=memory,
            google_calendar=google_calendar,
            rate_limiting=rate_limiting,
            asr_server=asr_server,
            sales_flow=sales_flow,
            slot_extraction=slot_extraction,
            web_search=web_search,
            url_parsing=url_parsing,
            intent_classifier=intent_classifier,
            rag=rag,
            meeting_summary=meeting_summary,
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

    async def validate_ai_server(self) -> None:
        """
        Проверка доступности AI сервера и правильности эндпоинта.

        Raises:
            ValueError: При ошибке подключения или недоступности эндпоинта
        """
        import httpx

        base_url = self.ai_server.base_url.rstrip("/")
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Пробуем сначала /v1/models (GET запрос, безопаснее)
            try:
                response = await client.get(f"{base_url}/v1/models")
                if response.status_code == 200:
                    logger.info(f"✅ AI сервер доступен: {base_url}/v1/models")
                    return
                elif response.status_code == 404:
                    logger.warning(
                        f"⚠️  Эндпоинт /v1/models вернул 404. "
                        f"Сервер отвечает, но эндпоинт не найден. "
                        f"Проверьте правильность base_url и что сервер поддерживает OpenAI-compatible API."
                    )
                    # Пробуем проверить другие возможные пути
                    alternative_paths = [
                        "/api/v1/models",
                        "/models",
                        "/health",
                        "/",
                    ]
                    for path in alternative_paths:
                        try:
                            alt_response = await client.get(f"{base_url}{path}", follow_redirects=True)
                            if alt_response.status_code == 200:
                                logger.info(f"✅ Найден альтернативный эндпоинт: {base_url}{path}")
                                logger.warning(
                                    f"⚠️  Возможно, нужно использовать другой base_url. "
                                    f"Текущий: {base_url}, найденный эндпоинт: {path}"
                                )
                                break
                        except Exception:
                            pass
                else:
                    logger.warning(
                        f"⚠️  AI сервер вернул статус {response.status_code} для /v1/models"
                    )
            except httpx.TimeoutException:
                raise ValueError(
                    f"AI сервер недоступен (таймаут): {base_url}. "
                    "Убедитесь, что сервер запущен и доступен по указанному адресу."
                )
            except httpx.ConnectError:
                raise ValueError(
                    f"Не удалось подключиться к AI серверу: {base_url}. "
                    "Убедитесь, что сервер запущен и доступен по указанному адресу."
                )
            except Exception as e:
                logger.debug(f"Ошибка при проверке /v1/models: {e}")

            # Если /v1/models не сработал, пробуем проверить базовый URL
            try:
                response = await client.get(base_url, follow_redirects=True)
                if response.status_code in (200, 404):
                    # Сервер отвечает, но эндпоинт может быть неправильным
                    logger.warning(
                        f"⚠️  AI сервер отвечает на {base_url}, но эндпоинт /v1/models или /v1/chat/completions недоступен. "
                        f"Проверьте правильность base_url и что сервер поддерживает OpenAI-compatible API. "
                        f"Возможно, нужно добавить префикс пути (например, /api/v1/chat/completions)."
                    )
                    # Не падаем с ошибкой, только предупреждаем - возможно, эндпоинт будет работать при реальном запросе
                    return
            except Exception:
                pass

            # Если ничего не сработало, выдаем ошибку
            raise ValueError(
                f"AI сервер недоступен или эндпоинт не найден: {base_url}. "
                f"Проверьте:\n"
                f"  1. Запущен ли AI сервер (vLLM или OpenAI-compatible API)\n"
                f"  2. Правильность base_url в config.yaml или AI_SERVER_BASE_URL в .env\n"
                f"  3. Что сервер поддерживает эндпоинты /v1/models или /v1/chat/completions\n"
                f"  4. Возможно, нужен другой путь (например, /api/v1/chat/completions вместо /v1/chat/completions)"
            )

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

