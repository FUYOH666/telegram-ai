"""Инструменты для работы с лидами и данными."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class Tools:
    """Набор инструментов для работы с лидами и данными."""

    def __init__(self, memory=None, web_search_tool=None):
        """
        Инициализация инструментов.

        Args:
            memory: Экземпляр Memory для работы с БД
            web_search_tool: Экземпляр WebSearchTool для веб-поиска
        """
        self.memory = memory
        self.web_search_tool = web_search_tool
        logger.info("Tools initialized")

    def save_lead(
        self,
        user_id: int,
        name: Optional[str] = None,
        lang: str = "ru",
        contact: Optional[str] = None,
        source: Optional[str] = "telegram",
        slots: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Сохранить лид в контексте пользователя.

        Args:
            user_id: ID пользователя Telegram
            name: Имя пользователя
            lang: Язык общения
            contact: Контакт (телефон, email и т.д.)
            source: Источник лида
            slots: Заполненные слоты
            notes: Дополнительные заметки

        Returns:
            Словарь с результатом сохранения
        """
        if not self.memory:
            logger.warning("Memory not available, cannot save lead")
            return {"lead_id": None, "status": "error", "error": "Memory not available"}

        try:
            # Получаем текущий контекст
            user_context_data = self.memory.get_user_context(user_id)
            if user_context_data:
                try:
                    data = json.loads(user_context_data)
                except (json.JSONDecodeError, ValueError):
                    data = {}
            else:
                data = {}

            # Обновляем данные лида
            if name:
                data["name"] = name
            data["lang"] = lang
            if contact:
                data["contact"] = contact
            data["source"] = source or "telegram"
            if slots:
                if "slots" not in data:
                    data["slots"] = {}
                data["slots"].update(slots)
            if notes:
                data["notes"] = notes

            data["lead_saved_at"] = datetime.now(timezone.utc).isoformat()
            data["lead_status"] = "active"

            # Сохраняем обновленный контекст
            updated_context = json.dumps(data)
            self.memory.save_user_context(user_id, updated_context)

            logger.info(f"Lead saved for user_id={user_id}, name={name}, contact={contact}")

            return {
                "lead_id": f"lead_{user_id}",
                "status": "saved",
                "user_id": user_id,
            }
        except Exception as e:
            logger.error(f"Error saving lead: {e}", exc_info=True)
            return {"lead_id": None, "status": "error", "error": str(e)}

    def get_lead_data(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить данные лида из контекста.

        Args:
            user_id: ID пользователя Telegram

        Returns:
            Словарь с данными лида или None
        """
        if not self.memory:
            return None

        try:
            user_context_data = self.memory.get_user_context(user_id)
            if not user_context_data:
                return None

            data = json.loads(user_context_data)
            return {
                "user_id": user_id,
                "name": data.get("name"),
                "lang": data.get("lang", "ru"),
                "contact": data.get("contact"),
                "source": data.get("source", "telegram"),
                "slots": data.get("slots", {}),
                "intent": data.get("intent"),
                "sales_stage": data.get("sales_stage"),
                "notes": data.get("notes"),
                "lead_saved_at": data.get("lead_saved_at"),
                "lead_status": data.get("lead_status"),
            }
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error getting lead data: {e}")
            return None

    async def web_search(
        self, query: str, user_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Выполнить веб-поиск через WebSearchTool.

        Args:
            query: Поисковый запрос
            user_id: ID пользователя (для проверки лимитов)

        Returns:
            Словарь с результатами поиска или None если поиск недоступен
        """
        if not self.web_search_tool:
            logger.debug("WebSearchTool not available")
            return None

        try:
            # Проверяем лимиты запросов за диалог (если есть memory и user_id)
            if self.memory and user_id is not None:
                user_context_data = self.memory.get_user_context(user_id)
                if user_context_data:
                    try:
                        data = json.loads(user_context_data)
                        web_search_count = data.get("web_search_count", 0)
                        max_queries = self.web_search_tool.max_queries_per_conversation if hasattr(
                            self.web_search_tool, "max_queries_per_conversation"
                        ) else 2
                        
                        if web_search_count >= max_queries:
                            logger.debug(
                                f"Web search limit reached for user_id={user_id}: "
                                f"{web_search_count}/{max_queries}"
                            )
                            return None
                    except (json.JSONDecodeError, ValueError):
                        pass

            # Выполняем поиск
            result = await self.web_search_tool.search(query)
            
            # Обновляем счетчик запросов
            if self.memory and user_id is not None:
                user_context_data = self.memory.get_user_context(user_id)
                if user_context_data:
                    try:
                        data = json.loads(user_context_data)
                        data["web_search_count"] = data.get("web_search_count", 0) + 1
                        self.memory.save_user_context(user_id, json.dumps(data))
                    except (json.JSONDecodeError, ValueError):
                        pass

            return result
        except Exception as e:
            logger.error(f"Error performing web search: {e}", exc_info=True)
            return None

