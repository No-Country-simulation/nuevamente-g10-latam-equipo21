from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)


def test_root_endpoint():
    """
    Verifica que el endpoint raíz responda 200 y contenga la bienvenida y enlaces útiles.
    """
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert settings.PROJECT_NAME in data["message"]
    assert "docs" in data
    assert "health" in data


def test_health_check_endpoint():
    """
    Verifica que el endpoint /api/v1/health responda 200 con el estado healthy.
    """
    response = client.get(f"{settings.API_V1_STR}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == settings.PROJECT_NAME
    assert data["version"] == settings.VERSION
    assert data["environment"] == settings.ENVIRONMENT
