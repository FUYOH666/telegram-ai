"""FastAPI приложение для REST API Gateway."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from shared.config.settings import Config

logger = logging.getLogger(__name__)

# Prometheus метрики
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)


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

    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint."""
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    # Middleware для сбора метрик
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        """Middleware для сбора метрик Prometheus."""
        start_time = time.time()
        
        # Обработка запроса
        response = await call_next(request)
        
        # Вычисление длительности
        duration = time.time() - start_time
        
        # Получение пути endpoint (без query параметров)
        endpoint = request.url.path
        
        # Сбор метрик
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code,
        ).inc()
        
        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=endpoint,
        ).observe(duration)
        
        return response

    return app

