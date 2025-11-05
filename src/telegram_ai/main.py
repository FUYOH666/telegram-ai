"""Точка входа в приложение."""

import asyncio
import logging
import sys
from pathlib import Path

from .config import Config

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


async def main():
    """Основная функция приложения."""
    try:
        # Загружаем конфигурацию
        config_path = Path(__file__).parent.parent.parent / "config.yaml"
        config = Config.from_yaml(str(config_path))

        # Валидируем конфигурацию
        config.validate()

        logger.info("Starting Telegram AI Assistant...")

        # Импортируем клиент здесь чтобы избежать циклических импортов
        from .client import TelegramUserClient

        # Создаем и запускаем клиент
        client = TelegramUserClient(config)
        await client.run()

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

