"""Тесты для AI Client."""

import pytest
from unittest.mock import AsyncMock, patch

from telegram_ai.ai_client import AIClient


@pytest.mark.asyncio
async def test_ai_client_initialization():
    """Тест инициализации AI Client."""
    client = AIClient(
        base_url="http://localhost:8000",
        model="test-model",
        timeout=30,
        max_retries=3,
        max_tokens=4096,
    )
    assert client.base_url == "http://localhost:8000"
    assert client.model == "test-model"
    assert client.timeout == 30
    await client.close()


@pytest.mark.asyncio
async def test_ai_client_get_response():
    """Тест получения ответа от AI-сервера."""
    client = AIClient(
        base_url="http://localhost:8000",
        model="test-model",
    )

    mock_response_data = {
        "choices": [
            {
                "message": {
                    "content": "Test response"
                }
            }
        ]
    }

    with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_response = AsyncMock()
        mock_response.json = lambda: mock_response_data
        mock_response.raise_for_status = lambda: None
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "Hello"}]
        response = await client.get_response(messages)

        assert response == "Test response"
        mock_post.assert_called_once()

    await client.close()

