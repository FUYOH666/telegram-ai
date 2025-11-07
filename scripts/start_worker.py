#!/usr/bin/env python3
"""Скрипт запуска Worker Service (Celery)."""

import logging
import sys
from pathlib import Path

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from shared.config.settings import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Запуск Worker Service."""
    try:
        config = Config.from_yaml(str(project_root / "config.yaml"))
        config.validate()

        logger.info("Starting Worker Service (Celery)...")

        # TODO: Инициализировать Celery и запустить worker
        # from services.worker.src.celery_app import celery_app
        # celery_app.worker_main()

        logger.warning("Worker Service not yet fully implemented")
        logger.info("To start Celery worker, run: celery -A services.worker.src.celery_app worker --loglevel=info")

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

