"""Тесты для базы данных."""

import pytest
from pathlib import Path
import sys

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from shared.config.settings import Config
from shared.database.connection import create_database_engine, init_database, get_db_session
from shared.database.models import Conversation, Message, Lead
from sqlalchemy import select


@pytest.fixture
def config():
    """Создать тестовую конфигурацию."""
    return Config.from_yaml(str(project_root / "config.yaml"))


@pytest.fixture
def engine(config):
    """Создать тестовый engine."""
    return create_database_engine(config.database)


def test_database_connection(engine):
    """Тест подключения к БД."""
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


def test_database_tables(engine):
    """Тест наличия таблиц."""
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "conversations" in tables
    assert "messages" in tables
    assert "leads" in tables


def test_get_conversations(config):
    """Тест получения диалогов из БД."""
    session = get_db_session(config.database)
    try:
        stmt = select(Conversation).limit(10)
        conversations = session.execute(stmt).scalars().all()
        assert isinstance(conversations, list)
    finally:
        session.close()


def test_get_messages(config):
    """Тест получения сообщений из БД."""
    session = get_db_session(config.database)
    try:
        stmt = select(Message).limit(10)
        messages = session.execute(stmt).scalars().all()
        assert isinstance(messages, list)
    finally:
        session.close()

