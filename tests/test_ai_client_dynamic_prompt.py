"""Тесты для динамического системного промпта в AIClient."""

import pytest

from telegram_ai.ai_client import AIClient


@pytest.fixture
def ai_client():
    """Создать AIClient для тестов."""
    return AIClient(
        base_url="http://localhost:8000",
        model="test-model",
        system_prompt="Базовый промпт",
        timezone_name="Europe/Moscow",
    )


def test_get_dynamic_system_prompt_contains_date(ai_client):
    """Тест что динамический промпт содержит дату."""
    prompt = ai_client._get_dynamic_system_prompt()
    
    assert "Текущая дата и время" in prompt
    assert "МСК" in prompt
    assert "Базовый промпт" in prompt  # Базовый промпт должен быть включен


def test_get_dynamic_system_prompt_no_base(ai_client):
    """Тест динамического промпта без базового."""
    ai_client.system_prompt = None
    prompt = ai_client._get_dynamic_system_prompt()
    
    assert "Текущая дата и время" in prompt
    assert len(prompt) > 0


def test_get_dynamic_system_prompt_format(ai_client):
    """Тест формата даты в промпте."""
    prompt = ai_client._get_dynamic_system_prompt()

    # Проверяем что дата присутствует (формат может варьироваться из-за timezone)
    assert "2025" in prompt or "2024" in prompt or "2026" in prompt  # Текущий год
    assert "МСК" in prompt
    assert ":" in prompt  # Время присутствует


def test_ai_client_timezone_config(ai_client):
    """Тест конфигурации timezone."""
    assert ai_client.timezone_name == "Europe/Moscow"


def test_ai_client_date_format_default(ai_client):
    """Тест дефолтного формата даты."""
    assert ai_client.date_format is not None
    assert "%d" in ai_client.date_format or "%B" in ai_client.date_format

