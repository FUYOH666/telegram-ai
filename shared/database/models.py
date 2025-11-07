"""SQLAlchemy модели для базы данных (PostgreSQL/SQLite)."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base

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
    message_metadata = Column(Text, nullable=True)  # JSON строка с дополнительными данными (переименовано из metadata)


class UserContext(Base):
    """Модель таблицы user_context для хранения контекста пользователя."""

    __tablename__ = "user_context"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, unique=True, index=True)
    context_data = Column(Text, nullable=True)  # JSON строка с дополнительными данными
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Lead(Base):
    """Модель таблицы leads для хранения лидов."""

    __tablename__ = "leads"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    contact = Column(String(255), nullable=True)
    source = Column(String(50), default="telegram", nullable=False)
    status = Column(String(50), default="active", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class LeadSlot(Base):
    """Модель таблицы lead_slots для хранения слотов лидов."""

    __tablename__ = "lead_slots"

    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, nullable=False, index=True)
    slot_name = Column(String(100), nullable=False)
    slot_value = Column(Text, nullable=False)
    extracted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class SalesStage(Base):
    """Модель таблицы sales_stages для отслеживания этапов продаж."""

    __tablename__ = "sales_stages"

    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, nullable=False, index=True)
    stage = Column(String(50), nullable=False)
    transitioned_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    stage_metadata = Column(Text, nullable=True)  # JSON строка с дополнительными данными (переименовано из metadata)


class SalesEvent(Base):
    """Модель таблицы sales_events для событий продаж."""

    __tablename__ = "sales_events"

    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    event_data = Column(Text, nullable=True)  # JSON строка с данными события
    occurred_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class Meeting(Base):
    """Модель таблицы meetings для встреч."""

    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, nullable=False, index=True)
    scheduled_at = Column(DateTime, nullable=False)
    duration = Column(Integer, default=60, nullable=False)  # в минутах
    status = Column(String(50), default="scheduled", nullable=False)
    calendar_event_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class MeetingSummary(Base):
    """Модель таблицы meeting_summaries для сводок встреч."""

    __tablename__ = "meeting_summaries"

    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, nullable=False, index=True)
    summary_text = Column(Text, nullable=False)
    summary_json = Column(Text, nullable=True)  # JSON строка со структурированными данными
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


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


class GlobalRateLimit(Base):
    """Модель таблицы global_rate_limits для глобального лимита на уровне аккаунта."""

    __tablename__ = "global_rate_limits"

    id = Column(Integer, primary_key=True, default=1)  # Всегда одна запись
    message_count_minute = Column(Integer, default=0, nullable=False)
    message_count_hour = Column(Integer, default=0, nullable=False)
    window_start_minute = Column(DateTime, nullable=False)
    window_start_hour = Column(DateTime, nullable=False)
    blocked_until = Column(DateTime, nullable=True)
    last_message_time = Column(DateTime, nullable=False)


class FloodWaitHistory(Base):
    """Модель таблицы flood_wait_history для отслеживания истории FloodWait событий."""

    __tablename__ = "flood_wait_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wait_seconds = Column(Integer, nullable=False)
    occurred_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    chat_type = Column(String(20), nullable=True)  # 'private', 'group', 'channel'


class ConversationSummary(Base):
    """Модель таблицы conversation_summaries для хранения резюме диалогов."""

    __tablename__ = "conversation_summaries"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, nullable=False, index=True)
    summary_text = Column(Text, nullable=False)
    cutoff_message_id = Column(Integer, nullable=False)  # ID последнего сообщения, включенного в summary
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ConversationMetric(Base):
    """Модель таблицы conversation_metrics для аналитики."""

    __tablename__ = "conversation_metrics"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, nullable=False, index=True)
    message_count = Column(Integer, default=0, nullable=False)
    duration_days = Column(Integer, default=0, nullable=False)
    top_themes = Column(Text, nullable=True)  # JSON массив тем
    tone = Column(String(50), nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ConversionFunnel(Base):
    """Модель таблицы conversion_funnel для воронки конверсий."""

    __tablename__ = "conversion_funnel"

    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, nullable=False, index=True)
    stage = Column(String(50), nullable=False)
    entered_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    exited_at = Column(DateTime, nullable=True)

