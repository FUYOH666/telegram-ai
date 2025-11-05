"""Тесты для Memory."""

import pytest
import tempfile
import os

from telegram_ai.memory import Memory


@pytest.fixture
def temp_db():
    """Создать временную БД для тестов."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    # Удаляем после тестов
    if os.path.exists(db_path):
        os.remove(db_path)


def test_memory_initialization(temp_db):
    """Тест инициализации Memory."""
    memory = Memory(db_path=temp_db, context_window=10, max_history_days=30)
    assert str(memory.db_path) == temp_db
    assert memory.context_window == 10
    assert memory.max_history_days == 30


def test_memory_save_and_get_message(temp_db):
    """Тест сохранения и получения сообщений."""
    memory = Memory(db_path=temp_db)

    # Сохраняем сообщение
    memory.save_message(
        user_id=123,
        content="Hello",
        role="user",
        username="test_user",
    )

    # Получаем контекст
    context = memory.get_context(user_id=123)

    assert len(context) == 1
    assert context[0]["role"] == "user"
    assert context[0]["content"] == "Hello"


def test_memory_context_window(temp_db):
    """Тест контекстного окна."""
    memory = Memory(db_path=temp_db, context_window=3)

    # Сохраняем 5 сообщений
    for i in range(5):
        memory.save_message(
            user_id=123,
            content=f"Message {i}",
            role="user",
        )

    # Получаем контекст (должно быть только 3 последних)
    context = memory.get_context(user_id=123)

    assert len(context) == 3
    assert context[0]["content"] == "Message 2"
    assert context[2]["content"] == "Message 4"


def test_memory_get_or_create_conversation(temp_db):
    """Тест получения или создания conversation."""
    memory = Memory(db_path=temp_db)

    # Создаем новый conversation
    conv1 = memory.get_or_create_conversation(user_id=123, username="test")
    assert conv1.user_id == 123
    assert conv1.username == "test"

    # Получаем существующий
    conv2 = memory.get_or_create_conversation(user_id=123, username="test2")
    assert conv2.id == conv1.id
    assert conv2.username == "test2"  # Обновилось

