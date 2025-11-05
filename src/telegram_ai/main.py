"""Точка входа в приложение."""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime

from .config import Config

# Создаем директорию для логов
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Имя файла лога с датой
log_file = logs_dir / f"telegram-ai-{datetime.now().strftime('%Y%m%d')}.log"

# Настройка логирования - и в консоль, и в файл
logging.basicConfig(
    level=logging.DEBUG,  # DEBUG для детального логирования
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),  # Консоль
        logging.FileHandler(log_file, encoding="utf-8"),  # Файл
    ],
)

logger = logging.getLogger(__name__)
logger.info(f"Logging initialized. Log file: {log_file}")


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

