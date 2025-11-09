"""Парсинг веб-страниц из URL в сообщениях пользователей."""

import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False
    logging.warning("trafilatura not available, will use BeautifulSoup fallback")

logger = logging.getLogger(__name__)


class URLParser:
    """Парсер веб-страниц для извлечения текстового содержимого."""

    def __init__(
        self,
        timeout: int = 10,
        max_content_length: int = 10000,
        max_urls_per_message: int = 3,
    ):
        """
        Инициализация URLParser.

        Args:
            timeout: Таймаут запроса в секундах
            max_content_length: Максимальная длина извлеченного текста
            max_urls_per_message: Максимальное количество URL для парсинга в одном сообщении
        """
        self.timeout = timeout
        self.max_content_length = max_content_length
        self.max_urls_per_message = max_urls_per_message

        # Настраиваем таймауты для httpx
        timeout_config = httpx.Timeout(
            connect=5.0,
            read=float(timeout),
            write=5.0,
            pool=5.0,
        )
        self.client = httpx.AsyncClient(
            timeout=timeout_config,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; TelegramAI/1.0; +https://scanovich.ai)"
            },
        )

        logger.info(
            f"URLParser initialized: timeout={timeout}s, "
            f"max_content_length={max_content_length}, "
            f"max_urls_per_message={max_urls_per_message}, "
            f"trafilatura_available={TRAFILATURA_AVAILABLE}"
        )

    @staticmethod
    def extract_urls(text: str) -> List[str]:
        """
        Извлечь все URL из текста.

        Args:
            text: Текст для поиска URL

        Returns:
            Список найденных URL
        """
        # Регулярное выражение для поиска URL
        # Более гибкое выражение, которое правильно обрабатывает дефисы и другие символы в URL
        url_pattern = re.compile(
            r"https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[-\w/_.~!*'();:@&=+$,?#\[\]%])*(?:\?(?:[-\w&=%.~!*'();:@+$,?#\[\]])*)?(?:#(?:[-\w.~!*'();:@&=+$,?#\[\]%])*)?)?",
            re.IGNORECASE,
        )

        urls = url_pattern.findall(text)
        logger.debug(f"Extracted URLs from text (before normalization): {urls}")
        # Нормализуем URL (убираем завершающие знаки препинания)
        normalized_urls = []
        for url in urls:
            # Убираем завершающие точки, запятые и другие знаки препинания
            url = url.rstrip(".,;:!?)")
            # Проверяем что это валидный URL
            try:
                parsed = urlparse(url)
                if parsed.scheme and parsed.netloc:
                    normalized_urls.append(url)
            except Exception:
                continue

        # Убираем дубликаты, сохраняя порядок
        seen = set()
        unique_urls = []
        for url in normalized_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        logger.debug(f"Extracted {len(unique_urls)} URLs from text: {unique_urls}")
        return unique_urls

    async def parse_url(self, url: str) -> Optional[Dict[str, str]]:
        """
        Парсить содержимое веб-страницы.

        Args:
            url: URL для парсинга

        Returns:
            Словарь с полями:
            - url: исходный URL
            - title: заголовок страницы
            - content: извлеченный текст
            - success: успешно ли извлечен контент
            Или None если парсинг не удался
        """
        try:
            logger.info(f"Parsing URL: {url}")

            # Загружаем страницу
            try:
                response = await self.client.get(url)
                response.raise_for_status()

                # Проверяем Content-Type
                content_type = response.headers.get("content-type", "").lower()
                if "text/html" not in content_type:
                    logger.warning(
                        f"URL {url} returned non-HTML content type: {content_type}"
                    )
                    return None

                html_content = response.text

                # Проверяем размер страницы (макс. 5MB)
                if len(html_content) > 5 * 1024 * 1024:
                    logger.warning(f"URL {url} content too large: {len(html_content)} bytes")
                    return None

            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error for URL {url}: {e.response.status_code}")
                return None
            except httpx.TimeoutException:
                logger.warning(f"Timeout loading URL {url}")
                return None
            except httpx.NetworkError as e:
                logger.warning(f"Network error loading URL {url}: {e}")
                return None
            except Exception as e:
                logger.error(f"Error loading URL {url}: {e}", exc_info=True)
                return None

            # Пробуем извлечь контент через trafilatura (предпочтительный метод)
            content = None
            title = None

            if TRAFILATURA_AVAILABLE:
                try:
                    # Извлекаем основной текст
                    extracted = trafilatura.extract(
                        html_content,
                        include_comments=False,
                        include_tables=False,
                        include_images=False,
                        include_links=False,
                    )
                    if extracted:
                        content = extracted.strip()
                        logger.debug(f"Extracted {len(content)} chars using trafilatura")

                    # Извлекаем метаданные (заголовок)
                    metadata = trafilatura.extract_metadata(html_content)
                    if metadata:
                        title = metadata.title or metadata.sitename
                except Exception as e:
                    logger.debug(f"trafilatura extraction failed for {url}: {e}")

            # Fallback на BeautifulSoup если trafilatura не сработал
            if not content:
                try:
                    soup = BeautifulSoup(html_content, "html.parser")

                    # Удаляем скрипты и стили
                    for script in soup(["script", "style", "nav", "footer", "header"]):
                        script.decompose()

                    # Извлекаем заголовок
                    if not title:
                        title_tag = soup.find("title")
                        if title_tag:
                            title = title_tag.get_text().strip()
                        else:
                            # Пробуем h1
                            h1_tag = soup.find("h1")
                            if h1_tag:
                                title = h1_tag.get_text().strip()

                    # Извлекаем основной текст
                    # Пробуем найти main или article тег
                    main_content = soup.find("main") or soup.find("article")
                    if main_content:
                        content = main_content.get_text(separator="\n", strip=True)
                    else:
                        # Извлекаем весь body
                        body = soup.find("body")
                        if body:
                            content = body.get_text(separator="\n", strip=True)
                        else:
                            content = soup.get_text(separator="\n", strip=True)

                    # Очищаем текст
                    if content:
                        # Удаляем множественные пробелы и переносы
                        lines = [line.strip() for line in content.split("\n") if line.strip()]
                        content = "\n".join(lines)
                        logger.debug(f"Extracted {len(content)} chars using BeautifulSoup")

                except Exception as e:
                    logger.error(f"BeautifulSoup extraction failed for {url}: {e}", exc_info=True)
                    return None

            if not content or len(content.strip()) < 50:
                logger.warning(f"URL {url} yielded insufficient content: {len(content) if content else 0} chars")
                return None

            # Ограничиваем длину контента
            if len(content) > self.max_content_length:
                content = content[:self.max_content_length].rsplit(" ", 1)[0] + "..."
                logger.debug(f"Truncated content to {len(content)} chars")

            result = {
                "url": url,
                "title": title or "Без названия",
                "content": content,
                "success": True,
            }

            logger.info(
                f"Successfully parsed URL {url}: title='{title}', "
                f"content_length={len(content)}"
            )

            return result

        except Exception as e:
            logger.error(f"Unexpected error parsing URL {url}: {e}", exc_info=True)
            return None

    async def parse_urls_from_text(self, text: str) -> List[Dict[str, str]]:
        """
        Извлечь URL из текста и распарсить их содержимое.

        Args:
            text: Текст для поиска и парсинга URL

        Returns:
            Список словарей с результатами парсинга (см. parse_url)
        """
        logger.info(f"parse_urls_from_text called with text: {text[:200]}...")
        urls = self.extract_urls(text)

        if not urls:
            logger.info(f"No URLs found in text: {text[:200]}...")
            return []

        logger.info(f"Found {len(urls)} URLs: {urls}")

        # Ограничиваем количество URL
        urls_to_parse = urls[:self.max_urls_per_message]
        logger.info(f"Parsing {len(urls_to_parse)} URLs (limited from {len(urls)})")

        results = []
        for url in urls_to_parse:
            logger.info(f"Parsing URL: {url}")
            parsed = await self.parse_url(url)
            if parsed:
                results.append(parsed)

        logger.info(f"Parsed {len(results)}/{len(urls_to_parse)} URLs from text")
        return results

    def format_parsed_content(self, parsed_results: List[Dict[str, str]]) -> str:
        """
        Форматировать результаты парсинга для включения в контекст.

        Args:
            parsed_results: Список результатов парсинга от parse_urls_from_text

        Returns:
            Отформатированная строка для включения в промпт
        """
        if not parsed_results:
            return ""

        formatted_parts = []
        for i, result in enumerate(parsed_results, 1):
            url = result["url"]
            title = result["title"]
            content = result["content"]

            part = f"Содержимое веб-страницы {i} ({title}):\nURL: {url}\n\n{content}"
            formatted_parts.append(part)

        formatted = "\n\n---\n\n".join(formatted_parts)
        formatted += "\n\nИспользуй эту информацию для ответа, но не повторяй источники дословно."

        return formatted

    async def close(self):
        """Закрыть HTTP клиент."""
        await self.client.aclose()
        logger.info("URLParser closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

