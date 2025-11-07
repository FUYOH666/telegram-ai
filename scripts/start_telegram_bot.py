#!/usr/bin/env python3
"""Скрипт запуска Telegram Bot Service."""

import asyncio
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

# Подавляем ошибки телеметрии ChromaDB (не критичные)
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)
# Подавляем предупреждения о file_cache в Google API
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


async def main():
    """Запуск Telegram Bot Service."""
    try:
        config = Config.from_yaml(str(project_root / "config.yaml"))
        config.validate()

        logger.info("Starting Telegram Bot Service...")

        # Импортируем клиент через правильный путь
        # Добавляем src в sys.path для корректных импортов
        src_path = project_root / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))
        
        # Импортируем как модуль
        from telegram_ai.client import TelegramUserClient

        client = TelegramUserClient(config)
        await client.run()

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

