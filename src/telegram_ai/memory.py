"""Управление памятью и контекстом диалогов в SQLite БД."""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()


class Conversation(Base):
    """Модель таблицы conversations."""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Message(Base):
    """Модель таблицы messages."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' или 'assistant'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class UserContext(Base):
    """Модель таблицы user_context для хранения контекста пользователя."""

    __tablename__ = "user_context"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, unique=True, index=True)
    context_data = Column(Text, nullable=True)  # JSON строка с дополнительными данными
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class RateLimit(Base):
    """Модель таблицы rate_limits для защиты от флуда."""

    __tablename__ = "rate_limits"

    user_id = Column(Integer, primary_key=True)
    message_count_minute = Column(Integer, default=0, nullable=False)
    message_count_hour = Column(Integer, default=0, nullable=False)
    window_start_minute = Column(DateTime, nullable=False)
    window_start_hour = Column(DateTime, nullable=False)
    blocked_until = Column(DateTime, nullable=True)
    last_message_time = Column(DateTime, nullable=False)
    repeated_messages = Column(Integer, default=0, nullable=False)
    last_message_content = Column(Text, nullable=True)


class Memory:
    """Управление памятью и контекстом диалогов."""

    def __init__(self, db_path: str, context_window: int = 10, max_history_days: int = 30):
        """
        Инициализация Memory.

        Args:
            db_path: Путь к файлу SQLite БД
            context_window: Количество последних сообщений для контекста
            max_history_days: Максимальный возраст истории в днях
        """
        self.db_path = Path(db_path)
        self.context_window = context_window
        self.max_history_days = max_history_days

        # Создаем директорию для БД если её нет
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Создаем engine и сессию
        # timeout=5.0 позволяет автоматически разблокировать базу при кратковременных блокировках
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            echo=False,
            connect_args={"check_same_thread": False, "timeout": 5.0},
        )
        self.SessionLocal = sessionmaker(bind=self.engine)

        # Создаем таблицы
        Base.metadata.create_all(self.engine)

        logger.info(
            f"Memory initialized: db_path={self.db_path}, "
            f"context_window={self.context_window}, max_history_days={self.max_history_days}"
        )

    def _get_session(self) -> Session:
        """Получить сессию БД."""
        return self.SessionLocal()

    def get_or_create_conversation(
        self, user_id: int, username: Optional[str] = None
    ) -> Conversation:
        """
        Получить или создать conversation для пользователя.

        Args:
            user_id: ID пользователя Telegram
            username: Имя пользователя (опционально)

        Returns:
            Conversation объект
        """
        session = self._get_session()
        try:
            conversation = (
                session.query(Conversation)
                .filter(Conversation.user_id == user_id)
                .first()
            )

            if not conversation:
                conversation = Conversation(user_id=user_id, username=username)
                session.add(conversation)
                session.commit()
                session.refresh(conversation)
                logger.info(f"Created new conversation for user_id={user_id}")
            else:
                if username and conversation.username != username:
                    conversation.username = username
                    session.commit()
                    session.refresh(conversation)

            # Возвращаем объект с загруженными атрибутами
            session.expunge(conversation)
            return conversation
        finally:
            session.close()

    def save_message(
        self,
        user_id: int,
        content: str,
        role: str = "user",
        username: Optional[str] = None,
    ) -> Message:
        """
        Сохранить сообщение в БД.

        Args:
            user_id: ID пользователя Telegram
            content: Текст сообщения
            role: Роль ('user' или 'assistant')
            username: Имя пользователя (опционально)

        Returns:
            Message объект
        """
        session = self._get_session()
        try:
            conversation = self.get_or_create_conversation(user_id, username)
            message = Message(
                conversation_id=conversation.id,
                role=role,
                content=content,
            )
            session.add(message)
            session.commit()
            logger.debug(f"Saved {role} message for user_id={user_id}")
            return message
        finally:
            session.close()

    def get_context(
        self, user_id: int, limit: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Получить контекст диалога для отправки в AI.

        Args:
            user_id: ID пользователя Telegram
            limit: Количество последних сообщений (по умолчанию context_window)

        Returns:
            Список сообщений в формате OpenAI API
            [{"role": "user", "content": "..."}, ...]
        """
        if limit is None:
            limit = self.context_window

        session = self._get_session()
        try:
            conversation = (
                session.query(Conversation)
                .filter(Conversation.user_id == user_id)
                .first()
            )

            if not conversation:
                return []

            messages = (
                session.query(Message)
                .filter(Message.conversation_id == conversation.id)
                .order_by(Message.timestamp.desc())
                .limit(limit)
                .all()
            )

            # Разворачиваем список (старые сообщения первыми)
            messages.reverse()

            context = [
                {"role": msg.role, "content": msg.content} for msg in messages
            ]

            logger.debug(f"Retrieved {len(context)} messages for user_id={user_id}")
            return context

        finally:
            session.close()

    def cleanup_old_messages(self):
        """Удалить старые сообщения старше max_history_days."""
        session = self._get_session()
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.max_history_days)
            deleted = (
                session.query(Message)
                .filter(Message.timestamp < cutoff_date)
                .delete()
            )
            session.commit()
            logger.info(f"Cleaned up {deleted} old messages")
        finally:
            session.close()

    def get_user_context(self, user_id: int) -> Optional[str]:
        """
        Получить контекст пользователя.

        Args:
            user_id: ID пользователя Telegram

        Returns:
            JSON строка с контекстом или None
        """
        session = self._get_session()
        try:
            user_context = (
                session.query(UserContext)
                .filter(UserContext.user_id == user_id)
                .first()
            )
            return user_context.context_data if user_context else None
        finally:
            session.close()

    def save_user_context(self, user_id: int, context_data: str):
        """
        Сохранить контекст пользователя.

        Args:
            user_id: ID пользователя Telegram
            context_data: JSON строка с контекстом
        """
        session = self._get_session()
        try:
            user_context = (
                session.query(UserContext)
                .filter(UserContext.user_id == user_id)
                .first()
            )

            if user_context:
                user_context.context_data = context_data
            else:
                user_context = UserContext(user_id=user_id, context_data=context_data)
                session.add(user_context)

            session.commit()
            logger.debug(f"Saved user context for user_id={user_id}")
        finally:
            session.close()

