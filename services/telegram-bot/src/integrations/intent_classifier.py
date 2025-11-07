"""Классификация намерений пользователя."""

import json
import logging
from enum import Enum
from typing import Optional, Tuple

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

    def __init__(self, ai_client=None, confidence_threshold: float = 0.7, use_llm: bool = True):
        """
        Инициализация классификатора.

        Args:
            ai_client: Экземпляр AIClient для LLM-based классификации (опционально)
            confidence_threshold: Минимальный порог уверенности для LLM классификации (0.0-1.0)
            use_llm: Использовать LLM для классификации, fallback на keyword-based если False или ai_client=None
        """
        self.ai_client = ai_client
        self.confidence_threshold = confidence_threshold
        self.use_llm = use_llm
        logger.info(
            f"IntentClassifier initialized: use_llm={use_llm}, "
            f"confidence_threshold={confidence_threshold}"
        )

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

    def _get_intent_classification_prompt(self, message: str, current_intent: Optional[str] = None) -> str:
        """
        Сформировать промпт для классификации намерений через LLM.

        Args:
            message: Сообщение пользователя
            current_intent: Текущее намерение (для контекста)

        Returns:
            Промпт для LLM
        """
        current_intent_context = ""
        if current_intent:
            current_intent_context = f"\n\nТекущее намерение в диалоге: {current_intent}"

        prompt = f"""Определи намерение пользователя в следующем сообщении. Доступные типы намерений:

1. SALES_AI - пользователь интересуется AI-решениями, автоматизацией, разработкой, проектами, услугами Scanovich.ai
2. REAL_ESTATE - пользователь интересуется недвижимостью на Пхукете (виллы, кондо, покупка, аренда, инвестиции)
3. SMALL_TALK - обычный разговор, приветствия, благодарности, общие вопросы без конкретной цели

Сообщение пользователя: "{message}"{current_intent_context}

Верни ответ ТОЛЬКО в формате JSON, без дополнительного текста:
{{
  "intent": "SALES_AI" | "REAL_ESTATE" | "SMALL_TALK",
  "confidence": 0.0-1.0,
  "reasoning": "краткое объяснение (1-2 предложения)"
}}

Уверенность (confidence) должна отражать насколько ты уверен в классификации:
- 0.9-1.0 - очень уверен (явные признаки)
- 0.7-0.9 - уверен (есть признаки)
- 0.5-0.7 - умеренно уверен (некоторые признаки)
- 0.0-0.5 - неуверен (недостаточно информации)

Если сообщение неоднозначное или недостаточно информации, установи низкую уверенность."""

        return prompt

    async def classify_with_confidence(
        self, message: Optional[str], current_intent: Optional[str] = None
    ) -> Tuple[Intent, float]:
        """
        Классифицировать намерение с оценкой уверенности через LLM.

        Args:
            message: Текст сообщения пользователя
            current_intent: Текущее намерение (для сохранения контекста)

        Returns:
            Кортеж (Intent, confidence_score)
        """
        if not message:
            return Intent.SMALL_TALK, 0.5

        # Если LLM недоступен или отключен - используем keyword-based классификацию
        if not self.use_llm or not self.ai_client:
            intent = self.classify(message, current_intent)
            # Для keyword-based даем умеренную уверенность
            confidence = 0.6
            logger.debug(f"Using keyword-based classification: {intent.value} (confidence={confidence})")
            return intent, confidence

        try:
            # Формируем промпт для классификации
            prompt = self._get_intent_classification_prompt(message, current_intent)

            # Отправляем запрос к LLM
            messages = [{"role": "user", "content": prompt}]
            response = await self.ai_client.get_response(
                messages,
                temperature=0.2,  # Низкая температура для более детерминированной классификации
                max_tokens=200,  # Достаточно для JSON ответа
            )

            # Парсим JSON ответ
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            result = json.loads(response)

            # Извлекаем intent и confidence
            intent_str = result.get("intent", "SMALL_TALK")
            confidence = float(result.get("confidence", 0.5))
            reasoning = result.get("reasoning", "")

            # Ограничиваем confidence в диапазоне [0.0, 1.0]
            confidence = max(0.0, min(1.0, confidence))

            try:
                intent = Intent(intent_str)
            except ValueError:
                logger.warning(f"Unknown intent from LLM: {intent_str}, falling back to keyword-based")
                intent = self.classify(message, current_intent)
                confidence = 0.5

            logger.debug(
                f"LLM classification: intent={intent.value}, confidence={confidence:.2f}, "
                f"reasoning={reasoning}"
            )

            # Если уверенность ниже порога - fallback на keyword-based
            if confidence < self.confidence_threshold:
                logger.debug(
                    f"Confidence {confidence:.2f} below threshold {self.confidence_threshold}, "
                    f"falling back to keyword-based classification"
                )
                intent = self.classify(message, current_intent)
                # Используем среднее между LLM confidence и keyword-based confidence
                confidence = (confidence + 0.6) / 2

            return intent, confidence

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse intent classification JSON: {e}")
            logger.debug(f"Response was: {response[:200]}")
            # Fallback на keyword-based
            intent = self.classify(message, current_intent)
            return intent, 0.5
        except Exception as e:
            logger.error(f"Error in LLM-based intent classification: {e}", exc_info=True)
            # Fallback на keyword-based
            intent = self.classify(message, current_intent)
            return intent, 0.5

