"""Тесты для RateLimiter."""

import pytest
import tempfile
import os

from telegram_ai.memory import Memory
from telegram_ai.rate_limiter import RateLimiter


@pytest.fixture
def temp_db():
    """Создать временную БД для тестов."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    # Удаляем после тестов
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def memory(temp_db):
    """Создать Memory для тестов."""
    return Memory(db_path=temp_db)


@pytest.fixture
def rate_limiter(memory):
    """Создать RateLimiter для тестов."""
    return RateLimiter(
        session_factory=memory.SessionLocal,
        enabled=True,
        messages_per_minute=5,
        messages_per_hour=10,
        min_interval_seconds=1,
        block_duration_minutes=5,
        max_repeated_messages=2,
        min_message_length=1,
        max_message_length=1000,
    )


def test_rate_limiter_initialization(rate_limiter):
    """Тест инициализации RateLimiter."""
    assert rate_limiter.enabled is True
    assert rate_limiter.messages_per_minute == 5
    assert rate_limiter.messages_per_hour == 10


def test_rate_limiter_check_allowed(rate_limiter):
    """Тест разрешенного сообщения."""
    user_id = 123
    message = "Hello, world!"

    allowed, reason = rate_limiter.check_rate_limit(user_id, message)
    assert allowed is True
    assert reason is None


def test_rate_limiter_min_length(rate_limiter):
    """Тест проверки минимальной длины сообщения."""
    user_id = 123
    message = ""  # Пустое сообщение (меньше min_message_length=1)

    allowed, reason = rate_limiter.check_rate_limit(user_id, message)
    assert allowed is False
    assert "короткое" in reason.lower()


def test_rate_limiter_max_length(rate_limiter):
    """Тест проверки максимальной длины сообщения."""
    user_id = 123
    message = "A" * 2000  # Слишком длинное

    allowed, reason = rate_limiter.check_rate_limit(user_id, message)
    assert allowed is False
    assert "длинное" in reason.lower()


def test_rate_limiter_repeated_messages(rate_limiter):
    """Тест блокировки повторяющихся сообщений."""
    import time
    user_id = 123
    message = "Test message"

    # Отправляем первое сообщение (check_rate_limit вызывает record_message внутри)
    allowed, reason = rate_limiter.check_rate_limit(user_id, message)
    assert allowed is True

    # Ждем минимальный интервал
    time.sleep(1.1)

    # Второе повторяющееся сообщение
    # После первого сообщения repeated_messages = 0, после второго = 1
    allowed, reason = rate_limiter.check_rate_limit(user_id, message)
    assert allowed is True  # Еще не достигли лимита (repeated_messages = 1 < max_repeated_messages=2)

    # Ждем минимальный интервал
    time.sleep(1.1)

    # Третье повторяющееся сообщение должно быть заблокировано
    # После второго сообщения repeated_messages = 1, после третьего = 2 (>= max_repeated_messages=2)
    allowed, reason = rate_limiter.check_rate_limit(user_id, message)
    assert allowed is False
    assert "повторяющихся" in reason.lower()


def test_rate_limiter_minute_limit(rate_limiter):
    """Тест лимита сообщений в минуту."""
    import time
    user_id = 123

    # Отправляем сообщения до лимита (messages_per_minute=5)
    # check_rate_limit вызывает record_message внутри, поэтому счетчик увеличивается автоматически
    for i in range(5):
        message = f"Message {i}"
        allowed, reason = rate_limiter.check_rate_limit(user_id, message)
        assert allowed is True, f"Message {i} should be allowed"
        # Ждем минимальный интервал между сообщениями
        if i < 4:  # Не ждем после последнего сообщения
            time.sleep(1.1)

    # После 5 сообщений счетчик = 5, что равно лимиту
    # Шестое сообщение должно быть заблокировано (лимит 5 сообщений в минуту)
    time.sleep(1.1)  # Ждем минимальный интервал
    allowed, reason = rate_limiter.check_rate_limit(user_id, "Too many")
    assert allowed is False
    assert "минуту" in reason.lower() or "лимит" in reason.lower()


def test_rate_limiter_is_blocked(rate_limiter):
    """Тест проверки блокировки пользователя."""
    user_id = 123

    # Пользователь не заблокирован
    blocked, reason = rate_limiter.is_blocked(user_id)
    assert blocked is False

    # Блокируем пользователя напрямую
    rate_limiter.block_user(user_id, "Test reason")

    # Пользователь должен быть заблокирован
    blocked, reason = rate_limiter.is_blocked(user_id)
    assert blocked is True
    assert reason is not None
    assert "минут" in reason.lower()


def test_rate_limiter_disabled(rate_limiter):
    """Тест работы при отключенном rate limiting."""
    rate_limiter.enabled = False
    user_id = 123
    message = "Test"

    allowed, reason = rate_limiter.check_rate_limit(user_id, message)
    assert allowed is True
    assert reason is None


def test_calculate_optimal_interval_no_user(rate_limiter):
    """Тест расчета интервала для пользователя без истории."""
    user_id = 999
    interval, needs_wait = rate_limiter.calculate_optimal_interval(user_id)
    assert interval == 0.0
    assert needs_wait is False


def test_calculate_optimal_interval_low_usage(rate_limiter):
    """Тест расчета интервала при низком использовании лимита."""
    import time
    user_id = 123
    message = "Test message"
    
    # Отправляем одно сообщение
    allowed, _ = rate_limiter.check_rate_limit(user_id, message)
    assert allowed is True
    
    # Рассчитываем интервал
    interval, needs_wait = rate_limiter.calculate_optimal_interval(user_id)
    # При низком использовании интервал должен быть небольшим или нулевым
    assert interval >= rate_limiter.min_interval_seconds
    # Если лимит не исчерпан, может не нужно ждать (но интервал все равно >= min)
    assert isinstance(needs_wait, bool)


def test_calculate_optimal_interval_high_usage(rate_limiter):
    """Тест расчета интервала при высоком использовании лимита."""
    import time
    user_id = 456
    messages_per_minute = 5
    
    # Отправляем сообщения близко к лимиту
    for i in range(4):
        message = f"Message {i}"
        allowed, _ = rate_limiter.check_rate_limit(user_id, message, messages_per_minute=messages_per_minute)
        assert allowed is True
        if i < 3:
            time.sleep(1.1)
    
    # Рассчитываем интервал - должен быть больше минимального
    interval, needs_wait = rate_limiter.calculate_optimal_interval(
        user_id, messages_per_minute=messages_per_minute
    )
    assert interval >= rate_limiter.min_interval_seconds
    # При высоком использовании обычно нужно ждать
    assert isinstance(needs_wait, bool)


def test_calculate_optimal_interval_custom_limit(rate_limiter):
    """Тест расчета интервала с кастомным лимитом."""
    import time
    user_id = 789
    custom_limit = 10
    message = "Test"
    
    # Отправляем сообщение
    allowed, _ = rate_limiter.check_rate_limit(user_id, message, messages_per_minute=custom_limit)
    assert allowed is True
    
    # Рассчитываем с кастомным лимитом
    interval, needs_wait = rate_limiter.calculate_optimal_interval(
        user_id, messages_per_minute=custom_limit
    )
    assert interval >= rate_limiter.min_interval_seconds
    assert isinstance(needs_wait, bool)


def test_calculate_optimal_interval_disabled(rate_limiter):
    """Тест расчета интервала при отключенном rate limiting."""
    rate_limiter.enabled = False
    user_id = 123
    
    interval, needs_wait = rate_limiter.calculate_optimal_interval(user_id)
    assert interval == 0.0
    assert needs_wait is False

