"""Точка входа в приложение."""

import asyncio
import logging
import sys
import sqlite3
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
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e).lower():
            logger.error(
                "Database is locked. This usually means:\n"
                "  1. Another instance of the application is already running\n"
                "  2. A previous instance didn't close properly\n"
                "\n"
                "Solutions:\n"
                "  - Check if another instance is running: ps aux | grep telegram-ai\n"
                "  - Kill the other instance: kill <PID>\n"
                "  - Or wait a few seconds and try again"
            )
            print(
                "\n❌ Ошибка: База данных заблокирована.\n"
                "   Вероятно, уже запущен другой экземпляр приложения.\n"
                "   Проверьте: ps aux | grep telegram-ai\n"
                "   Или подождите несколько секунд и попробуйте снова.\n"
            )
        else:
            logger.error(f"SQLite error: {e}", exc_info=True)
            print(f"\n❌ Ошибка базы данных: {e}\n")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


def cli():
    """CLI точка входа."""
    asyncio.run(main())


if __name__ == "__main__":
    cli()

