"""Тесты для VoiceHandler."""

import pytest
from unittest.mock import AsyncMock, patch
from pathlib import Path
import tempfile
import os

from telegram_ai.voice_handler import VoiceHandler


@pytest.fixture
def voice_handler():
    """Создать VoiceHandler для тестов."""
    return VoiceHandler(
        base_url="http://localhost:8001",
        timeout=60,
        enabled=True,
    )


@pytest.mark.asyncio
async def test_voice_handler_initialization(voice_handler):
    """Тест инициализации VoiceHandler."""
    assert voice_handler.base_url == "http://localhost:8001"
    assert voice_handler.timeout == 60
    assert voice_handler.enabled is True
    await voice_handler.close()


@pytest.mark.asyncio
async def test_voice_handler_transcribe_success(voice_handler):
    """Тест успешной транскрибации."""
    # Создаем временный аудио файл
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(b"fake audio data")
        audio_path = Path(f.name)

    try:
        mock_response_data = {"text": "Транскрибированный текст"}

        with patch.object(voice_handler.client, "post", new_callable=AsyncMock) as mock_post:
            mock_response = AsyncMock()
            mock_response.json = lambda: mock_response_data
            mock_response.raise_for_status = lambda: None
            mock_post.return_value = mock_response

            result = await voice_handler.transcribe_voice(audio_path, language="ru")
            assert result == "Транскрибированный текст"
            mock_post.assert_called_once()

    finally:
        if audio_path.exists():
            os.unlink(audio_path)

    await voice_handler.close()


@pytest.mark.asyncio
async def test_voice_handler_file_not_found(voice_handler):
    """Тест обработки отсутствующего файла."""
    fake_path = Path("/nonexistent/file.ogg")

    with pytest.raises(FileNotFoundError):
        await voice_handler.transcribe_voice(fake_path)

    await voice_handler.close()


@pytest.mark.asyncio
async def test_voice_handler_disabled(voice_handler):
    """Тест работы при отключенном handler."""
    voice_handler.enabled = False

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(b"fake audio data")
        audio_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="disabled"):
            await voice_handler.transcribe_voice(audio_path)
    finally:
        if audio_path.exists():
            os.unlink(audio_path)

    await voice_handler.close()


@pytest.mark.asyncio
async def test_voice_handler_empty_response(voice_handler):
    """Тест обработки пустого ответа от ASR."""
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(b"fake audio data")
        audio_path = Path(f.name)

    try:
        mock_response_data = {"text": ""}  # Пустой текст

        with patch.object(voice_handler.client, "post", new_callable=AsyncMock) as mock_post:
            mock_response = AsyncMock()
            mock_response.json = lambda: mock_response_data
            mock_response.raise_for_status = lambda: None
            mock_post.return_value = mock_response

            with pytest.raises(ValueError, match="empty"):
                await voice_handler.transcribe_voice(audio_path)

    finally:
        if audio_path.exists():
            os.unlink(audio_path)

    await voice_handler.close()













