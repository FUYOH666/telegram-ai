"""API endpoints для аналитики."""

import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shared.config.settings import Config
from shared.database.connection import get_db_session
from shared.database.models import Lead, Conversation

logger = logging.getLogger(__name__)

router = APIRouter()


class MetricsResponse(BaseModel):
    """Схема ответа для метрик."""

    total_leads: int
    total_conversations: int
    active_leads: int
    conversion_rate: float
    updated_at: datetime


@router.get("/analytics/metrics", response_model=MetricsResponse)
async def get_metrics():
    """
    Получить метрики и статистику.

    Returns:
        Метрики системы
    """
    try:
        config = Config.from_yaml("config.yaml")
        session: Session = get_db_session(config.database)

        try:
            # Подсчитываем общее количество лидов
            total_leads_stmt = select(func.count(Lead.id))
            total_leads = session.execute(total_leads_stmt).scalar() or 0

            # Подсчитываем активные лиды
            active_leads_stmt = select(func.count(Lead.id)).where(Lead.status == "active")
            active_leads = session.execute(active_leads_stmt).scalar() or 0

            # Подсчитываем общее количество диалогов
            total_conversations_stmt = select(func.count(Conversation.id))
            total_conversations = session.execute(total_conversations_stmt).scalar() or 0

            # Вычисляем конверсию (лиды с диалогами / общее количество лидов)
            conversion_rate = (total_conversations / total_leads * 100) if total_leads > 0 else 0.0

            return MetricsResponse(
                total_leads=total_leads,
                total_conversations=total_conversations,
                active_leads=active_leads,
                conversion_rate=round(conversion_rate, 2),
                updated_at=datetime.now(),
            )
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error getting metrics: {e}", exc_info=True)
        # Возвращаем пустые метрики при ошибке
        return MetricsResponse(
            total_leads=0,
            total_conversations=0,
            active_leads=0,
            conversion_rate=0.0,
            updated_at=datetime.now(),
        )


@router.get("/analytics/reports")
async def get_reports():
    """
    Получить отчеты.

    Returns:
        Отчеты по конверсиям и этапам продаж
    """
    # TODO: Реализовать генерацию отчетов
    return {"reports": []}

