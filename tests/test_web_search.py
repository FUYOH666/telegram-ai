"""Тесты для WebSearchTool."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from telegram_ai.web_search import WebSearchTool


@pytest.fixture
def web_search_tool():
    """Создать WebSearchTool для тестов."""
    return WebSearchTool(
        mcp_server_url="http://localhost:8080",
        timeout=10,
        max_results=3,
        max_queries_per_conversation=2,
    )


def test_web_search_tool_initialization(web_search_tool):
    """Тест инициализации WebSearchTool."""
    assert web_search_tool.mcp_server_url == "http://localhost:8080"
    assert web_search_tool.timeout == 10
    assert web_search_tool.max_results == 3
    assert web_search_tool.max_queries_per_conversation == 2


@pytest.mark.asyncio
async def test_web_search_success(web_search_tool):
    """Тест успешного поиска."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "answer": "Это ответ на запрос",
        "results": [
            {"url": "https://example.com", "title": "Example", "snippet": "Some text"},
            {"url": "https://test.com", "title": "Test", "snippet": "More text"},
        ],
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(web_search_tool.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        result = await web_search_tool.search("test query")

        assert result["answer"] == "Это ответ на запрос"
        assert len(result["results"]) == 2
        assert result["results"][0]["url"] == "https://example.com"
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_web_search_timeout(web_search_tool):
    """Тест обработки таймаута."""
    with patch.object(web_search_tool.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Request timeout")

        with pytest.raises(httpx.TimeoutException):
            await web_search_tool.search("test query")


@pytest.mark.asyncio
async def test_web_search_network_error(web_search_tool):
    """Тест обработки сетевой ошибки."""
    with patch.object(web_search_tool.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.NetworkError("Network error")

        with pytest.raises(httpx.NetworkError):
            await web_search_tool.search("test query")


@pytest.mark.asyncio
async def test_web_search_http_error(web_search_tool):
    """Тест обработки HTTP ошибки."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server error", request=MagicMock(), response=mock_response
    )

    with patch.object(web_search_tool.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            await web_search_tool.search("test query")


def test_format_search_results(web_search_tool):
    """Тест форматирования результатов поиска."""
    search_result = {
        "answer": "Это ответ на запрос",
        "results": [
            {"url": "https://example.com", "title": "Example"},
            {"url": "https://test.com", "title": "Test"},
        ],
    }

    formatted = web_search_tool.format_search_results(search_result)

    assert "Результаты поиска:" in formatted
    assert "Это ответ на запрос" in formatted
    assert "Источники:" in formatted
    assert "example.com" in formatted
    assert "test.com" in formatted


def test_format_search_results_empty(web_search_tool):
    """Тест форматирования пустых результатов."""
    search_result = {"answer": "", "results": []}

    formatted = web_search_tool.format_search_results(search_result)

    assert formatted == ""


def test_format_search_results_no_answer(web_search_tool):
    """Тест форматирования результатов без ответа."""
    search_result = {
        "answer": "",
        "results": [{"url": "https://example.com", "title": "Example"}],
    }

    formatted = web_search_tool.format_search_results(search_result)

    assert "Источники:" in formatted
    assert "example.com" in formatted


@pytest.mark.asyncio
async def test_web_search_close(web_search_tool):
    """Тест закрытия клиента."""
    with patch.object(web_search_tool.client, "aclose", new_callable=AsyncMock) as mock_close:
        await web_search_tool.close()
        mock_close.assert_called_once()


@pytest.mark.asyncio
async def test_web_search_context_manager(web_search_tool):
    """Тест использования как контекстного менеджера."""
    with patch.object(web_search_tool.client, "aclose", new_callable=AsyncMock) as mock_close:
        async with web_search_tool:
            pass
        mock_close.assert_called_once()














