"""Тесты для API Gateway."""

import pytest
from fastapi.testclient import TestClient
import importlib.util
from pathlib import Path
import sys

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from shared.config.settings import Config


@pytest.fixture
def app():
    """Создать тестовое приложение."""
    # Импортируем API Gateway
    api_gateway_path = project_root / "services" / "api-gateway" / "src" / "main.py"
    spec = importlib.util.spec_from_file_location("api_gateway_main", api_gateway_path)
    api_gateway = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api_gateway)

    config = Config.from_yaml(str(project_root / "config.yaml"))
    return api_gateway.create_app(config)


@pytest.fixture
def client(app):
    """Создать тестовый клиент."""
    return TestClient(app)


def test_health_endpoint(client):
    """Тест health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "api-gateway"


def test_list_leads(client):
    """Тест получения списка лидов."""
    response = client.get("/api/v1/leads")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_conversations(client):
    """Тест получения списка диалогов."""
    response = client.get("/api/v1/conversations")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_metrics(client):
    """Тест получения метрик."""
    response = client.get("/api/v1/analytics/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "total_leads" in data
    assert "total_conversations" in data
    assert "active_leads" in data
    assert "conversion_rate" in data

