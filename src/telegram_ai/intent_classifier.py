"""Классификация намерений пользователя."""

import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    """Типы намерений пользователя."""

    SALES_AI = "SALES_AI"
    REAL_ESTATE = "REAL_ESTATE"
    SMALL_TALK = "SMALL_TALK"


class IntentClassifier:
    """Классификатор намерений на основе ключевых слов."""

    # Ключевые слова для Sales AI (расширенный список)
    SALES_KEYWORDS = [
        "бот",
        "чат-бот",
        "ai",
        "искусственный интеллект",
        "ии",
        "автоматизация",
        "автоматизировать",
        "ml",
        "machine learning",
        "машинное обучение",
        "ocr",
        "speech",
        "speech-to-text",
        "распознавание",
        "распознать",
        "nlp",
        "natural language processing",
        "компьютерное зрение",
        "computer vision",
        "сканович",
        "scanovich",
        "проект",
        "разработка",
        "разработать",
        "внедрение",
        "внедрить",
        "система",
        "платформа",
        "api",
        "интеграция",
        "интегрировать",
        "модель",
        "нейросеть",
        "llm",
        "чат",
        "ассистент",
        "помощник",
        "решение",
        "технология",
        "алгоритм",
        "анализ данных",
        "data science",
        "deep learning",
        "глубокое обучение",
        "обработка текста",
        "обработка изображений",
        "обработка речи",
        "классификация",
        "классифицировать",
        "рекомендательная система",
        "recommendation system",
    ]

    # Ключевые слова для Real Estate (расширенный список)
    REAL_ESTATE_KEYWORDS = [
        "недвижимость",
        "пхукет",
        "phuket",
        "вилла",
        "кондо",
        "квартира",
        "дом",
        "земля",
        "участок",
        "лаян",
        "лайян",
        "layan",
        "найтон",
        "nai thon",
        "bang tao",
        "банг-тао",
        "бангтао",
        "чанот",
        "chanote",
        "квота",
        "quota",
        "покупка",
        "купить",
        "продажа",
        "продать",
        "аренда",
        "арендовать",
        "снять",
        "инвестиция",
        "инвестировать",
        "инвест",
        "жить",
        "проживание",
        "thb",
        "бат",
        "baht",
        "цена",
        "стоимость",
        "стоит",
        "объект",
        "показ",
        "смотр",
        "посмотреть",
        "посетить",
        "район",
        "location",
        "море",
        "sea",
        "пляж",
        "beach",
        "вид",
        "view",
        "спальни",
        "bedroom",
        "ванная",
        "bathroom",
    ]

    # Ключевые слова для Small Talk
    SMALL_TALK_KEYWORDS = [
        "привет",
        "здравствуй",
        "как дела",
        "спасибо",
        "пожалуйста",
        "погода",
        "как жизнь",
        "что нового",
        "отлично",
        "хорошо",
        "плохо",
        # Английские приветствия
        "hi",
        "hello",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
        "thanks",
        "thank you",
        "how are you",
        "what's up",
    ]

    def __init__(self):
        """Инициализация классификатора."""
        logger.info("IntentClassifier initialized")

    def classify(self, message: Optional[str], current_intent: Optional[str] = None) -> Intent:
        """
        Классифицировать намерение на основе сообщения.

        Args:
            message: Текст сообщения пользователя
            current_intent: Текущее намерение (для сохранения контекста)

        Returns:
            Тип намерения
        """
        if not message:
            return Intent.SMALL_TALK

        message_lower = message.lower()

        # Подсчитываем совпадения по категориям с весами (важные слова имеют больший вес)
        # Веса: 2.0 для очень важных слов, 1.0 для обычных
        important_sales_keywords = {
            "ai", "искусственный интеллект", "ии", "автоматизация", "бот", "чат-бот",
            "сканович", "scanovich", "разработка", "проект", "ocr", "speech-to-text"
        }
        important_real_estate_keywords = {
            "недвижимость", "пхукет", "phuket", "вилла", "кондо", "лаян", "найтон",
            "чанот", "квота", "инвестиция", "покупка", "аренда"
        }

        sales_score = 0.0
        for keyword in self.SALES_KEYWORDS:
            if keyword in message_lower:
                weight = 2.0 if keyword in important_sales_keywords else 1.0
                sales_score += weight

        real_estate_score = 0.0
        for keyword in self.REAL_ESTATE_KEYWORDS:
            if keyword in message_lower:
                weight = 2.0 if keyword in important_real_estate_keywords else 1.0
                real_estate_score += weight

        small_talk_score = sum(
            1 for keyword in self.SMALL_TALK_KEYWORDS if keyword in message_lower
        )

        # Логируем результаты для анализа
        logger.debug(
            f"Intent classification scores: sales={sales_score:.1f}, "
            f"real_estate={real_estate_score:.1f}, small_talk={small_talk_score}, "
            f"current_intent={current_intent}"
        )

        # Если есть явные признаки - используем их (учитываем веса)
        if real_estate_score > 0 and real_estate_score >= sales_score:
            return Intent.REAL_ESTATE
        elif sales_score > 0:
            return Intent.SALES_AI
        elif small_talk_score > 0 and sales_score == 0 and real_estate_score == 0:
            return Intent.SMALL_TALK

        # Если текущее намерение установлено и нет явных признаков смены - сохраняем его
        # Но только если сообщение не очень короткое (для коротких сообщений приоритет small talk)
        if current_intent and len(message.split()) > 3:
            try:
                intent = Intent(current_intent)
                # Если текущий intent не small_talk и нет явных признаков другого intent - сохраняем
                if intent != Intent.SMALL_TALK or small_talk_score == 0:
                    return intent
            except ValueError:
                pass

        # По умолчанию - Small Talk для коротких сообщений, Sales AI для остальных
        if len(message.split()) <= 3:
            return Intent.SMALL_TALK

        return Intent.SALES_AI

