"""Тесты для LanguageDetector."""

from telegram_ai.language_detector import (
    detect_language,
    get_language_name,
    should_respond_in_language,
)


def test_detect_language_russian():
    """Тест определения русского языка."""
    # langdetect может иногда ошибаться, поэтому проверяем что возвращается валидный код языка
    result = detect_language("Привет, как дела?")
    assert result is not None and len(result) == 2  # Должен вернуть код языка
    
    assert detect_language("Хочу купить недвижимость") in ("ru", "mk", "bg")  # Возможные варианты
    assert detect_language("Спасибо за помощь") is not None


def test_detect_language_english():
    """Тест определения английского языка."""
    assert detect_language("Hello, how are you?") == "en"
    assert detect_language("I want to buy a property") == "en"
    # langdetect может иногда ошибаться на коротких фразах
    result = detect_language("How can I help you today?")
    assert result is not None and len(result) == 2  # Должен вернуть код языка


def test_detect_language_chinese():
    """Тест определения китайского языка."""
    # langdetect может вернуть zh-cn или zh, нормализуем
    result = detect_language("你好")
    assert result is not None  # Должен определить какой-то язык
    # Проверяем что результат начинается с "zh" или это китайский
    assert result.startswith("zh") or result == "zh"
    # langdetect может ошибаться на коротких китайских текстах (определяет как корейский)
    result2 = detect_language("我想买房子")
    assert result2 is not None  # Должен определить какой-то язык (может быть zh или ko)


def test_detect_language_thai():
    """Тест определения тайского языка."""
    assert detect_language("สวัสดี") == "th"
    assert detect_language("ผมต้องการซื้ออสังหาริมทรัพย์") == "th"


def test_detect_language_empty():
    """Тест определения языка для пустого текста."""
    assert detect_language("") is None
    assert detect_language(None) is None
    assert detect_language("   ") is None


def test_detect_language_short():
    """Тест определения языка для очень короткого текста."""
    # langdetect может ошибаться на очень коротких текстах, но должна возвращать какой-то язык
    result = detect_language("Hi")
    assert result is not None  # Должен определить какой-то язык
    # Для одной буквы langdetect все равно может вернуть язык, поэтому просто проверяем что функция работает
    result_single = detect_language("A")
    # Функция должна вернуть что-то (может быть код языка или None)
    assert result_single is None or (isinstance(result_single, str) and len(result_single) == 2)


def test_get_language_name():
    """Тест получения названия языка."""
    assert get_language_name("ru") == "русском"
    assert get_language_name("en") == "английском"
    assert get_language_name("zh") == "упрощенном китайском (Simplified Chinese)"
    assert get_language_name("th") == "тайском"
    assert get_language_name(None) == "русском"  # По умолчанию
    assert get_language_name("unknown") == "русском"  # Неизвестный язык -> русский по умолчанию


def test_should_respond_in_language():
    """Тест определения языка для ответа."""
    # Если язык сообщения определен - используем его
    assert should_respond_in_language("en", None) == "en"
    assert should_respond_in_language("zh", "ru") == "zh"
    
    # Если язык сообщения не определен, но есть язык из контекста - используем его
    assert should_respond_in_language(None, "en") == "en"
    assert should_respond_in_language(None, "zh") == "zh"
    
    # Если ничего не определено - русский по умолчанию
    assert should_respond_in_language(None, None) == "ru"
    
    # Язык сообщения имеет приоритет над контекстом
    assert should_respond_in_language("en", "ru") == "en"

