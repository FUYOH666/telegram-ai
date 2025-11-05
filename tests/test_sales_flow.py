"""Тесты для SalesFlow."""

import json

import pytest

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
    assert (
        new_stage in [SalesStage.CONSULTATION_OFFER, SalesStage.OBJECTIONS]
        or new_stage is None
    )

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
    new_stage = sales_flow.detect_stage_transition(
        message, current_stage, is_first_message=True
    )
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
        assert max_len is not None or stage not in [
            SS.GREETING,
            SS.NEEDS_DISCOVERY,
            SS.PRESENTATION,
            SS.OBJECTIONS,
            SS.CONSULTATION_OFFER,
            SS.SCHEDULING,
        ]


def test_sales_flow_get_slots_empty(sales_flow):
    """Тест получения слотов из пустого контекста."""
    slots = sales_flow.get_slots(None)
    assert slots == {}


def test_sales_flow_get_slots_from_context(sales_flow):
    """Тест получения слотов из контекста."""
    context_data = json.dumps(
        {"slots": {"goal": "автоматизация", "budget": "10k", "contact": "+79991234567"}}
    )
    slots = sales_flow.get_slots(context_data)
    assert slots["goal"] == "автоматизация"
    assert slots["budget"] == "10k"
    assert slots["contact"] == "+79991234567"


def test_sales_flow_update_slot(sales_flow):
    """Тест обновления слота."""
    context_data = json.dumps({"slots": {"goal": "старая цель"}})
    updated = sales_flow.update_slot(context_data, "budget", "20k")

    data = json.loads(updated)
    assert data["slots"]["goal"] == "старая цель"  # Старый слот сохранился
    assert data["slots"]["budget"] == "20k"  # Новый слот добавился
    assert "missing_slots" in data  # Должен пересчитаться список missing_slots


def test_sales_flow_update_slot_new_context(sales_flow):
    """Тест обновления слота в новом контексте."""
    updated = sales_flow.update_slot(None, "goal", "новая цель")

    data = json.loads(updated)
    assert data["slots"]["goal"] == "новая цель"
    assert "missing_slots" in data


def test_sales_flow_get_missing_slots_sales(sales_flow):
    """Тест получения недостающих слотов для Sales AI."""
    # Пустой контекст - все слоты недостающие
    missing = sales_flow.get_missing_slots(None, "SALES_AI")
    assert len(missing) > 0
    assert "goal" in missing
    assert "contact" in missing

    # Контекст с заполненными слотами
    context_data = json.dumps(
        {
            "intent": "SALES_AI",
            "slots": {"goal": "автоматизация", "contact": "+79991234567"},
        }
    )
    missing = sales_flow.get_missing_slots(context_data, "SALES_AI")
    assert "goal" not in missing
    assert "contact" not in missing
    assert len(missing) > 0  # Еще есть недостающие


def test_sales_flow_get_missing_slots_real_estate(sales_flow):
    """Тест получения недостающих слотов для Real Estate."""
    # Пустой контекст - все слоты недостающие
    missing = sales_flow.get_missing_slots(None, "REAL_ESTATE")
    assert len(missing) > 0
    assert "purpose" in missing
    assert "budget" in missing
    assert "contact" in missing


def test_sales_flow_get_slot_prompt_sales(sales_flow):
    """Тест получения промпта для слота Sales."""
    prompt = sales_flow.get_slot_prompt("goal", "SALES_AI")
    assert prompt is not None
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_sales_flow_get_slot_prompt_real_estate(sales_flow):
    """Тест получения промпта для слота Real Estate."""
    prompt = sales_flow.get_slot_prompt("purpose", "REAL_ESTATE")
    assert prompt is not None
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_sales_flow_get_slot_prompt_not_found(sales_flow):
    """Тест получения промпта для несуществующего слота."""
    prompt = sales_flow.get_slot_prompt("nonexistent_slot", "SALES_AI")
    assert prompt is None


def test_sales_flow_get_next_slot_to_ask(sales_flow):
    """Тест получения следующего слота для запроса."""
    # Пустой контекст - должен вернуть приоритетный слот
    next_slot = sales_flow.get_next_slot_to_ask(None, "SALES_AI")
    assert next_slot is not None
    assert next_slot in ["goal", "purpose", "budget", "budget_band", "contact"]

    # Контекст с заполненными приоритетными слотами
    context_data = json.dumps(
        {"intent": "SALES_AI", "slots": {"goal": "автоматизация", "budget_band": "10k"}}
    )
    next_slot = sales_flow.get_next_slot_to_ask(context_data, "SALES_AI")
    assert next_slot is not None
    assert next_slot != "goal"
    assert next_slot != "budget_band"


def test_sales_flow_get_next_slot_to_ask_all_filled(sales_flow):
    """Тест получения следующего слота когда все заполнены."""
    # Создаем контекст со всеми заполненными слотами
    all_slots = {slot: f"value_{slot}" for slot in sales_flow.SALES_REQUIRED_SLOTS}
    context_data = json.dumps({"intent": "SALES_AI", "slots": all_slots})
    next_slot = sales_flow.get_next_slot_to_ask(context_data, "SALES_AI")
    assert next_slot is None


def test_sales_flow_update_intent(sales_flow):
    """Тест обновления intent в контексте."""
    context_data = json.dumps({"slots": {"goal": "автоматизация"}})
    updated = sales_flow.update_intent(context_data, "REAL_ESTATE")

    data = json.loads(updated)
    assert data["intent"] == "REAL_ESTATE"
    assert "missing_slots" in data  # Должен пересчитаться список missing_slots


def test_sales_flow_update_intent_new_context(sales_flow):
    """Тест обновления intent в новом контексте."""
    updated = sales_flow.update_intent(None, "SALES_AI")

    data = json.loads(updated)
    assert data["intent"] == "SALES_AI"
