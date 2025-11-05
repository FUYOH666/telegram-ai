"""Интеграция с MCP Web Search сервером для получения актуальных данных."""

import logging
from typing import Dict, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class WebSearchTool:
    """Инструмент для веб-поиска через MCP Web Search сервер."""

    def __init__(
        self,
        mcp_server_url: str,
        timeout: int = 10,
        max_results: int = 3,
        max_retries: int = 3,
        max_queries_per_conversation: int = 2,
    ):
        """
        Инициализация WebSearchTool.

        Args:
            mcp_server_url: URL MCP Web Search сервера
            timeout: Таймаут запроса в секундах
            max_results: Максимальное количество результатов
            max_retries: Максимальное количество повторных попыток
            max_queries_per_conversation: Максимальное количество запросов за диалог
        """
        self.mcp_server_url = mcp_server_url.rstrip("/")
        self.timeout = timeout
        self.max_results = max_results
        self.max_retries = max_retries
        self.max_queries_per_conversation = max_queries_per_conversation

        timeout_config = httpx.Timeout(
            connect=5.0,
            read=float(timeout),
            write=5.0,
            pool=5.0,
        )
        self.client = httpx.AsyncClient(timeout=timeout_config)

        logger.info(
            f"WebSearchTool initialized: mcp_server_url={self.mcp_server_url}, "
            f"timeout={timeout}s, max_results={max_results}"
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
        reraise=True,
    )
    async def search(self, query: str, max_results: Optional[int] = None) -> Dict:
        """
        Выполнить поиск в интернете.

        Args:
            query: Поисковый запрос
            max_results: Максимальное количество результатов (использует self.max_results если не указано)

        Returns:
            Словарь с результатами поиска:
            {
                "answer": str,  # Краткий ответ на основе результатов
                "results": List[Dict],  # Список результатов с полями url, title, snippet
            }

        Raises:
            httpx.HTTPError: При ошибке HTTP запроса
            ValueError: При некорректном ответе сервера
        """
        url = f"{self.mcp_server_url}/search"
        results_count = max_results if max_results is not None else self.max_results

        payload = {
            "query": query,
            "max_results": results_count,
        }

        try:
            logger.debug(f"Searching web for: {query}")
            response = await self.client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()

            # Проверяем формат ответа
            if not isinstance(data, dict):
                raise ValueError(f"Invalid response format: expected dict, got {type(data)}")

            # Нормализуем ответ
            result = {
                "answer": data.get("answer", ""),
                "results": data.get("results", []),
            }

            logger.debug(
                f"Web search completed: found {len(result['results'])} results, "
                f"answer length={len(result['answer'])}"
            )

            return result

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error from MCP Web Search server: "
                f"{e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.TimeoutException as e:
            logger.error(f"Timeout connecting to MCP Web Search server: {e}")
            raise
        except httpx.NetworkError as e:
            logger.error(f"Network error connecting to MCP Web Search server: {e}")
            raise
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Invalid response format from MCP Web Search server: {e}")
            raise ValueError(f"Invalid response format: {e}") from e

    def format_search_results(self, search_result: Dict) -> str:
        """
        Форматировать результаты поиска для включения в промпт.

        Args:
            search_result: Результат поиска от метода search()

        Returns:
            Отформатированная строка с результатами поиска
        """
        answer = search_result.get("answer", "")
        results = search_result.get("results", [])

        if not answer and not results:
            return ""

        formatted = []
        if answer:
            formatted.append(f"Результаты поиска:\n{answer}")

        if results:
            sources = []
            for i, result in enumerate(results[:3], 1):  # Максимум 3 источника
                url = result.get("url", "")
                title = result.get("title", "")
                if url:
                    sources.append(f"{i}. {title} ({url})" if title else f"{i}. {url}")

            if sources:
                formatted.append("\nИсточники:\n" + "\n".join(sources))

        return "\n".join(formatted)

    async def close(self):
        """Закрыть HTTP клиент."""
        await self.client.aclose()
        logger.info("WebSearchTool closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

