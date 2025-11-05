"""Обработка голосовых сообщений через ASR сервис."""

import logging
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class VoiceHandler:
    """Клиент для работы с ASR сервисом для транскрибации голосовых сообщений."""

    def __init__(
        self,
        base_url: str,
        timeout: int = 60,
        enabled: bool = True,
    ):
        """
        Инициализация VoiceHandler.

        Args:
            base_url: Базовый URL ASR сервиса
            timeout: Таймаут запроса в секундах
            enabled: Включить обработку голосовых сообщений
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.enabled = enabled

        self.client = httpx.AsyncClient(timeout=timeout)

        logger.info(
            f"VoiceHandler initialized: base_url={self.base_url}, "
            f"enabled={enabled}, timeout={timeout}"
        )

    async def transcribe_voice(
        self, audio_file_path: Path, language: Optional[str] = None
    ) -> str:
        """
        Транскрибировать голосовое сообщение.

        Args:
            audio_file_path: Путь к аудио файлу
            language: Код языка (опционально, например "ru", "en")

        Returns:
            Транскрибированный текст

        Raises:
            httpx.HTTPError: При ошибке HTTP запроса
            ValueError: При некорректном ответе сервера
        """
        if not self.enabled:
            raise ValueError("VoiceHandler is disabled")

        if not audio_file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

        url = f"{self.base_url}/transcribe"

        try:
            logger.info(f"Transcribing audio file: {audio_file_path}")

            # Определяем MIME-тип по расширению файла
            mime_types = {
                ".ogg": "audio/ogg",
                ".oga": "audio/ogg",  # .oga это тоже Ogg контейнер
                ".wav": "audio/wav",
                ".mp3": "audio/mpeg",
                ".m4a": "audio/mp4",
                ".flac": "audio/flac",
                ".webm": "audio/webm",
            }
            file_ext = audio_file_path.suffix.lower()
            mime_type = mime_types.get(file_ext, "audio/ogg")  # По умолчанию audio/ogg

            # Открываем файл и отправляем multipart/form-data запрос
            with open(audio_file_path, "rb") as audio_file:
                # Используем правильное имя файла и MIME-тип
                files = {"file": (audio_file_path.name, audio_file, mime_type)}
                data = {}
                if language:
                    data["language"] = language

                response = await self.client.post(url, files=files, data=data)
                response.raise_for_status()

                result = response.json()

                # Извлекаем текст из ответа
                text = result.get("text", "")
                if not text:
                    logger.warning(f"No text in ASR response: {result}")
                    raise ValueError("ASR service returned empty transcription")

                logger.info(f"Transcription successful: {len(text)} characters")
                logger.debug(f"Transcribed text: {text[:100]}...")

                return text

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error from ASR server: {e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.TimeoutException as e:
            logger.error(f"Timeout connecting to ASR server: {e}")
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
        logger.info("VoiceHandler closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

