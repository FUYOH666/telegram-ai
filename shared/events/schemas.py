"""Схемы событий для event bus."""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel


class LeadCreated(BaseModel):
    """Событие создания лида."""

    user_id: int
    lead_id: int
    slots: Dict[str, Any]
    occurred_at: datetime


class LeadStageChanged(BaseModel):
    """Событие изменения этапа продаж."""

    lead_id: int
    old_stage: str
    new_stage: str
    occurred_at: datetime


class MeetingScheduled(BaseModel):
    """Событие назначения встречи."""

    meeting_id: int
    lead_id: int
    scheduled_at: datetime
    occurred_at: datetime


class MeetingSummaryGenerated(BaseModel):
    """Событие генерации summary встречи."""

    meeting_id: int
    summary: str
    occurred_at: datetime


class MessageReceived(BaseModel):
    """Событие получения сообщения."""

    user_id: int
    message_id: int
    content: str
    occurred_at: datetime


class ConversationStarted(BaseModel):
    """Событие начала диалога."""

    user_id: int
    conversation_id: int
    occurred_at: datetime


class ConversationSummaryCreated(BaseModel):
    """Событие создания summary диалога."""

    conversation_id: int
    summary: str
    occurred_at: datetime

