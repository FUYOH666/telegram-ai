"""Главный файл для запуска Telegram Bot Service."""

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корень проекта в путь для импортов
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.config.settings import Config

logger = logging.getLogger(__name__)


async def main():
    """Основная функция для запуска Telegram Bot Service."""
    try:
        # Загружаем конфигурацию
        config_path = project_root / "config.yaml"
        config = Config.from_yaml(str(config_path))
        config.validate()

        logger.info("Starting Telegram Bot Service...")

        # TODO: Инициализировать и запустить Telegram Bot
        # Импортируем существующий client.py и адаптируем под новую структуру
        # from services.telegram_bot.src.integrations.client import TelegramUserClient
        # client = TelegramUserClient(config)
        # await client.run()

        logger.info("Telegram Bot Service started")

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


def cli():
    """CLI точка входа."""
    asyncio.run(main())


if __name__ == "__main__":
    cli()

