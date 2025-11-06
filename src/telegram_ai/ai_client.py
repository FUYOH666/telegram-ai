"""Клиент для подключения к локальному AI-серверу (OpenAI-compatible API)."""

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

        # Настраиваем таймауты: отдельно для подключения и чтения
        # httpx.Timeout требует либо default, либо все четыре параметра (connect, read, write, pool)
        timeout_config = httpx.Timeout(
            connect=15.0,  # Таймаут подключения: 15 секунд
            read=float(timeout),  # Таймаут чтения: настраиваемый через config (в секундах)
            write=10.0,  # Таймаут записи: 10 секунд
            pool=10.0,  # Таймаут пула соединений: 10 секунд
        )
        self.client = httpx.AsyncClient(
            timeout=timeout_config,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else None,
        )

        logger.info(
            f"AI Client initialized: base_url={self.base_url}, "
            f"model={self.model}, max_tokens={self.max_tokens}, timezone={timezone_name}, "
            f"timeouts(connect=15.0s, read={timeout}s, write=10.0s, pool=10.0s), max_retries={max_retries}"
        )

    def _get_date_info(self) -> str:
        """
        Получить только информацию о текущей дате и времени.

        Returns:
            Строка с информацией о текущей дате/времени
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

        # Возвращаем только информацию о дате
        return f"Текущая дата и время: {date_str}. Используй эту дату при ответах на вопросы о времени.\n\n"

    def _get_dynamic_system_prompt(self) -> str:
        """
        Получить системный промпт с актуальной датой и временем.

        Returns:
            Системный промпт с добавленной информацией о текущей дате/времени
        """
        date_info = self._get_date_info()

        if self.system_prompt:
            return date_info + self.system_prompt
        else:
            return date_info

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        # Ретраи при TimeoutException и NetworkError, НО НЕ при ReadTimeout
        # ReadTimeout означает, что сервер обрабатывает запрос, но слишком медленно - ретрай не поможет
        retry=retry_any(
            retry_if_exception_type(httpx.NetworkError),
            retry_if_exception_type(httpx.TimeoutException) & retry_unless_exception_type(httpx.ReadTimeout)
        ),
        reraise=True,
    )
    async def get_response(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_response_length: Optional[int] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        rag_system=None,
    ) -> str:
        """
        Получить ответ от AI-сервера.

        Args:
            messages: Список сообщений в формате OpenAI API
                [{"role": "user", "content": "текст"}, ...]
            temperature: Температура генерации (0.0-1.0)
            max_response_length: Максимальная длина ответа в символах (опционально)
            max_tokens: Максимальное количество токенов в ответе (опционально)
            top_p: Top-p sampling parameter (опционально)
            frequency_penalty: Frequency penalty parameter (опционально)
            presence_penalty: Presence penalty parameter (опционально)
            rag_system: Экземпляр RAGSystem для поиска релевантной информации (опционально)

        Returns:
            Ответ от AI-сервера (обрезанный до max_response_length если указано)

        Raises:
            httpx.HTTPError: При ошибке HTTP запроса
            ValueError: При некорректном ответе сервера
        """
        url = f"{self.base_url}/v1/chat/completions"

        # Всегда добавляем актуальную дату в системное сообщение
        final_messages = messages.copy()
        date_info = self._get_date_info()
        
        # Поиск релевантной информации через RAG (если включено)
        rag_context = ""
        if rag_system and rag_system.enabled:
            try:
                # Извлекаем последнее пользовательское сообщение для поиска
                user_query = ""
                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        user_query = msg.get("content", "")
                        break
                
                if user_query:
                    found_info = await rag_system.search_relevant_info(user_query)
                    if found_info:
                        rag_context = rag_system.format_context(found_info)
                        logger.debug(f"RAG found {len(found_info)} relevant chunks for query: {user_query[:50]}...")
            except Exception as e:
                logger.warning(f"Error searching RAG knowledge base: {e}", exc_info=True)
        
        if date_info or rag_context:
            # Ищем существующее системное сообщение
            system_found = False
            for msg in final_messages:
                if msg.get("role") == "system":
                    # Добавляем дату и RAG контекст в начало существующего системного сообщения
                    enhanced_content = date_info + rag_context + "\n\n" + msg["content"] if rag_context else date_info + msg["content"]
                    msg["content"] = enhanced_content
                    system_found = True
                    break
            
            # Если системного сообщения нет, добавляем основное
            if not system_found:
                dynamic_prompt = self._get_dynamic_system_prompt()
                if dynamic_prompt:
                    enhanced_prompt = date_info + rag_context + "\n\n" + dynamic_prompt if rag_context else date_info + dynamic_prompt
                    final_messages.insert(0, {"role": "system", "content": enhanced_prompt})
                else:
                    # Если нет основного промпта, добавляем только дату и RAG контекст
                    content = date_info + rag_context if rag_context else date_info
                    final_messages.insert(0, {"role": "system", "content": content})

        payload = {
            "model": self.model,
            "messages": final_messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
        }

        # Добавляем дополнительные параметры если указаны
        if top_p is not None:
            payload["top_p"] = top_p
        if frequency_penalty is not None:
            payload["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            payload["presence_penalty"] = presence_penalty

        request_start_time = time.time()
        
        try:
            logger.debug(f"Sending request to {url} with {len(final_messages)} messages (timeout={self.timeout}s)")
            response = await self.client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()

            if "choices" not in data or not data["choices"]:
                raise ValueError("Invalid response format: missing choices")

            content = data["choices"][0]["message"]["content"]
            request_time = time.time() - request_start_time
            logger.debug(f"Received response in {request_time:.2f}s: {content[:100]}...")

            # Обрезаем ответ если указана максимальная длина
            if max_response_length and len(content) > max_response_length:
                original_length = len(content)
                content = self._truncate_response(content, max_response_length)
                logger.debug(
                    f"Response truncated from {original_length} to {len(content)} characters"
                )

            # Улучшаем форматирование ответа
            content = self._format_response(content)

            return content

        except httpx.HTTPStatusError as e:
            request_time = time.time() - request_start_time
            logger.error(
                f"HTTP error from AI server after {request_time:.2f}s: "
                f"{e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.ReadTimeout as e:
            # ReadTimeout должен обрабатываться ДО TimeoutException, так как он является подклассом
            request_time = time.time() - request_start_time
            logger.error(
                f"Read timeout from AI server after {request_time:.2f}s (server took longer than {self.timeout}s to respond): {e}. "
                f"Not retrying - server is processing but too slow."
            )
            raise
        except httpx.TimeoutException as e:
            # TimeoutException для проблем подключения (не ReadTimeout)
            request_time = time.time() - request_start_time
            logger.error(
                f"Timeout connecting to AI server after {request_time:.2f}s: {e}. "
                f"Will retry if connection can be established."
            )
            raise
        except httpx.NetworkError as e:
            request_time = time.time() - request_start_time
            logger.error(
                f"Network error after {request_time:.2f}s: {e}. "
                f"Will retry if connection can be established."
            )
            raise
        except (KeyError, ValueError, TypeError) as e:
            request_time = time.time() - request_start_time
            logger.error(f"Invalid response format after {request_time:.2f}s: {e}")
            raise ValueError(f"Invalid response format: {e}") from e

    def _format_response(self, text: str) -> str:
        """
        Улучшить форматирование ответа для лучшей читаемости.

        Args:
            text: Текст ответа

        Returns:
            Отформатированный текст
        """
        if not text:
            return text

        # Если текст уже хорошо отформатирован (есть пустые строки), возвращаем как есть
        if "\n\n" in text:
            # Текст уже имеет разбивку на абзацы, но можем улучшить
            lines = text.split("\n")
            formatted_lines = []
            for line in lines:
                line = line.strip()
                if line:
                    formatted_lines.append(line)
                elif formatted_lines and formatted_lines[-1] != "":
                    # Добавляем пустую строку только если предыдущая не пустая
                    formatted_lines.append("")
            
            result = "\n".join(formatted_lines).strip()
            return result

        # Если текст длинный без разрывов (больше 200 символов), разбиваем на абзацы
        if len(text) > 200 and "\n" not in text:
            # Пытаемся разбить по предложениям
            sentences = re.split(r'([.!?]\s+)', text)
            paragraphs = []
            current_paragraph = ""
            
            for i in range(0, len(sentences), 2):
                if i + 1 < len(sentences):
                    sentence = sentences[i] + sentences[i + 1]
                else:
                    sentence = sentences[i]
                
                # Если текущий абзац + предложение больше 200 символов, начинаем новый абзац
                if current_paragraph and len(current_paragraph + sentence) > 200:
                    paragraphs.append(current_paragraph.strip())
                    current_paragraph = sentence
                else:
                    current_paragraph += sentence
            
            if current_paragraph:
                paragraphs.append(current_paragraph.strip())
            
            # Объединяем абзацы с пустыми строками между ними
            if len(paragraphs) > 1:
                return "\n\n".join(paragraphs)
        
        # Если текст короткий или уже с разрывами, возвращаем как есть
        return text.strip()

    def _truncate_response(self, text: str, max_length: int) -> str:
        """
        Обрезать ответ до максимальной длины, сохраняя целостность предложений.

        Args:
            text: Текст ответа
            max_length: Максимальная длина в символах

        Returns:
            Обрезанный текст
        """
        if len(text) <= max_length:
            return text

        # Пытаемся обрезать по предложениям
        # Находим последнее полное предложение, которое помещается в лимит
        sentences = re.split(r'([.!?]\s+)', text)
        result = ""
        
        for i in range(0, len(sentences), 2):
            if i + 1 < len(sentences):
                sentence = sentences[i] + sentences[i + 1]
            else:
                sentence = sentences[i]
            
            if len(result + sentence) <= max_length:
                result += sentence
            else:
                break
        
        # Если не получилось обрезать по предложениям, обрезаем по словам
        if not result or len(result) < max_length * 0.5:
            words = text.split()
            result = ""
            for word in words:
                if len(result + " " + word) <= max_length:
                    result += (" " + word) if result else word
                else:
                    break
        
        # Добавляем многоточие только если текст был обрезан в середине предложения
        # Если обрезка произошла по предложениям - многоточие не добавляем (предложение завершено)
        if result != text and len(result) < len(text):
            # Проверяем, закончилось ли последнее предложение пунктуацией
            if result and result[-1] not in ".!?;:":
                result = result.rstrip() + "..."
        
        return result

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

