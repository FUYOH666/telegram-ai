"""Тесты для MeetingSummary."""

import pytest

from telegram_ai.meeting_summary import MeetingSummary


@pytest.fixture
def meeting_summary():
    """Создать MeetingSummary для тестов."""
    return MeetingSummary()


def test_meeting_summary_initialization(meeting_summary):
    """Тест инициализации MeetingSummary."""
    assert meeting_summary is not None


def test_generate_summary_empty(meeting_summary):
    """Тест генерации сводки из пустых слотов."""
    summary = meeting_summary.generate_summary({})
    assert summary == "Информация о клиенте не собрана."


def test_generate_summary_basic(meeting_summary):
    """Тест генерации сводки с базовыми данными."""
    slots = {
        "client_name": "Иван",
        "company_name": "ООО Тест",
        "contact": "+79991234567",
        "company_size": "50 человек",
    }
    summary = meeting_summary.generate_summary(slots)
    assert "ИНФОРМАЦИЯ О КЛИЕНТЕ" in summary
    assert "Иван" in summary
    assert "ООО Тест" in summary
    assert "+79991234567" in summary
    assert "50 человек" in summary


def test_generate_summary_business_info(meeting_summary):
    """Тест генерации сводки с информацией о бизнесе."""
    slots = {
        "client_name": "Иван",
        "company_name": "ООО Тест",
        "company_domain": "медицина",
        "main_problems": "много ручной работы",
        "time_consuming_tasks": "обработка документов",
    }
    summary = meeting_summary.generate_summary(slots)
    assert "О БИЗНЕСЕ" in summary
    assert "медицина" in summary
    assert "много ручной работы" in summary
    assert "обработка документов" in summary


def test_generate_summary_metrics(meeting_summary):
    """Тест генерации сводки с метриками."""
    slots = {
        "client_name": "Иван",
        "company_name": "ООО Тест",
        "process_volume": "100 документов в день",
        "employees_involved": "3 человека",
        "current_time_cost": "20 часов в неделю",
        "error_rate": "10% ошибок",
        "business_revenue": "10 млн в месяц",
        "current_cost": "150k зарплаты",
    }
    summary = meeting_summary.generate_summary(slots)
    assert "МЕТРИКИ И ПОКАЗАТЕЛИ" in summary
    assert "100 документов в день" in summary
    assert "3 человека" in summary
    assert "20 часов в неделю" in summary
    assert "10% ошибок" in summary
    assert "10 млн в месяц" in summary
    assert "150k зарплаты" in summary


def test_generate_summary_project_info(meeting_summary):
    """Тест генерации сводки с информацией о проекте."""
    slots = {
        "client_name": "Иван",
        "company_name": "ООО Тест",
        "goal": "автоматизация обработки документов",
        "deadline": "через месяц",
        "budget_band": "до 500k",
        "data_access": "есть доступ",
        "success_metric": "сокращение времени на 50%",
    }
    summary = meeting_summary.generate_summary(slots)
    assert "О ПРОЕКТЕ" in summary
    assert "автоматизация обработки документов" in summary
    assert "через месяц" in summary
    assert "до 500k" in summary
    assert "есть доступ" in summary
    assert "сокращение времени на 50%" in summary


def test_generate_summary_full(meeting_summary):
    """Тест генерации полной сводки."""
    slots = {
        "client_name": "Иван",
        "company_name": "ООО Тест",
        "contact": "+79991234567",
        "company_size": "50 человек",
        "company_domain": "медицина",
        "main_problems": "много ручной работы",
        "goal": "автоматизация",
    }
    summary = meeting_summary.generate_summary(slots)
    assert "ИНФОРМАЦИЯ О КЛИЕНТЕ" in summary
    assert "О БИЗНЕСЕ" in summary


def test_generate_json_summary_empty(meeting_summary):
    """Тест генерации JSON сводки из пустых слотов."""
    summary = meeting_summary.generate_json_summary({})
    assert summary == {}


def test_generate_json_summary_basic(meeting_summary):
    """Тест генерации JSON сводки с базовыми данными."""
    slots = {
        "client_name": "Иван",
        "company_name": "ООО Тест",
        "contact": "+79991234567",
        "company_size": "50 человек",
    }
    summary = meeting_summary.generate_json_summary(slots)
    assert "client_info" in summary
    assert summary["client_info"]["client_name"] == "Иван"
    assert summary["client_info"]["company_name"] == "ООО Тест"
    assert summary["client_info"]["contact"] == "+79991234567"
    assert summary["client_info"]["company_size"] == "50 человек"


def test_generate_json_summary_full(meeting_summary):
    """Тест генерации полной JSON сводки."""
    slots = {
        "client_name": "Иван",
        "company_name": "ООО Тест",
        "contact": "+79991234567",
        "company_size": "50 человек",
        "company_domain": "медицина",
        "main_problems": "много ручной работы",
        "goal": "автоматизация",
        "process_volume": "100 документов в день",
    }
    summary = meeting_summary.generate_json_summary(slots)
    assert "client_info" in summary
    assert "business_info" in summary
    assert "metrics" in summary
    assert "project_info" in summary
    assert summary["business_info"]["company_domain"] == "медицина"
    assert summary["project_info"]["goal"] == "автоматизация"


def test_generate_json_summary_domain_compatibility(meeting_summary):
    """Тест обратной совместимости со старым полем domain."""
    slots = {
        "client_name": "Иван",
        "domain": "медицина",  # Старое поле
    }
    summary = meeting_summary.generate_json_summary(slots)
    assert summary["business_info"]["company_domain"] == "медицина"


def test_is_ready_for_meeting_empty(meeting_summary):
    """Тест проверки готовности к встрече с пустыми слотами."""
    assert not meeting_summary.is_ready_for_meeting({})


def test_is_ready_for_meeting_minimal(meeting_summary):
    """Тест проверки готовности к встрече с минимальными данными."""
    slots = {
        "client_name": "Иван",
        "company_name": "ООО Тест",
        "contact": "+79991234567",
        "main_problems": "много ручной работы",
        "goal": "автоматизация",
    }
    assert meeting_summary.is_ready_for_meeting(slots)


def test_is_ready_for_meeting_partial(meeting_summary):
    """Тест проверки готовности к встрече с частичными данными."""
    slots = {
        "client_name": "Иван",
        "company_name": "ООО Тест",
        "contact": "+79991234567",
        # Отсутствуют main_problems и goal
    }
    # Должно быть достаточно 3 из 5 базовых слотов
    assert meeting_summary.is_ready_for_meeting(slots)


def test_is_ready_for_meeting_custom_required(meeting_summary):
    """Тест проверки готовности с кастомным набором обязательных слотов."""
    slots = {
        "client_name": "Иван",
        "company_name": "ООО Тест",
    }
    custom_required = {"client_name", "company_name", "contact"}
    # Не все обязательные слоты заполнены
    assert not meeting_summary.is_ready_for_meeting(slots, custom_required)

    slots["contact"] = "+79991234567"
    # Все обязательные слоты заполнены
    assert meeting_summary.is_ready_for_meeting(slots, custom_required)


def test_analyze_conversation_history(meeting_summary):
    """Тест анализа истории диалога."""
    history = [
        {"role": "user", "content": "Привет, нужна автоматизация обработки документов"},
        {"role": "assistant", "content": "Здравствуйте! Расскажите подробнее"},
        {"role": "user", "content": "У нас много ручной работы, хочу автоматизировать"},
        {"role": "assistant", "content": "Понял, какие задачи отнимают больше всего времени?"},
    ]
    analysis = meeting_summary.analyze_conversation_history(history)
    assert analysis["total_messages"] == 4
    assert analysis["user_messages_count"] == 2
    assert analysis["assistant_messages_count"] == 2
    assert len(analysis["top_themes"]) > 0
    assert "автоматизация" in " ".join(analysis["top_themes"]).lower()


def test_analyze_conversation_history_empty(meeting_summary):
    """Тест анализа пустой истории."""
    analysis = meeting_summary.analyze_conversation_history([])
    assert analysis["total_messages"] == 0
    assert analysis["tone"] == "neutral"
    assert analysis["top_themes"] == []


def test_detect_tone(meeting_summary):
    """Тест определения тона общения."""
    positive_history = [
        {"role": "user", "content": "Очень интересно, хочу попробовать"},
        {"role": "user", "content": "Отлично, давайте обсудим"},
    ]
    analysis = meeting_summary.analyze_conversation_history(positive_history)
    assert analysis["tone"] == "положительный"

    negative_history = [
        {"role": "user", "content": "Это дорого для нас"},
        {"role": "user", "content": "Не уверен, что это нужно"},
    ]
    analysis = meeting_summary.analyze_conversation_history(negative_history)
    assert analysis["tone"] == "негативный"


def test_extract_objections(meeting_summary):
    """Тест извлечения возражений."""
    history = [
        {"role": "user", "content": "Это дорого для нас. Может быть есть варианты подешевле?"},
        {"role": "assistant", "content": "Понимаю, можем обсудить варианты"},
        {"role": "user", "content": "Подумаю, может быть позже"},
    ]
    analysis = meeting_summary.analyze_conversation_history(history)
    assert len(analysis["objections"]) > 0
    assert any("дорого" in obj.lower() for obj in analysis["objections"])


def test_extract_interests(meeting_summary):
    """Тест извлечения интересов."""
    history = [
        {"role": "user", "content": "Хочу узнать, как это работает"},
        {"role": "user", "content": "Расскажи, что можно автоматизировать"},
    ]
    analysis = meeting_summary.analyze_conversation_history(history)
    assert len(analysis["interests"]) > 0


def test_generate_recommendations(meeting_summary):
    """Тест генерации рекомендаций."""
    slots = {
        "main_problems": "много времени уходит на обработку документов, 20 часов в неделю",
        "current_time_cost": "20 часов в неделю",
        "error_rate": "10% ошибок",
    }
    analysis = {
        "objections": ["бюджет большой"],
        "top_themes": ["автоматизация", "обработка документов"],
    }
    recommendations = meeting_summary.generate_recommendations(slots, analysis, "objections")
    assert len(recommendations) > 0
    assert any("ROI" in rec or "экономия" in rec.lower() for rec in recommendations)


def test_generate_full_summary(meeting_summary):
    """Тест генерации полной сводки."""
    slots = {
        "client_name": "Иван",
        "company_name": "ООО Тест",
        "main_problems": "много ручной работы",
        "goal": "автоматизация",
    }
    history = [
        {"role": "user", "content": "Нужна автоматизация обработки документов"},
        {"role": "assistant", "content": "Расскажите подробнее"},
    ]
    full_summary = meeting_summary.generate_full_summary(slots, history, "needs_discovery")
    assert "ИНФОРМАЦИЯ О КЛИЕНТЕ" in full_summary
    assert "ЧТО ОБСУЖДАЛОСЬ" in full_summary
    assert "РЕКОМЕНДОВАННЫЕ АКЦЕНТЫ" in full_summary
    assert "Иван" in full_summary


def test_generate_owner_report(meeting_summary):
    """Тест генерации отчета для владельца."""
    slots = {
        "client_name": "Иван",
        "main_problems": "много ручной работы",
        "current_time_cost": "20 часов в неделю",
        "error_rate": "10% ошибок",
    }
    history = [
        {"role": "user", "content": "Нужна автоматизация обработки документов"},
        {"role": "user", "content": "Интересно, расскажи подробнее"},
    ]
    report = meeting_summary.generate_owner_report("Иван", slots, history, "needs_discovery")
    assert "📊 Summary встречи с Иван" in report
    assert "Количество сообщений" in report
    assert "Топ-3 темы" in report
    assert "Основные проблемы" in report
    assert "Тон:" in report


def test_generate_owner_report_empty(meeting_summary):
    """Тест генерации отчета с пустыми данными."""
    report = meeting_summary.generate_owner_report(None, {}, [])
    assert "📊 Summary встречи" in report

