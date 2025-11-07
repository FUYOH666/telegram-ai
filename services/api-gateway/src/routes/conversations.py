"""API endpoints для работы с диалогами."""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.config.settings import Config
from shared.database.connection import get_db_session
from shared.database.models import Conversation, Message

logger = logging.getLogger(__name__)

router = APIRouter()


class MessageResponse(BaseModel):
    """Схема ответа для сообщения."""

    id: int
    conversation_id: int
    role: str
    content: str
    timestamp: datetime


class ConversationResponse(BaseModel):
    """Схема ответа для диалога."""

    id: int
    user_id: int
    username: Optional[str]
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = []


@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(limit: int = 100, offset: int = 0):
    """
    Получить список диалогов.

    Args:
        limit: Максимальное количество результатов
        offset: Смещение для пагинации

    Returns:
        Список диалогов
    """
    try:
        config = Config.from_yaml("config.yaml")
        session: Session = get_db_session(config.database)

        try:
            stmt = select(Conversation).limit(limit).offset(offset).order_by(Conversation.updated_at.desc())
            conversations = session.execute(stmt).scalars().all()

            return [
                ConversationResponse(
                    id=conv.id,
                    user_id=conv.user_id,
                    username=conv.username,
                    created_at=conv.created_at,
                    updated_at=conv.updated_at,
                    messages=[],  # Можно добавить загрузку сообщений при необходимости
                )
                for conv in conversations
            ]
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error listing conversations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: int):
    """
    Получить историю диалога.

    Args:
        conversation_id: ID диалога

    Returns:
        История диалога с сообщениями

    Raises:
        HTTPException: Если диалог не найден
    """
    try:
        config = Config.from_yaml("config.yaml")
        session: Session = get_db_session(config.database)

        try:
            # Получаем диалог
            stmt = select(Conversation).where(Conversation.id == conversation_id)
            conv = session.execute(stmt).scalar_one_or_none()

            if not conv:
                raise HTTPException(status_code=404, detail="Conversation not found")

            # Получаем сообщения
            stmt = select(Message).where(Message.conversation_id == conversation_id).order_by(Message.timestamp)
            messages = session.execute(stmt).scalars().all()

            return ConversationResponse(
                id=conv.id,
                user_id=conv.user_id,
                username=conv.username,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                messages=[
                    MessageResponse(
                        id=msg.id,
                        conversation_id=msg.conversation_id,
                        role=msg.role,
                        content=msg.content,
                        timestamp=msg.timestamp,
                    )
                    for msg in messages
                ],
            )
        finally:
            session.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation {conversation_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

