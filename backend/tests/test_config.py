import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_missing_environment_raises_validation_error(monkeypatch):
    """
    Verifica que la ausencia de la variable obligatoria ENVIRONMENT
    genera un ValidationError.
    """
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(
            USE_MOCK_LLM=True,
            _env_file=None,
        )

    errors = exc_info.value.errors()
    assert any(err["loc"] == ("ENVIRONMENT",) for err in errors)


def test_environment_loaded_from_env_var(monkeypatch):
    """
    Verifica que la variable ENVIRONMENT se cargue correctamente
    desde variables de entorno.
    """
    monkeypatch.setenv("ENVIRONMENT", "staging")

    settings = Settings(
        USE_MOCK_LLM=True,
        _env_file=None,
    )

    assert settings.ENVIRONMENT == "staging"


def test_environment_loaded_from_dotenv_file(tmp_path, monkeypatch):
    """
    Verifica que la configuración se cargue correctamente
    desde un archivo .env.
    """
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "ENVIRONMENT=production\n"
        "PROJECT_NAME=NuevaMente Prod\n"
        "USE_MOCK_LLM=true\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=str(env_file))

    assert settings.ENVIRONMENT == "production"
    assert settings.PROJECT_NAME == "NuevaMente Prod"


def test_cors_origins_json_parsing():
    """
    Verifica la deserialización de CORS_ORIGINS desde string JSON
    y la captura de json.JSONDecodeError.
    """
    settings_valid = Settings(
        ENVIRONMENT="test",
        USE_MOCK_LLM=True,
        CORS_ORIGINS='["http://localhost:3000", "http://localhost:8501"]',
        _env_file=None,
    )

    assert settings_valid.CORS_ORIGINS == [
        "http://localhost:3000",
        "http://localhost:8501",
    ]

    settings_fallback = Settings(
        ENVIRONMENT="test",
        USE_MOCK_LLM=True,
        CORS_ORIGINS='["http://localhost:3000", http://localhost:8501',
        _env_file=None,
    )

    assert isinstance(settings_fallback.CORS_ORIGINS, list)


# ---------------------------------------------------------------------------
# NM-25 - Validación de configuración al arrancar
# ---------------------------------------------------------------------------

def test_real_mode_requires_gemini_api_key(monkeypatch):
    """
    Con USE_MOCK_LLM=False la aplicación debe rechazar
    una configuración sin GEMINI_API_KEY.
    """
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OCI_NAMESPACE", raising=False)

    with pytest.raises(ValidationError, match="GEMINI_API_KEY"):
        Settings(
            ENVIRONMENT="test",
            USE_MOCK_LLM=False,
            GEMINI_API_KEY="",
            OCI_NAMESPACE="test-namespace",
            _env_file=None,
        )


def test_real_mode_requires_oci_namespace(monkeypatch):
    """
    Con USE_MOCK_LLM=False la aplicación debe rechazar
    una configuración sin OCI_NAMESPACE.
    """
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OCI_NAMESPACE", raising=False)

    with pytest.raises(ValidationError, match="OCI_NAMESPACE"):
        Settings(
            ENVIRONMENT="test",
            USE_MOCK_LLM=False,
            GEMINI_API_KEY="test-gemini-key",
            OCI_NAMESPACE="",
            _env_file=None,
        )


def test_real_mode_reports_all_missing_required_variables(monkeypatch):
    """
    Si faltan ambas variables, el mensaje de error debe nombrar
    GEMINI_API_KEY y OCI_NAMESPACE.
    """
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OCI_NAMESPACE", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="test",
            USE_MOCK_LLM=False,
            GEMINI_API_KEY="",
            OCI_NAMESPACE="",
            _env_file=None,
        )

    message = str(exc_info.value)

    assert "GEMINI_API_KEY" in message
    assert "OCI_NAMESPACE" in message


def test_mock_mode_allows_missing_real_service_credentials(monkeypatch):
    """
    Con USE_MOCK_LLM=True se permite iniciar sin credenciales
    de Gemini ni namespace de OCI.
    """
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OCI_NAMESPACE", raising=False)

    settings = Settings(
        ENVIRONMENT="test",
        USE_MOCK_LLM=True,
        GEMINI_API_KEY="",
        OCI_NAMESPACE="",
        _env_file=None,
    )

    assert settings.USE_MOCK_LLM is True
    assert settings.GEMINI_API_KEY == ""
    assert settings.OCI_NAMESPACE == ""


def test_oci_auth_mode_defaults_to_instance_principal():
    """
    Mantiene instance_principal como valor por defecto
    para no romper la configuración de la VM de NM-D2.
    """
    settings = Settings(
        ENVIRONMENT="test",
        USE_MOCK_LLM=True,
        _env_file=None,
    )

    assert settings.OCI_AUTH_MODE == "instance_principal"