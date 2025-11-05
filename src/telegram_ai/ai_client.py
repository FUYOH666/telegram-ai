"""Клиент для подключения к локальному AI-серверу (OpenAI-compatible API)."""

import logging
from typing import List, Dict, Optional

import httpx
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
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_tokens = max_tokens

        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else None,
        )

        logger.info(
            f"AI Client initialized: base_url={self.base_url}, "
            f"model={self.model}, max_tokens={self.max_tokens}"
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        reraise=True,
    )
    async def get_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
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

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
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

