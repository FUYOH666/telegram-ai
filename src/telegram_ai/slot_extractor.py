"""Автоматическое извлечение слотов из сообщений пользователя через LLM."""

import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class SlotExtractor:
    """Извлечение слотов из сообщений пользователя с помощью LLM."""

    def __init__(self, ai_client=None, enabled: bool = True):
        """
        Инициализация SlotExtractor.

        Args:
            ai_client: Экземпляр AIClient для запросов к LLM
            enabled: Включить автоматическое извлечение слотов
        """
        self.ai_client = ai_client
        self.enabled = enabled
        logger.info(f"SlotExtractor initialized: enabled={enabled}")

    def _get_slot_extraction_prompt(
        self, message: str, intent: str, required_slots: List[str]
    ) -> str:
        """
        Сформировать промпт для извлечения слотов.

        Args:
            message: Сообщение пользователя
            intent: Тип намерения ("SALES_AI" или "REAL_ESTATE")
            required_slots: Список требуемых слотов

        Returns:
            Промпт для LLM
        """
        # Описания слотов для Sales AI
        sales_slot_descriptions = {
            "goal": "Главная цель проекта или задача, которую хочет решить пользователь (например: 'автоматизация поддержки', 'распознавание документов')",
            "domain": "Сфера бизнеса или домен (например: 'медицина', 'финансы', 'ритейл', 'юриспруденция')",
            "deadline": "Сроки проекта (например: 'через месяц', 'к концу года', 'Q2 2024')",
            "budget_band": "Бюджет или диапазон бюджета (например: 'до 500k', '100k-300k', 'не ограничен')",
            "data_access": "Информация о доступе к данным (например: 'есть доступ', 'нужны интеграции', 'данных нет')",
            "success_metric": "Критерий успеха проекта (например: 'сокращение времени обработки на 50%', 'точность 95%')",
            "contact": "Контактная информация (телефон, email, Telegram username)",
        }

        # Описания слотов для Real Estate
        real_estate_slot_descriptions = {
            "purpose": "Цель покупки/аренды (например: 'для жизни', 'инвестиция', 'аренда')",
            "budget": "Бюджет в USD или THB (например: '500k USD', '15M THB', 'до 20M бат')",
            "districts": "Интересующие районы (например: 'Лаян', 'Найтон', 'Банг-Тао')",
            "property_type": "Тип недвижимости (например: 'кондо', 'вилла', 'земля')",
            "beds": "Количество спален (например: '2 спальни', '3+ спальни')",
            "sea_view": "Нужен ли вид на море (например: 'да', 'не важно', 'обязательно')",
            "distance_to_sea": "Расстояние до моря (например: 'до 500м', 'не важно')",
            "title_status": "Статус права (например: 'чанот', 'квота кондо', 'аренда')",
            "timeline": "Сроки покупки/просмотра (например: 'в течение месяца', 'сейчас')",
            "contact": "Контактная информация (телефон, email, Telegram username)",
        }

        slot_descriptions = (
            real_estate_slot_descriptions
            if intent == "REAL_ESTATE"
            else sales_slot_descriptions
        )

        # Формируем список описаний требуемых слотов
        slots_info = []
        for slot in required_slots:
            description = slot_descriptions.get(slot, f"Слот {slot}")
            slots_info.append(f"- {slot}: {description}")

        slots_text = "\n".join(slots_info)

        prompt = f"""Ты помогаешь извлечь структурированную информацию из сообщения пользователя.

Сообщение пользователя: "{message}"

Тип намерения: {intent}

Нужно извлечь следующие слоты (если они упомянуты в сообщении):
{slots_text}

Верни ответ ТОЛЬКО в формате JSON, без дополнительного текста, пример:
{{
  "goal": "автоматизация поддержки клиентов",
  "budget_band": "до 500k",
  "contact": "+7XXXXXXXXXX"
}}

Если слот не упомянут в сообщении, не включай его в JSON.
Если не нашлось ни одного слота, верни пустой объект {{}}."""

        return prompt

    async def extract_slots(
        self, message: str, intent: str, required_slots: List[str]
    ) -> Dict[str, Any]:
        """
        Извлечь слоты из сообщения пользователя с помощью LLM.

        Args:
            message: Сообщение пользователя
            intent: Тип намерения ("SALES_AI" или "REAL_ESTATE")
            required_slots: Список требуемых слотов для извлечения

        Returns:
            Словарь с извлеченными слотами {slot_name: value}
        """
        if not self.enabled or not self.ai_client:
            logger.debug("Slot extraction disabled or AI client not available")
            return {}

        if not required_slots:
            logger.debug("No required slots to extract")
            return {}

        try:
            # Формируем промпт для извлечения слотов
            prompt = self._get_slot_extraction_prompt(message, intent, required_slots)

            # Отправляем запрос к LLM
            messages = [{"role": "user", "content": prompt}]
            response = await self.ai_client.get_response(
                messages,
                temperature=0.3,  # Низкая температура для более детерминированного ответа
                max_tokens=500,  # Достаточно для JSON ответа
            )

            # Парсим JSON ответ
            # Убираем markdown code blocks если есть
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            extracted_slots = json.loads(response)

            if not isinstance(extracted_slots, dict):
                logger.warning(
                    f"Invalid slot extraction response format: {type(extracted_slots)}"
                )
                return {}

            # Фильтруем только те слоты, которые в required_slots
            filtered_slots = {
                slot: value
                for slot, value in extracted_slots.items()
                if slot in required_slots and value
            }

            logger.info(
                f"Extracted {len(filtered_slots)} slots from message: {list(filtered_slots.keys())}"
            )
            logger.debug(f"Extracted slots: {filtered_slots}")

            return filtered_slots

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse slot extraction JSON: {e}")
            logger.debug(f"Response was: {response[:200]}")
            return {}
        except Exception as e:
            logger.error(f"Error extracting slots: {e}", exc_info=True)
            return {}
