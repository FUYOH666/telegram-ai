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


class ConversationSummary(Base):
    """Модель таблицы conversation_summaries для хранения резюме диалогов."""

    __tablename__ = "conversation_summaries"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, nullable=False, index=True)
    summary_text = Column(Text, nullable=False)
    cutoff_message_id = Column(Integer, nullable=False)  # ID последнего сообщения, включенного в summary
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Memory:
    """Управление памятью и контекстом диалогов."""

    def __init__(
        self,
        db_path: str,
        context_window: int = 10,
        max_history_days: int = 30,
        auto_summarize: bool = True,
        summary_threshold: int = 15,
        ai_client=None,
        vector_memory=None,
    ):
        """
        Инициализация Memory.

        Args:
            db_path: Путь к файлу SQLite БД
            context_window: Количество последних сообщений для контекста
            max_history_days: Максимальный возраст истории в днях
            auto_summarize: Автоматически создавать summary для старых сообщений
            summary_threshold: Минимальное количество сообщений для создания summary
            ai_client: Экземпляр AIClient для создания summary (опционально)
            vector_memory: Экземпляр VectorMemory для векторного поиска (опционально)
        """
        self.db_path = Path(db_path)
        self.context_window = context_window
        self.max_history_days = max_history_days
        self.auto_summarize = auto_summarize
        self.summary_threshold = summary_threshold
        self.ai_client = ai_client
        self.vector_memory = vector_memory

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

            # Добавляем сообщение в векторное хранилище будет выполнено асинхронно в другом месте
            # (не блокируем сохранение в БД)

            return message
        finally:
            session.close()

    def get_summary(self, conversation_id: int) -> Optional[str]:
        """
        Получить summary для разговора.

        Args:
            conversation_id: ID разговора

        Returns:
            Текст summary или None если его нет
        """
        session = self._get_session()
        try:
            summary = (
                session.query(ConversationSummary)
                .filter(ConversationSummary.conversation_id == conversation_id)
                .order_by(ConversationSummary.updated_at.desc())
                .first()
            )
            return summary.summary_text if summary else None
        finally:
            session.close()

    async def summarize_old_messages(
        self, user_id: int, cutoff_message_id: int
    ) -> Optional[str]:
        """
        Создать summary для старых сообщений до указанного ID.

        Args:
            user_id: ID пользователя Telegram
            cutoff_message_id: ID последнего сообщения, которое нужно включить в summary

        Returns:
            Текст summary или None если не удалось создать
        """
        if not self.auto_summarize or not self.ai_client:
            return None

        session = self._get_session()
        try:
            conversation = (
                session.query(Conversation)
                .filter(Conversation.user_id == user_id)
                .first()
            )

            if not conversation:
                return None

            # Получаем все сообщения до cutoff_message_id включительно
            old_messages = (
                session.query(Message)
                .filter(
                    Message.conversation_id == conversation.id,
                    Message.id <= cutoff_message_id,
                )
                .order_by(Message.timestamp.asc())
                .all()
            )

            if len(old_messages) < self.summary_threshold:
                # Недостаточно сообщений для summary
                return None

            # Формируем текст для summarization
            messages_text = "\n".join(
                [
                    f"{msg.role}: {msg.content}"
                    for msg in old_messages
                    if msg.content.strip()
                ]
            )

            if not messages_text.strip():
                return None

            # Промпт для summarization
            summary_prompt = f"""Создай краткое резюме следующего диалога, сохранив ключевую информацию:
- Основные темы обсуждения
- Важные детали (бюджет, сроки, контакты, цели)
- Решения и договоренности
- Любые важные факты о пользователе или проекте

Диалог:
{messages_text}

Резюме (до 200 слов):"""

            try:
                # Используем LLM для создания summary
                messages = [{"role": "user", "content": summary_prompt}]
                summary_text = await self.ai_client.get_response(
                    messages,
                    temperature=0.3,  # Низкая температура для более детерминированного summary
                    max_tokens=300,
                )

                if not summary_text or len(summary_text.strip()) < 20:
                    logger.warning("Generated summary is too short or empty")
                    return None

                # Сохраняем summary в БД
                # Удаляем старый summary если есть
                session.query(ConversationSummary).filter(
                    ConversationSummary.conversation_id == conversation.id
                ).delete()

                summary = ConversationSummary(
                    conversation_id=conversation.id,
                    summary_text=summary_text.strip(),
                    cutoff_message_id=cutoff_message_id,
                )
                session.add(summary)
                session.commit()

                logger.info(
                    f"Created summary for conversation_id={conversation.id}, "
                    f"cutoff_message_id={cutoff_message_id}, length={len(summary_text)}"
                )

                return summary_text.strip()

            except Exception as e:
                logger.error(f"Error creating summary: {e}", exc_info=True)
                return None

        finally:
            session.close()

    def should_create_summary(self, user_id: int, limit: Optional[int] = None) -> Optional[int]:
        """
        Проверить, нужно ли создать summary для пользователя.

        Args:
            user_id: ID пользователя Telegram
            limit: Количество последних сообщений (по умолчанию context_window)

        Returns:
            cutoff_message_id для создания summary или None если не нужно
        """
        if not self.auto_summarize or not self.ai_client:
            return None

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
                return None

            # Получаем общее количество сообщений
            total_messages = (
                session.query(Message)
                .filter(Message.conversation_id == conversation.id)
                .count()
            )

            # Если сообщений меньше limit, summary не нужен
            if total_messages <= limit:
                return None

            # Проверяем, есть ли уже summary
            existing_summary = (
                session.query(ConversationSummary)
                .filter(ConversationSummary.conversation_id == conversation.id)
                .first()
            )

            if existing_summary:
                # Summary уже есть, но нужно проверить актуальность
                # Если появилось много новых сообщений, может понадобиться обновить summary
                # Для простоты, если summary есть - не создаем новый
                return None

            # Получаем ID первого сообщения, которое будет включено в context
            first_message_in_context = (
                session.query(Message)
                .filter(Message.conversation_id == conversation.id)
                .order_by(Message.timestamp.asc())
                .offset(total_messages - limit)
                .first()
            )

            if not first_message_in_context:
                return None

            # cutoff_message_id - это ID последнего сообщения ДО context
            cutoff_id = first_message_in_context.id - 1

            # Проверяем, достаточно ли сообщений для summary
            old_messages_count = (
                session.query(Message)
                .filter(
                    Message.conversation_id == conversation.id,
                    Message.id <= cutoff_id,
                )
                .count()
            )

            if old_messages_count < self.summary_threshold:
                return None

            return cutoff_id

        finally:
            session.close()

    async def get_relevant_context(
        self, user_id: int, query: str, limit: int = 5
    ) -> List[Dict[str, str]]:
        """
        Получить релевантные сообщения из истории через векторный поиск.

        Args:
            user_id: ID пользователя Telegram
            query: Поисковый запрос
            limit: Максимальное количество результатов

        Returns:
            Список сообщений в формате OpenAI API
            [{"role": "user", "content": "..."}, ...]
        """
        if not self.vector_memory or not self.vector_memory.enabled:
            return []

        session = self._get_session()
        try:
            conversation = (
                session.query(Conversation)
                .filter(Conversation.user_id == user_id)
                .first()
            )

            if not conversation:
                return []

            # Выполняем векторный поиск
            relevant_messages = await self.vector_memory.search_relevant_messages(
                query=query,
                user_id=user_id,
                conversation_id=conversation.id,
                limit=limit,
            )

            # Преобразуем в формат OpenAI API
            context = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in relevant_messages
            ]

            logger.debug(
                f"Found {len(context)} relevant messages via vector search for user_id={user_id}"
            )
            return context

        finally:
            session.close()

    def get_context(
        self, user_id: int, limit: Optional[int] = None, query: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Получить контекст диалога для отправки в AI.

        Args:
            user_id: ID пользователя Telegram
            limit: Количество последних сообщений (по умолчанию context_window)
            query: Поисковый запрос для векторного поиска (опционально)

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

            # Получаем общее количество сообщений
            total_messages = (
                session.query(Message)
                .filter(Message.conversation_id == conversation.id)
                .count()
            )

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

            # Если включен векторный поиск и есть query - добавляем релевантные сообщения
            if (
                query
                and self.vector_memory
                and self.vector_memory.enabled
                and total_messages > limit
            ):
                try:
                    # Используем синхронный вызов, но векторный поиск может быть асинхронным
                    # Для простоты, если есть query - векторный поиск будет вызван отдельно
                    # в асинхронном контексте (через get_relevant_context)
                    pass
                except Exception as e:
                    logger.debug(f"Vector search not available: {e}")

            # Если сообщений больше чем limit и включен auto_summarize, добавляем summary
            if (
                total_messages > limit
                and self.auto_summarize
                and messages
                and messages[0].id
            ):
                # cutoff_message_id - это ID последнего сообщения, которое НЕ включено в context
                # (самое старое сообщение в context имеет id = messages[0].id)
                # Но нам нужно summarization для сообщений ДО этого, поэтому берем предыдущий ID
                # Для простоты используем ID первого сообщения в context как границу
                cutoff_id = messages[0].id - 1 if messages[0].id > 1 else None

                if cutoff_id:
                    summary = self.get_summary(conversation.id)
                    if summary:
                        # Добавляем summary в начало контекста
                        context.insert(
                            0, {"role": "system", "content": f"Резюме предыдущего диалога:\n{summary}"}
                        )
                        logger.debug(
                            f"Included summary in context for user_id={user_id}"
                        )

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

    def delete_user_data(self, user_id: int) -> Dict[str, int]:
        """
        Удалить все данные пользователя: сообщения, разговор, контекст и rate limit записи.

        Args:
            user_id: ID пользователя Telegram

        Returns:
            Словарь с количеством удаленных записей:
            {
                "messages": количество удаленных сообщений,
                "conversations": количество удаленных разговоров (0 или 1),
                "user_context": количество удаленных контекстов (0 или 1),
                "rate_limits": количество удаленных rate limit записей (0 или 1)
            }
        """
        session = self._get_session()
        try:
            deleted_counts = {
                "messages": 0,
                "conversations": 0,
                "user_context": 0,
                "rate_limits": 0,
            }

            # Находим conversation для пользователя
            conversation = (
                session.query(Conversation)
                .filter(Conversation.user_id == user_id)
                .first()
            )

            if conversation:
                # Удаляем все сообщения этого разговора
                deleted_messages = (
                    session.query(Message)
                    .filter(Message.conversation_id == conversation.id)
                    .delete()
                )
                deleted_counts["messages"] = deleted_messages

                # Удаляем сам разговор
                session.delete(conversation)
                deleted_counts["conversations"] = 1

            # Удаляем user_context
            deleted_context = (
                session.query(UserContext)
                .filter(UserContext.user_id == user_id)
                .delete()
            )
            deleted_counts["user_context"] = deleted_context

            # Удаляем rate_limits
            deleted_rate_limits = (
                session.query(RateLimit)
                .filter(RateLimit.user_id == user_id)
                .delete()
            )
            deleted_counts["rate_limits"] = deleted_rate_limits

            session.commit()
            logger.info(
                f"Deleted all data for user_id={user_id}: "
                f"{deleted_counts['messages']} messages, "
                f"{deleted_counts['conversations']} conversations, "
                f"{deleted_counts['user_context']} user contexts, "
                f"{deleted_counts['rate_limits']} rate limits"
            )
            return deleted_counts
        finally:
            session.close()

