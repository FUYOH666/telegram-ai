"""Клиент для подключения к существующему vLLM серверу (OpenAI-compatible API)."""

import logging
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
import pytz
from tenacity import (
    retry,
    retry_any,
    retry_if_exception_type,
    retry_unless_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class AIClient:
    """Клиент для взаимодействия с существующим vLLM сервером через OpenAI-compatible API."""

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
            base_url: Базовый URL vLLM или OpenAI-compatible сервера (настраивается через AI_SERVER_BASE_URL)
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

        # Настраиваем таймауты: отдельно для подключения и чтения
        timeout_config = httpx.Timeout(
            connect=15.0,
            read=float(timeout),
            write=10.0,
            pool=10.0,
        )
        self.client = httpx.AsyncClient(
            timeout=timeout_config,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else None,
        )

        logger.info(
            f"AI Client initialized: base_url={self.base_url}, "
            f"model={self.model}, max_tokens={self.max_tokens}, timezone={timezone_name}"
        )

    def _get_date_info(self) -> str:
        """Получить информацию о текущей дате и времени."""
        now_utc = datetime.now(timezone.utc)
        try:
            tz = pytz.timezone(self.timezone_name)
            now_local = now_utc.astimezone(tz)
        except pytz.exceptions.UnknownTimeZoneError:
            logger.warning(f"Unknown timezone: {self.timezone_name}, using UTC")
            now_local = now_utc

        weekday_names = {
            0: "понедельник", 1: "вторник", 2: "среда", 3: "четверг",
            4: "пятница", 5: "суббота", 6: "воскресенье",
        }
        month_names = {
            1: "января", 2: "февраля", 3: "марта", 4: "апреля",
            5: "мая", 6: "июня", 7: "июля", 8: "августа",
            9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
        }

        day = now_local.day
        month = month_names[now_local.month]
        year = now_local.year
        weekday = weekday_names[now_local.weekday()]
        hour = now_local.hour
        minute = now_local.minute

        date_str = f"{day} {month} {year} года, {weekday}, {hour:02d}:{minute:02d} (МСК)"
        return f"Текущая дата и время: {date_str}. Используй эту дату при ответах на вопросы о времени.\n\n"

    def _get_dynamic_system_prompt(self) -> str:
        """Получить системный промпт с актуальной датой и временем."""
        date_info = self._get_date_info()
        if self.system_prompt:
            return date_info + self.system_prompt
        return date_info

    @retry(
        retry=retry_any(
            retry_if_exception_type(httpx.NetworkError),
            retry_if_exception_type(httpx.TimeoutException),
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def get_response(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """
        Получить ответ от AI сервера.

        Args:
            messages: Список сообщений в формате OpenAI API
            temperature: Температура генерации (опционально)
            max_tokens: Максимальное количество токенов (опционально)
            **kwargs: Дополнительные параметры

        Returns:
            Текст ответа от AI
        """
        # Добавляем системный промпт с датой/временем
        system_prompt = self._get_dynamic_system_prompt()
        if messages and messages[0].get("role") != "system":
            messages = [{"role": "system", "content": system_prompt}] + messages
        elif messages and messages[0].get("role") == "system":
            messages[0]["content"] = system_prompt + messages[0].get("content", "")

        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            **kwargs,
        }

        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except httpx.ReadTimeout:
            logger.error(f"Read timeout when calling AI server: {url}")
            raise
        except Exception as e:
            logger.error(f"Error calling AI server: {e}", exc_info=True)
            raise

    async def close(self):
        """Закрыть HTTP клиент."""
        await self.client.aclose()
