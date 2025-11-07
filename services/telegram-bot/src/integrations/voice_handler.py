"""Обработка голосовых сообщений через существующий ASR сервер."""

import logging
from io import BytesIO
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class VoiceHandler:
    """Клиент для работы с существующим ASR сервисом для транскрибации голосовых сообщений."""

    def __init__(
        self,
        base_url: str,
        timeout: int = 180,
        enabled: bool = True,
    ):
        """
        Инициализация VoiceHandler.

        Args:
            base_url: Базовый URL ASR сервиса (настраивается через ASR_SERVER_BASE_URL)
            timeout: Таймаут запроса в секундах (для длинных аудио файлов)
            enabled: Включить обработку голосовых сообщений
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.enabled = enabled

        timeout_config = httpx.Timeout(
            connect=15.0,
            read=float(timeout),
            write=30.0,
            pool=10.0,
        )
        self.client = httpx.AsyncClient(timeout=timeout_config)

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
            file_size = audio_file_path.stat().st_size
            logger.info(
                f"Transcribing audio file: {audio_file_path} (size: {file_size} bytes)"
            )

            mime_types = {
                ".ogg": "audio/ogg",
                ".oga": "audio/ogg",
                ".wav": "audio/wav",
                ".mp3": "audio/mpeg",
                ".m4a": "audio/mp4",
                ".flac": "audio/flac",
                ".webm": "audio/webm",
            }
            file_ext = audio_file_path.suffix.lower()
            mime_type = mime_types.get(file_ext, "audio/ogg")

            audio_data = audio_file_path.read_bytes()
            audio_file_obj = BytesIO(audio_data)
            audio_file_obj.seek(0)

            files = {"file": (audio_file_path.name, audio_file_obj, mime_type)}
            data = {}
            if language:
                data["language"] = language

            response = await self.client.post(url, files=files, data=data)
            response.raise_for_status()

            result = response.json()
            transcript = result.get("text", "")

            if not transcript:
                logger.warning(f"Empty transcript from ASR server for {audio_file_path}")
                return ""

            logger.info(f"Transcribed {audio_file_path.name}: {len(transcript)} characters")
            return transcript

        except httpx.HTTPError as e:
            logger.error(f"HTTP error transcribing audio: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}", exc_info=True)
            raise ValueError(f"Failed to transcribe audio: {e}")

    async def close(self):
        """Закрыть HTTP клиент."""
        await self.client.aclose()
