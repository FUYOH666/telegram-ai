"""Событийная система для гибкого управления переходами в диалоге."""

import logging
import time
from collections import defaultdict
from typing import Any, Callable, Dict, List, NamedTuple, Optional

logger = logging.getLogger(__name__)


class Event(NamedTuple):
    """Событие в системе."""

    name: str
    payload: Dict[str, Any]
    timestamp: float  # time.time()


class EventBus:
    """Шина событий для публикации и подписки на события."""

    def __init__(self):
        """Инициализация EventBus."""
        self._subscribers: Dict[str, List[Callable[[Event], None]]] = defaultdict(list)
        logger.info("EventBus initialized")

    def publish(self, event: Event) -> None:
        """
        Публиковать событие, вызывать всех подписчиков.

        Args:
            event: Событие для публикации
        """
        logger.debug(f"Publishing event: {event.name} with payload: {event.payload}")
        
        # Вызываем всех подписчиков на это событие
        handlers = self._subscribers.get(event.name, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    f"Error in event handler for '{event.name}': {e}",
                    exc_info=True,
                )

    def subscribe(
        self, event_name: str, handler: Callable[[Event], None]
    ) -> None:
        """
        Подписаться на событие.

        Args:
            event_name: Название события
            handler: Функция-обработчик события
        """
        self._subscribers[event_name].append(handler)
        logger.debug(f"Subscribed handler to event: {event_name}")

    def unsubscribe(
        self, event_name: str, handler: Callable[[Event], None]
    ) -> None:
        """
        Отписаться от события.

        Args:
            event_name: Название события
            handler: Функция-обработчик события
        """
        if event_name in self._subscribers:
            try:
                self._subscribers[event_name].remove(handler)
                logger.debug(f"Unsubscribed handler from event: {event_name}")
            except ValueError:
                logger.warning(
                    f"Handler not found in subscribers for event: {event_name}"
                )


# Константы для названий событий
EVENT_NEW_MESSAGE = "NEW_MESSAGE"
EVENT_SLOT_FOUND = "SLOT_FOUND"
EVENT_SLOT_CORRECTION = "SLOT_CORRECTION"
EVENT_TIME_PROPOSED = "TIME_PROPOSED"
EVENT_CONSENT_GIVEN = "CONSENT_GIVEN"
EVENT_CONFLICT_FOUND = "CONFLICT_FOUND"
EVENT_INTENT_CHANGED = "INTENT_CHANGED"

