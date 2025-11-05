"""Скрипт продаж (Sales Flow) с state machine."""

import json
import logging
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class SalesStage(str, Enum):
    """Этапы скрипта продаж."""

    GREETING = "greeting"
    NEEDS_DISCOVERY = "needs_discovery"
    PRESENTATION = "presentation"
    OBJECTIONS = "objections"
    CONSULTATION_OFFER = "consultation_offer"
    SCHEDULING = "scheduling"


class SalesFlow:
    """Управление скриптом продаж с state machine."""

    # Ключевые слова для переходов между этапами
    GREETING_KEYWORDS = ["привет", "здравствуй", "добрый", "здравствуйте", "начать"]
    NEEDS_KEYWORDS = [
        "нужно",
        "хочу",
        "интересно",
        "проблема",
        "задача",
        "помощь",
        "автоматизация",
    ]
    PRESENTATION_KEYWORDS = [
        "расскажи",
        "что",
        "как",
        "услуги",
        "решения",
        "возможности",
    ]
    OBJECTIONS_KEYWORDS = [
        "дорого",
        "не нужно",
        "не интересно",
        "позже",
        "думаю",
        "сомневаюсь",
    ]
    CONSULTATION_KEYWORDS = [
        "консультация",
        "встреча",
        "обсудить",
        "поговорить",
        "узнать больше",
    ]
    SCHEDULING_KEYWORDS = [
        "когда",
        "время",
        "договориться",
        "записаться",
        "встретиться",
    ]

    def __init__(self, enabled: bool = True):
        """
        Инициализация SalesFlow.

        Args:
            enabled: Включить скрипт продаж
        """
        self.enabled = enabled
        logger.info(f"SalesFlow initialized: enabled={enabled}")

    def get_stage(self, context_data: Optional[str]) -> SalesStage:
        """
        Получить текущий этап из контекста.

        Args:
            context_data: JSON строка с контекстом пользователя

        Returns:
            Текущий этап скрипта продаж
        """
        if not context_data:
            return SalesStage.GREETING

        try:
            data = json.loads(context_data)
            stage_str = data.get("sales_stage", "greeting")
            return SalesStage(stage_str)
        except (json.JSONDecodeError, ValueError):
            return SalesStage.GREETING

    def update_stage(
        self, context_data: Optional[str], new_stage: SalesStage
    ) -> str:
        """
        Обновить этап в контексте.

        Args:
            context_data: Текущий JSON контекст
            new_stage: Новый этап

        Returns:
            Обновленный JSON контекст
        """
        if context_data:
            try:
                data = json.loads(context_data)
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}

        data["sales_stage"] = new_stage.value
        return json.dumps(data)

    def detect_stage_transition(self, message: str, current_stage: SalesStage) -> Optional[SalesStage]:
        """
        Определить переход на следующий этап на основе сообщения.

        Args:
            message: Текст сообщения пользователя
            current_stage: Текущий этап

        Returns:
            Новый этап или None если переход не требуется
        """
        if not self.enabled:
            return None

        message_lower = message.lower()

        # Логика переходов
        if current_stage == SalesStage.GREETING:
            if any(keyword in message_lower for keyword in self.NEEDS_KEYWORDS):
                return SalesStage.NEEDS_DISCOVERY
            if any(keyword in message_lower for keyword in self.PRESENTATION_KEYWORDS):
                return SalesStage.PRESENTATION

        elif current_stage == SalesStage.NEEDS_DISCOVERY:
            if any(keyword in message_lower for keyword in self.PRESENTATION_KEYWORDS):
                return SalesStage.PRESENTATION
            if any(keyword in message_lower for keyword in self.OBJECTIONS_KEYWORDS):
                return SalesStage.OBJECTIONS

        elif current_stage == SalesStage.PRESENTATION:
            if any(keyword in message_lower for keyword in self.OBJECTIONS_KEYWORDS):
                return SalesStage.OBJECTIONS
            if any(keyword in message_lower for keyword in self.CONSULTATION_KEYWORDS):
                return SalesStage.CONSULTATION_OFFER

        elif current_stage == SalesStage.OBJECTIONS:
            if any(keyword in message_lower for keyword in self.CONSULTATION_KEYWORDS):
                return SalesStage.CONSULTATION_OFFER

        elif current_stage == SalesStage.CONSULTATION_OFFER:
            if any(keyword in message_lower for keyword in self.SCHEDULING_KEYWORDS):
                return SalesStage.SCHEDULING

        return None

    def get_stage_prompt_modifier(self, stage: SalesStage) -> str:
        """
        Получить модификатор системного промпта для этапа.

        Args:
            stage: Этап скрипта продаж

        Returns:
            Дополнительный текст для системного промпта
        """
        modifiers = {
            SalesStage.GREETING: (
                "Сейчас этап приветствия. Поприветствуй пользователя дружелюбно, "
                "представься как ассистент Scanovich.ai. Спроси, чем можешь помочь."
            ),
            SalesStage.NEEDS_DISCOVERY: (
                "Сейчас этап выявления потребностей. Задавай уточняющие вопросы, "
                "чтобы понять потребности пользователя. Будь любопытным, но не навязчивым."
            ),
            SalesStage.PRESENTATION: (
                "Сейчас этап презентации услуг. Расскажи о возможностях Scanovich.ai, "
                "но делай это естественно, основываясь на выявленных потребностях пользователя."
            ),
            SalesStage.OBJECTIONS: (
                "Сейчас этап работы с возражениями. Выслушай возражения пользователя, "
                "постарайся понять их причины и предложи решения. Будь понимающим и терпеливым."
            ),
            SalesStage.CONSULTATION_OFFER: (
                "Сейчас этап предложения консультации. Предложи бесплатную консультацию, "
                "чтобы обсудить детали и найти лучшее решение для пользователя."
            ),
            SalesStage.SCHEDULING: (
                "Сейчас этап согласования времени встречи. Помоги пользователю выбрать удобное время. "
                "Будь гибким и предложи несколько вариантов."
            ),
        }

        return modifiers.get(stage, "")

