"""Задачи для генерации summary встреч."""

from celery import Celery
import logging

logger = logging.getLogger(__name__)

# Celery app будет инициализирован в main
app = None


def init_celery_app(redis_url: str) -> Celery:
    """
    Инициализировать Celery приложение.

    Args:
        redis_url: URL Redis для брокера

    Returns:
        Celery приложение
    """
    global app
    app = Celery(
        "telegram_ai_worker",
        broker=redis_url,
        backend=redis_url,
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
    )
    return app


@app.task(name="generate_meeting_summary")
def generate_meeting_summary(meeting_id: int, slots: dict, conversation_history: list):
    """
    Генерировать summary для встречи.

    Args:
        meeting_id: ID встречи
        slots: Заполненные слоты
        conversation_history: История диалога

    Returns:
        Сгенерированный summary
    """
    # TODO: Реализовать генерацию summary
    logger.info(f"Generating meeting summary for meeting_id={meeting_id}")
    return {"status": "pending", "meeting_id": meeting_id}

