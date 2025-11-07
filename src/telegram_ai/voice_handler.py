"""Обработка голосовых сообщений через ASR сервис."""

import logging
from io import BytesIO
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

        # Настраиваем таймауты: отдельно для подключения, чтения и записи
        # Для длинных аудио файлов нужны большие таймауты
        # write timeout должен быть достаточным для загрузки больших файлов (до 60 сек аудио)
        self.write_timeout = max(timeout * 0.5, 60.0)  # Минимум 60 секунд для загрузки файла
        timeout_config = httpx.Timeout(
            connect=15.0,  # Таймаут подключения: 15 секунд
            read=float(timeout),  # Таймаут чтения: настраиваемый (для обработки длинных аудио)
            write=self.write_timeout,  # Таймаут записи: минимум 60 секунд (загрузка файла может занять время)
            pool=10.0,  # Таймаут пула соединений: 10 секунд
        )
        self.client = httpx.AsyncClient(timeout=timeout_config)

        logger.info(
            f"VoiceHandler initialized: base_url={self.base_url}, "
            f"enabled={enabled}, timeout={timeout}s (read={timeout}s, write={self.write_timeout:.1f}s)"
        )

    async def transcribe_voice(
        self, audio_file_path: Path, language: Optional[str] = None, duration: Optional[int] = None
    ) -> str:
        """
        Транскрибировать голосовое сообщение.

        Args:
            audio_file_path: Путь к аудио файлу
            language: Код языка (опционально, например "ru", "en")
            duration: Длительность аудио в секундах (опционально, для логирования)

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
            # Получаем размер файла для логирования
            file_size = audio_file_path.stat().st_size
            duration_info = f", duration: {duration}s" if duration else ""
            logger.info(
                f"Transcribing audio file: {audio_file_path} (size: {file_size} bytes{duration_info}, "
                f"timeout: {self.timeout}s read, {self.write_timeout:.1f}s write)"
            )

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

            # Читаем файл в память перед отправкой (чтобы избежать проблем с закрытием файла)
            audio_data = audio_file_path.read_bytes()
            logger.debug(f"Read {len(audio_data)} bytes from audio file")

            # Используем BytesIO для передачи файла httpx
            # Важно: создаем BytesIO с данными и устанавливаем позицию в начало
            audio_file_obj = BytesIO(audio_data)
            audio_file_obj.seek(0)  # Убеждаемся что позиция в начале

            # Формируем multipart/form-data запрос
            files = {"file": (audio_file_path.name, audio_file_obj, mime_type)}
            data = {}
            if language:
                data["language"] = language

            logger.info(
                f"Sending POST request to {url} with file size {len(audio_data)} bytes, "
                f"language={language}, mime_type={mime_type}"
            )

            try:
                response = await self.client.post(url, files=files, data=data)
            except Exception as e:
                logger.error(f"Error sending request to ASR server: {e}", exc_info=True)
                raise
            logger.debug(f"Received response: status={response.status_code}")

            response.raise_for_status()

            result = response.json()
            logger.debug(f"Response JSON: {result}")

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

