"""Тесты для Tools."""

import pytest
import json
from unittest.mock import Mock

from telegram_ai.tools import Tools


@pytest.fixture
def mock_memory():
    """Создать mock Memory для тестов."""
    memory = Mock()
    memory.get_user_context = Mock(return_value=None)
    memory.save_user_context = Mock()
    return memory


@pytest.fixture
def tools(mock_memory):
    """Создать Tools для тестов."""
    return Tools(memory=mock_memory)


def test_tools_initialization(tools):
    """Тест инициализации Tools."""
    assert tools is not None
    assert tools.memory is not None


def test_save_lead_without_memory():
    """Тест сохранения лида без Memory."""
    tools = Tools(memory=None)
    result = tools.save_lead(user_id=123)
    assert result["status"] == "error"
    assert "Memory not available" in result["error"]


def test_save_lead_new_lead(tools, mock_memory):
    """Тест сохранения нового лида."""
    mock_memory.get_user_context.return_value = None
    
    result = tools.save_lead(
        user_id=123,
        name="Тестовый Пользователь",
        lang="ru",
        contact="+79991234567",
        source="telegram",
        slots={"goal": "автоматизация", "budget": "10k"},
        notes="Тестовые заметки"
    )
    
    assert result["status"] == "saved"
    assert result["user_id"] == 123
    assert result["lead_id"] == "lead_123"
    
    # Проверяем что контекст был сохранен
    assert mock_memory.save_user_context.called
    call_args = mock_memory.save_user_context.call_args
    assert call_args[0][0] == 123  # user_id
    
    # Проверяем содержимое сохраненного контекста
    saved_context = call_args[0][1]
    data = json.loads(saved_context)
    assert data["name"] == "Тестовый Пользователь"
    assert data["lang"] == "ru"
    assert data["contact"] == "+79991234567"
    assert data["source"] == "telegram"
    assert data["slots"]["goal"] == "автоматизация"
    assert data["slots"]["budget"] == "10k"
    assert data["notes"] == "Тестовые заметки"
    assert "lead_saved_at" in data
    assert data["lead_status"] == "active"


def test_save_lead_update_existing(tools, mock_memory):
    """Тест обновления существующего лида."""
    existing_context = json.dumps({
        "intent": "SALES_AI",
        "sales_stage": "needs_discovery",
        "slots": {"goal": "старая цель"}
    })
    mock_memory.get_user_context.return_value = existing_context
    
    result = tools.save_lead(
        user_id=123,
        name="Обновленное Имя",
        contact="новый@email.com",
        slots={"goal": "новая цель", "budget": "20k"}
    )
    
    assert result["status"] == "saved"
    
    # Проверяем что данные объединились
    call_args = mock_memory.save_user_context.call_args
    saved_context = call_args[0][1]
    data = json.loads(saved_context)
    
    # Старые данные сохранились
    assert data["intent"] == "SALES_AI"
    assert data["sales_stage"] == "needs_discovery"
    
    # Новые данные добавились
    assert data["name"] == "Обновленное Имя"
    assert data["contact"] == "новый@email.com"
    assert data["slots"]["goal"] == "новая цель"  # Обновилось
    assert data["slots"]["budget"] == "20k"  # Добавилось


def test_save_lead_minimal_data(tools, mock_memory):
    """Тест сохранения лида с минимальными данными."""
    mock_memory.get_user_context.return_value = None
    
    result = tools.save_lead(user_id=456)
    
    assert result["status"] == "saved"
    
    call_args = mock_memory.save_user_context.call_args
    saved_context = call_args[0][1]
    data = json.loads(saved_context)
    
    assert data["lang"] == "ru"  # Дефолтное значение
    assert data["source"] == "telegram"  # Дефолтное значение
    assert "lead_saved_at" in data
    assert data["lead_status"] == "active"


def test_get_lead_data_without_memory():
    """Тест получения данных лида без Memory."""
    tools = Tools(memory=None)
    result = tools.get_lead_data(user_id=123)
    assert result is None


def test_get_lead_data_not_found(tools, mock_memory):
    """Тест получения данных лида когда контекст отсутствует."""
    mock_memory.get_user_context.return_value = None
    
    result = tools.get_lead_data(user_id=123)
    assert result is None


def test_get_lead_data_found(tools, mock_memory):
    """Тест получения данных лида когда контекст существует."""
    context_data = json.dumps({
        "name": "Тестовый Пользователь",
        "lang": "ru",
        "contact": "+79991234567",
        "source": "telegram",
        "intent": "SALES_AI",
        "sales_stage": "needs_discovery",
        "slots": {"goal": "автоматизация", "budget": "10k"},
        "notes": "Тестовые заметки",
        "lead_saved_at": "2024-01-01T12:00:00Z",
        "lead_status": "active"
    })
    mock_memory.get_user_context.return_value = context_data
    
    result = tools.get_lead_data(user_id=123)
    
    assert result is not None
    assert result["user_id"] == 123
    assert result["name"] == "Тестовый Пользователь"
    assert result["lang"] == "ru"
    assert result["contact"] == "+79991234567"
    assert result["source"] == "telegram"
    assert result["intent"] == "SALES_AI"
    assert result["sales_stage"] == "needs_discovery"
    assert result["slots"]["goal"] == "автоматизация"
    assert result["notes"] == "Тестовые заметки"
    assert result["lead_saved_at"] == "2024-01-01T12:00:00Z"
    assert result["lead_status"] == "active"


def test_get_lead_data_invalid_json(tools, mock_memory):
    """Тест получения данных лида с невалидным JSON."""
    mock_memory.get_user_context.return_value = "invalid json"
    
    result = tools.get_lead_data(user_id=123)
    assert result is None

