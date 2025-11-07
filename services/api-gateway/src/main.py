"""FastAPI приложение для REST API Gateway."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config.settings import Config

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""
    # Startup
    logger.info("Starting API Gateway...")
    # Здесь можно инициализировать подключения к БД, Redis и т.д.
    yield
    # Shutdown
    logger.info("Shutting down API Gateway...")


def create_app(config: Config) -> FastAPI:
    """
    Создать FastAPI приложение.

    Args:
        config: Конфигурация приложения

    Returns:
        FastAPI приложение
    """
    app = FastAPI(
        title="Telegram AI API Gateway",
        description="REST API для интеграций с Telegram AI Assistant",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # В production указать конкретные домены
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Импортируем роуты (используем относительные импорты)
    try:
        # Добавляем путь к проекту для импортов
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        # Импортируем роуты через прямые пути
        import importlib.util
        leads_path = project_root / "services" / "api-gateway" / "src" / "routes" / "leads.py"
        conversations_path = project_root / "services" / "api-gateway" / "src" / "routes" / "conversations.py"
        analytics_path = project_root / "services" / "api-gateway" / "src" / "routes" / "analytics.py"
        
        spec = importlib.util.spec_from_file_location("leads", leads_path)
        leads = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(leads)
        
        spec = importlib.util.spec_from_file_location("conversations", conversations_path)
        conversations = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(conversations)
        
        spec = importlib.util.spec_from_file_location("analytics", analytics_path)
        analytics = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(analytics)
        
        app.include_router(leads.router, prefix="/api/v1", tags=["leads"])
        app.include_router(conversations.router, prefix="/api/v1", tags=["conversations"])
        app.include_router(analytics.router, prefix="/api/v1", tags=["analytics"])
        logger.info("API routes loaded successfully")
    except Exception as e:
        # Если роуты не загрузились, приложение все равно создается
        logger.warning(f"Routes not loaded: {e}. API Gateway will have only health endpoint")

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "ok", "service": "api-gateway"}

    return app

