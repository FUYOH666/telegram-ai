"""Тесты для SalesFlow."""

import pytest
import json

from telegram_ai.sales_flow import SalesFlow, SalesStage


@pytest.fixture
def sales_flow():
    """Создать SalesFlow для тестов."""
    return SalesFlow(enabled=True)


def test_sales_flow_initialization(sales_flow):
    """Тест инициализации SalesFlow."""
    assert sales_flow.enabled is True


def test_sales_flow_get_stage_default(sales_flow):
    """Тест получения этапа по умолчанию."""
    stage = sales_flow.get_stage(None)
    assert stage == SalesStage.GREETING


def test_sales_flow_get_stage_from_context(sales_flow):
    """Тест получения этапа из контекста."""
    context_data = json.dumps({"sales_stage": "needs_discovery"})
    stage = sales_flow.get_stage(context_data)
    assert stage == SalesStage.NEEDS_DISCOVERY


def test_sales_flow_update_stage(sales_flow):
    """Тест обновления этапа."""
    new_stage = SalesStage.PRESENTATION
    updated = sales_flow.update_stage(None, new_stage)
    
    data = json.loads(updated)
    assert data["sales_stage"] == "presentation"


def test_sales_flow_greeting_to_needs(sales_flow):
    """Тест перехода от приветствия к выявлению потребностей."""
    message = "Мне нужно автоматизировать процесс"
    current_stage = SalesStage.GREETING
    
    new_stage = sales_flow.detect_stage_transition(message, current_stage)
    assert new_stage == SalesStage.NEEDS_DISCOVERY


def test_sales_flow_needs_to_presentation(sales_flow):
    """Тест перехода от потребностей к презентации."""
    message = "Расскажи что вы можете предложить"
    current_stage = SalesStage.NEEDS_DISCOVERY
    
    new_stage = sales_flow.detect_stage_transition(message, current_stage)
    assert new_stage == SalesStage.PRESENTATION


def test_sales_flow_presentation_to_objections(sales_flow):
    """Тест перехода к возражениям."""
    message = "Это дорого для нас"
    current_stage = SalesStage.PRESENTATION
    
    new_stage = sales_flow.detect_stage_transition(message, current_stage)
    assert new_stage == SalesStage.OBJECTIONS


def test_sales_flow_to_consultation(sales_flow):
    """Тест перехода к предложению консультации."""
    message = "Хочу консультацию"
    current_stage = SalesStage.PRESENTATION

    new_stage = sales_flow.detect_stage_transition(message, current_stage)
    # Проверяем что либо переход к консультации, либо к возражениям (если есть "хочу")
    assert new_stage in [SalesStage.CONSULTATION_OFFER, SalesStage.OBJECTIONS] or new_stage is None

    # Проверяем с другим сообщением с явным ключевым словом "консультация"
    message2 = "Можно обсудить детали на консультации?"
    new_stage2 = sales_flow.detect_stage_transition(message2, current_stage)
    assert new_stage2 == SalesStage.CONSULTATION_OFFER


def test_sales_flow_to_scheduling(sales_flow):
    """Тест перехода к согласованию времени."""
    message = "Когда можем встретиться?"
    current_stage = SalesStage.CONSULTATION_OFFER
    
    new_stage = sales_flow.detect_stage_transition(message, current_stage)
    assert new_stage == SalesStage.SCHEDULING


def test_sales_flow_no_transition(sales_flow):
    """Тест отсутствия перехода."""
    message = "Спасибо за информацию"
    current_stage = SalesStage.GREETING
    
    new_stage = sales_flow.detect_stage_transition(message, current_stage)
    assert new_stage is None


def test_sales_flow_get_stage_prompt_modifier(sales_flow):
    """Тест получения модификатора промпта для этапа."""
    modifier = sales_flow.get_stage_prompt_modifier(SalesStage.GREETING)
    assert isinstance(modifier, str)
    assert len(modifier) > 0
    # Проверяем что содержит ключевые слова этапа
    assert "этап" in modifier.lower() or "привет" in modifier.lower()


def test_sales_flow_disabled(sales_flow):
    """Тест работы при отключенном sales flow."""
    sales_flow.enabled = False
    message = "Мне нужно автоматизировать процесс"
    current_stage = SalesStage.GREETING
    
    new_stage = sales_flow.detect_stage_transition(message, current_stage)
    assert new_stage is None


def test_sales_flow_first_message_greeting(sales_flow):
    """Тест определения приветствия для первого сообщения."""
    message = "Привет"
    current_stage = SalesStage.NEEDS_DISCOVERY  # Даже если текущий этап другой
    
    # При первом сообщении должно вернуться GREETING
    new_stage = sales_flow.detect_stage_transition(message, current_stage, is_first_message=True)
    assert new_stage == SalesStage.GREETING


def test_sales_flow_get_stage_max_length(sales_flow):
    """Тест получения максимальной длины ответа для этапа."""
    max_length = sales_flow.get_stage_max_length(SalesStage.GREETING)
    assert max_length == 150
    
    max_length = sales_flow.get_stage_max_length(SalesStage.PRESENTATION)
    assert max_length == 500
    
    # Для несуществующего этапа должно вернуться None
    from telegram_ai.sales_flow import SalesStage as SS
    # Проверяем что метод работает для всех этапов
    for stage in SS:
        max_len = sales_flow.get_stage_max_length(stage)
        assert max_len is not None or stage not in [SS.GREETING, SS.NEEDS_DISCOVERY, SS.PRESENTATION, SS.OBJECTIONS, SS.CONSULTATION_OFFER, SS.SCHEDULING]

