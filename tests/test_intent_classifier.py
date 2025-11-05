"""Тесты для IntentClassifier."""

import pytest

from telegram_ai.intent_classifier import IntentClassifier, Intent


@pytest.fixture
def intent_classifier():
    """Создать IntentClassifier для тестов."""
    return IntentClassifier()


def test_intent_classifier_initialization(intent_classifier):
    """Тест инициализации IntentClassifier."""
    assert intent_classifier is not None


def test_classify_sales_ai(intent_classifier):
    """Тест классификации Sales AI."""
    # Явные ключевые слова
    assert intent_classifier.classify("Мне нужен чат-бот для автоматизации") == Intent.SALES_AI
    assert intent_classifier.classify("Хочу разработать AI систему") == Intent.SALES_AI
    assert intent_classifier.classify("Проект Scanovich.ai интересен") == Intent.SALES_AI
    assert intent_classifier.classify("Нужна интеграция с API") == Intent.SALES_AI


def test_classify_real_estate(intent_classifier):
    """Тест классификации Real Estate."""
    # Явные ключевые слова
    assert intent_classifier.classify("Ищу недвижимость на Пхукете") == Intent.REAL_ESTATE
    assert intent_classifier.classify("Хочу купить виллу в Лаяне") == Intent.REAL_ESTATE
    assert intent_classifier.classify("Кондо в Банг-Тао, нужен чанот") == Intent.REAL_ESTATE
    assert intent_classifier.classify("Инвестиция в недвижимость Пхукета") == Intent.REAL_ESTATE


def test_classify_small_talk(intent_classifier):
    """Тест классификации Small Talk."""
    # Явные ключевые слова (русские)
    assert intent_classifier.classify("Привет") == Intent.SMALL_TALK
    assert intent_classifier.classify("Как дела?") == Intent.SMALL_TALK
    assert intent_classifier.classify("Спасибо за помощь") == Intent.SMALL_TALK
    
    # Английские приветствия
    assert intent_classifier.classify("Hi") == Intent.SMALL_TALK
    assert intent_classifier.classify("Hello") == Intent.SMALL_TALK
    assert intent_classifier.classify("Hey") == Intent.SMALL_TALK
    assert intent_classifier.classify("Good morning") == Intent.SMALL_TALK
    assert intent_classifier.classify("Thanks") == Intent.SMALL_TALK
    assert intent_classifier.classify("How are you?") == Intent.SMALL_TALK


def test_classify_empty_message(intent_classifier):
    """Тест классификации пустого сообщения."""
    assert intent_classifier.classify("") == Intent.SMALL_TALK
    assert intent_classifier.classify(None) == Intent.SMALL_TALK


def test_classify_preserve_current_intent(intent_classifier):
    """Тест сохранения текущего намерения при отсутствии явных признаков."""
    # Длинные сообщения без явных признаков сохраняют текущее намерение
    assert intent_classifier.classify("Хорошо, понял все детали проекта", current_intent="SALES_AI") == Intent.SALES_AI
    assert intent_classifier.classify("Окей, спасибо за информацию об объектах", current_intent="REAL_ESTATE") == Intent.REAL_ESTATE
    
    # Короткие сообщения всегда классифицируются как SMALL_TALK независимо от current_intent
    assert intent_classifier.classify("Хорошо", current_intent="SALES_AI") == Intent.SMALL_TALK


def test_classify_priority_real_estate_over_sales(intent_classifier):
    """Тест приоритета Real Estate над Sales при равных совпадениях."""
    # Если есть признаки обоих, но Real Estate >= Sales, выбираем Real Estate
    message = "Хочу автоматизировать процесс работы с недвижимостью на Пхукете"
    result = intent_classifier.classify(message)
    # Должно быть Real Estate, так как есть явные ключевые слова недвижимости
    assert result == Intent.REAL_ESTATE


def test_classify_short_message_default(intent_classifier):
    """Тест классификации коротких сообщений по умолчанию."""
    # Короткие сообщения (<= 3 слова) без явных признаков -> Small Talk
    assert intent_classifier.classify("Окей") == Intent.SMALL_TALK
    assert intent_classifier.classify("Хорошо спасибо") == Intent.SMALL_TALK
    
    # Длинные сообщения без явных признаков -> Sales AI
    assert intent_classifier.classify("Интересная информация которая требует размышлений") == Intent.SALES_AI


def test_classify_change_intent_on_explicit_signals(intent_classifier):
    """Тест смены намерения при явных сигналах."""
    # Даже если текущее намерение Sales AI, но есть явные признаки Real Estate - меняем
    assert intent_classifier.classify("Кондо в Лаяне", current_intent="SALES_AI") == Intent.REAL_ESTATE
    
    # Даже если текущее намерение Real Estate, но есть явные признаки Sales AI - меняем
    assert intent_classifier.classify("Нужен чат-бот", current_intent="REAL_ESTATE") == Intent.SALES_AI

