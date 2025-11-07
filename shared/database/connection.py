"""Подключение к базе данных (PostgreSQL или SQLite)."""

import logging
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shared.config.settings import DatabaseConfig
from shared.database.models import Base

logger = logging.getLogger(__name__)


def create_database_engine(config: DatabaseConfig):
    """
    Создать engine для базы данных.

    Args:
        config: Конфигурация базы данных

    Returns:
        SQLAlchemy engine
    """
    # Если указан URL - используем его (PostgreSQL)
    if config.url:
        database_url = config.url
        logger.info(f"Using PostgreSQL database: {database_url}")
        engine = create_engine(
            database_url,
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
            echo=config.echo,
        )
    else:
        # Иначе используем SQLite (обратная совместимость)
        db_path = Path(config.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite:///{db_path}"
        logger.info(f"Using SQLite database: {database_url}")
        engine = create_engine(
            database_url,
            echo=config.echo,
            connect_args={"check_same_thread": False, "timeout": 5.0},
        )

    return engine


def init_database(engine):
    """
    Инициализировать базу данных (создать таблицы).

    Args:
        engine: SQLAlchemy engine
    """
    Base.metadata.create_all(engine)
    logger.info("Database tables created")


def get_session_factory(engine):
    """
    Получить фабрику сессий.

    Args:
        engine: SQLAlchemy engine

    Returns:
        Session factory
    """
    return sessionmaker(bind=engine)


def get_db_session(config: DatabaseConfig):
    """
    Получить сессию базы данных.

    Args:
        config: Конфигурация базы данных

    Returns:
        SQLAlchemy session
    """
    engine = create_database_engine(config)
    session_factory = get_session_factory(engine)
    return session_factory()

