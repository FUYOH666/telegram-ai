"""API endpoints для работы с лидами."""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.config.settings import Config
from shared.database.connection import get_db_session
from shared.database.models import Lead

logger = logging.getLogger(__name__)

router = APIRouter()


class LeadResponse(BaseModel):
    """Схема ответа для лида."""

    id: int
    user_id: int
    name: Optional[str]
    contact: Optional[str]
    source: str
    status: str
    created_at: datetime
    updated_at: datetime


class LeadCreate(BaseModel):
    """Схема создания лида."""

    user_id: int
    name: Optional[str] = None
    contact: Optional[str] = None
    source: str = "telegram"


@router.get("/leads", response_model=List[LeadResponse])
async def list_leads(limit: int = 100, offset: int = 0):
    """
    Получить список лидов.

    Args:
        limit: Максимальное количество результатов
        offset: Смещение для пагинации

    Returns:
        Список лидов
    """
    try:
        # Загружаем конфигурацию для получения сессии БД
        config = Config.from_yaml("config.yaml")
        session: Session = get_db_session(config.database)

        try:
            # Получаем лиды из БД
            stmt = select(Lead).limit(limit).offset(offset).order_by(Lead.created_at.desc())
            leads = session.execute(stmt).scalars().all()

            return [
                LeadResponse(
                    id=lead.id,
                    user_id=lead.user_id,
                    name=lead.name,
                    contact=lead.contact,
                    source=lead.source,
                    status=lead.status,
                    created_at=lead.created_at,
                    updated_at=lead.updated_at,
                )
                for lead in leads
            ]
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error listing leads: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/leads/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: int):
    """
    Получить детали лида.

    Args:
        lead_id: ID лида

    Returns:
        Детали лида

    Raises:
        HTTPException: Если лид не найден
    """
    try:
        config = Config.from_yaml("config.yaml")
        session: Session = get_db_session(config.database)

        try:
            stmt = select(Lead).where(Lead.id == lead_id)
            lead = session.execute(stmt).scalar_one_or_none()

            if not lead:
                raise HTTPException(status_code=404, detail="Lead not found")

            return LeadResponse(
                id=lead.id,
                user_id=lead.user_id,
                name=lead.name,
                contact=lead.contact,
                source=lead.source,
                status=lead.status,
                created_at=lead.created_at,
                updated_at=lead.updated_at,
            )
        finally:
            session.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting lead {lead_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/leads", response_model=LeadResponse)
async def create_lead(lead: LeadCreate):
    """
    Создать новый лид.

    Args:
        lead: Данные лида

    Returns:
        Созданный лид
    """
    # TODO: Реализовать создание в БД
    return LeadResponse(
        id=1,
        user_id=lead.user_id,
        name=lead.name,
        contact=lead.contact,
        source=lead.source,
        status="active",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@router.put("/leads/{lead_id}", response_model=LeadResponse)
async def update_lead(lead_id: int, lead: LeadCreate):
    """
    Обновить лид.

    Args:
        lead_id: ID лида
        lead: Обновленные данные

    Returns:
        Обновленный лид

    Raises:
        HTTPException: Если лид не найден
    """
    # TODO: Реализовать обновление в БД
    raise HTTPException(status_code=404, detail="Lead not found")

