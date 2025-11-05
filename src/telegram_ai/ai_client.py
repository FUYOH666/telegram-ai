"""Клиент для подключения к локальному AI-серверу (OpenAI-compatible API)."""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional

import httpx
import pytz
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)


class AIClient:
    """Клиент для взаимодействия с локальным AI-сервером через OpenAI-compatible API."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        max_tokens: int = 4096,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        timezone_name: str = "Europe/Moscow",
        date_format: Optional[str] = None,
    ):
        """
        Инициализация AI клиента.

        Args:
            base_url: Базовый URL AI-сервера
            model: Название модели
            api_key: API ключ (опционально)
            timeout: Таймаут запроса в секундах
            max_retries: Максимальное количество повторных попыток
            max_tokens: Максимальное количество токенов в ответе
            system_prompt: Базовый системный промпт
            temperature: Температура генерации
            timezone_name: Название часового пояса (например, "Europe/Moscow")
            date_format: Формат даты (опционально, используется дефолтный если None)
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.timezone_name = timezone_name
        self.date_format = date_format or "%d %B %Y года, %A, %H:%M (МСК)"

        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else None,
        )

        logger.info(
            f"AI Client initialized: base_url={self.base_url}, "
            f"model={self.model}, max_tokens={self.max_tokens}, timezone={timezone_name}"
        )

    def _get_dynamic_system_prompt(self) -> str:
        """
        Получить системный промпт с актуальной датой и временем.

        Returns:
            Системный промпт с добавленной информацией о текущей дате/времени
        """
        # Получаем текущее время в UTC
        now_utc = datetime.now(timezone.utc)

        # Конвертируем в указанный часовой пояс
        try:
            tz = pytz.timezone(self.timezone_name)
            now_local = now_utc.astimezone(tz)
        except pytz.exceptions.UnknownTimeZoneError:
            logger.warning(f"Unknown timezone: {self.timezone_name}, using UTC")
            now_local = now_utc

        # Форматируем дату на русском языке
        # Используем русские названия дней недели и месяцев
        weekday_names = {
            0: "понедельник",
            1: "вторник",
            2: "среда",
            3: "четверг",
            4: "пятница",
            5: "суббота",
            6: "воскресенье",
        }
        month_names = {
            1: "января",
            2: "февраля",
            3: "марта",
            4: "апреля",
            5: "мая",
            6: "июня",
            7: "июля",
            8: "августа",
            9: "сентября",
            10: "октября",
            11: "ноября",
            12: "декабря",
        }

        # Форматируем дату вручную для русского языка
        day = now_local.day
        month = month_names[now_local.month]
        year = now_local.year
        weekday = weekday_names[now_local.weekday()]
        hour = now_local.hour
        minute = now_local.minute

        date_str = f"{day} {month} {year} года, {weekday}, {hour:02d}:{minute:02d} (МСК)"

        # Добавляем информацию о дате в начало системного промпта
        date_info = f"Текущая дата и время: {date_str}. Используй эту дату при ответах на вопросы о времени.\n\n"

        if self.system_prompt:
            return date_info + self.system_prompt
        else:
            return date_info

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        reraise=True,
    )
    async def get_response(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
    ) -> str:
        """
        Получить ответ от AI-сервера.

        Args:
            messages: Список сообщений в формате OpenAI API
                [{"role": "user", "content": "текст"}, ...]
            temperature: Температура генерации (0.0-1.0)

        Returns:
            Ответ от AI-сервера

        Raises:
            httpx.HTTPError: При ошибке HTTP запроса
            ValueError: При некорректном ответе сервера
        """
        url = f"{self.base_url}/v1/chat/completions"

        # Добавляем системный промпт с актуальной датой если есть
        final_messages = messages.copy()
        dynamic_prompt = self._get_dynamic_system_prompt()
        if dynamic_prompt:
            # Проверяем есть ли уже системное сообщение
            if not any(msg.get("role") == "system" for msg in final_messages):
                final_messages.insert(0, {"role": "system", "content": dynamic_prompt})

        payload = {
            "model": self.model,
            "messages": final_messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": self.max_tokens,
        }

        try:
            logger.debug(f"Sending request to {url} with {len(messages)} messages")
            response = await self.client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()

            if "choices" not in data or not data["choices"]:
                raise ValueError("Invalid response format: missing choices")

            content = data["choices"][0]["message"]["content"]
            logger.debug(f"Received response: {content[:100]}...")

            return content

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from AI server: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.TimeoutException as e:
            logger.error(f"Timeout connecting to AI server: {e}")
            raise
        except httpx.NetworkError as e:
            logger.error(f"Network error: {e}")
            raise
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Invalid response format: {e}")
            raise ValueError(f"Invalid response format: {e}") from e

    async def close(self):
        """Закрыть HTTP клиент."""
        await self.client.aclose()
        logger.info("AI Client closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

