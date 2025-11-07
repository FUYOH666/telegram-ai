#!/usr/bin/env python3
"""Скрипт запуска API Gateway Service."""

import logging
import sys
from pathlib import Path

import uvicorn

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
    """Запуск API Gateway Service."""
    try:
        config = Config.from_yaml(str(project_root / "config.yaml"))
        config.validate()

        logger.info("Starting API Gateway Service...")

        # Импортируем и создаем приложение
        import importlib.util
        main_path = project_root / "services" / "api-gateway" / "src" / "main.py"
        spec = importlib.util.spec_from_file_location("api_gateway_main", main_path)
        api_gateway = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(api_gateway)

        app = api_gateway.create_app(config)

        # Запускаем сервер
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
        )

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

