import pytest
from pydantic import ValidationError
from app.core.config import Settings


def test_missing_environment_raises_validation_error(monkeypatch):
    """
    Verifica que la ausencia de la variable obligatoria ENVIRONMENT genera un ValidationError.
    """
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    errors = exc_info.value.errors()
    assert any(err["loc"] == ("ENVIRONMENT",) for err in errors)


def test_environment_loaded_from_env_var(monkeypatch):
    """
    Verifica que la variable ENVIRONMENT se cargue correctamente desde variables de entorno.
    """
    monkeypatch.setenv("ENVIRONMENT", "staging")
    settings = Settings(_env_file=None)
    assert settings.ENVIRONMENT == "staging"


def test_environment_loaded_from_dotenv_file(tmp_path, monkeypatch):
    """
    Verifica que la configuración se cargue correctamente desde un archivo .env.
    """
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("ENVIRONMENT=production\nPROJECT_NAME=NuevaMente Prod\n", encoding="utf-8")

    settings = Settings(_env_file=str(env_file))
    assert settings.ENVIRONMENT == "production"
    assert settings.PROJECT_NAME == "NuevaMente Prod"


def test_cors_origins_json_parsing():
    """
    Verifica la deserialización de CORS_ORIGINS desde string JSON y la captura de json.JSONDecodeError.
    """
    # Formato JSON válido
    settings_valid = Settings(
        ENVIRONMENT="test",
        CORS_ORIGINS='["http://localhost:3000", "http://localhost:8501"]',
        _env_file=None,
    )
    assert settings_valid.CORS_ORIGINS == ["http://localhost:3000", "http://localhost:8501"]

    # Formato JSON malformado (debe capturar JSONDecodeError y aplicar fallback por comas)
    settings_fallback = Settings(
        ENVIRONMENT="test",
        CORS_ORIGINS='["http://localhost:3000", http://localhost:8501',
        _env_file=None,
    )
    assert isinstance(settings_fallback.CORS_ORIGINS, list)
