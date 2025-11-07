"""Управление согласиями пользователей (PDPA, GDPR и др.)."""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ConsentManager:
    """Менеджер согласий для обработки персональных данных."""

    # Типы согласий
    CONSENT_PDPA_PROFILE = "pdpa_profile"  # Сбор профиля (PDPA для Таиланда)
    CONSENT_CALENDAR_INVITE = "calendar_invite"  # Создание встреч в календаре

    def __init__(self, memory):
        """
        Инициализация ConsentManager.

        Args:
            memory: Экземпляр Memory для работы с контекстом пользователя
        """
        self.memory = memory
        logger.info("ConsentManager initialized")

    def check_consent(self, user_id: int, consent_type: str) -> bool:
        """
        Проверить, есть ли согласие пользователя.

        Args:
            user_id: ID пользователя Telegram
            consent_type: Тип согласия ("pdpa_profile", "calendar_invite")

        Returns:
            True если согласие предоставлено, False иначе
        """
        consents = self.memory.get_user_consents(user_id)
        consent_data = consents.get(consent_type, {})
        return consent_data.get("granted", False)

    def request_consent(
        self, user_id: int, consent_type: str, message: str
    ) -> Optional[str]:
        """
        Запросить согласие у пользователя (возвращает текст запроса).

        Args:
            user_id: ID пользователя Telegram
            consent_type: Тип согласия ("pdpa_profile", "calendar_invite")
            message: Сообщение для пользователя

        Returns:
            Текст запроса согласия или None если согласие уже есть
        """
        if self.check_consent(user_id, consent_type):
            logger.debug(
                f"Consent '{consent_type}' already granted for user_id={user_id}"
            )
            return None

        # Генерируем текст запроса в зависимости от типа согласия
        if consent_type == self.CONSENT_PDPA_PROFILE:
            consent_text = (
                f"{message}\n\n"
                "Для продолжения нужно ваше согласие на обработку персональных данных "
                "(PDPA - Personal Data Protection Act). Продолжить? [Да/Нет]"
            )
        elif consent_type == self.CONSENT_CALENDAR_INVITE:
            consent_text = (
                f"{message}\n\n"
                "Для создания встречи в календаре нужно ваше согласие. "
                "Создать встречу? [Да/Нет]"
            )
        else:
            consent_text = f"{message}\n\nНужно ваше согласие. Продолжить? [Да/Нет]"

        logger.info(f"Requesting consent '{consent_type}' for user_id={user_id}")
        return consent_text

    def record_consent(
        self, user_id: int, consent_type: str, granted: bool
    ) -> None:
        """
        Записать согласие пользователя.

        Args:
            user_id: ID пользователя Telegram
            consent_type: Тип согласия ("pdpa_profile", "calendar_invite")
            granted: Предоставлено ли согласие
        """
        self.memory.save_user_consent(user_id, consent_type, granted)
        logger.info(
            f"Recorded consent '{consent_type}'={granted} for user_id={user_id}"
        )

    def parse_consent_response(self, message: str) -> Optional[bool]:
        """
        Распарсить ответ пользователя на запрос согласия.

        Args:
            message: Сообщение пользователя

        Returns:
            True если согласие, False если отказ, None если не распознано
        """
        message_lower = message.lower().strip()

        # Положительные ответы
        positive_keywords = [
            "да",
            "yes",
            "ок",
            "ok",
            "согласен",
            "согласна",
            "согласны",
            "продолжить",
            "продолжать",
            "создать",
            "создай",
            "подтверждаю",
            "подтверждаем",
            "✅",
            "👍",
        ]

        # Отрицательные ответы
        negative_keywords = [
            "нет",
            "no",
            "не",
            "не нужно",
            "не хочу",
            "отмена",
            "отменить",
            "отказ",
            "❌",
            "👎",
        ]

        if any(keyword in message_lower for keyword in positive_keywords):
            return True
        elif any(keyword in message_lower for keyword in negative_keywords):
            return False

        return None

