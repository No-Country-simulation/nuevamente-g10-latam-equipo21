from pathlib import Path

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = PROJECT_ROOT / "backend" / "Dockerfile"
FRONTEND_DOCKERFILE = PROJECT_ROOT / "frontend" / "Dockerfile"
COMPOSE_FILE = PROJECT_ROOT / "deploy" / "oci" / "compose.backend.yml"
GITIGNORE = PROJECT_ROOT / ".gitignore"


@pytest.fixture
def compose():
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))


def test_imagen_del_backend_se_ejecuta_sin_root_y_con_healthcheck():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "USER 10001:10001" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "/api/v1/health" in dockerfile


def test_compose_no_publica_fastapi_y_habilita_reinicio_automatico(compose):
    for service in compose["services"].values():
        assert not service.get("ports")
        assert service["restart"] == "unless-stopped"
        assert service["read_only"] is True
        assert "no-new-privileges:true" in service["security_opt"]
        assert service["cap_drop"] == ["ALL"]
        assert int(service["user"].split(":")[0]) != 0
        assert service["healthcheck"]["test"][0] == "CMD"
    assert "8000" in compose["services"]["backend"]["expose"]


def test_compose_usa_instance_principal_y_red_interna(compose):
    backend = compose["services"]["backend"]
    assert backend["environment"]["OCI_AUTH_MODE"] == "instance_principal"
    assert compose["networks"]["backend_internal"]["internal"] is True
    assert compose["networks"]["backend_internal"]["name"] == "nuevamente-internal"
    for service in compose["services"].values():
        assert "backend_internal" in service["networks"]
    assert "proxy" in backend["networks"]  # Egreso requerido por Gemini/OCI.
    assert backend["labels"]["traefik.enable"] == "false"
    assert not any(key.startswith("traefik.http.") for key in backend["labels"])


def test_imagen_de_streamlit_se_ejecuta_sin_root_y_con_healthcheck():
    dockerfile = FRONTEND_DOCKERFILE.read_text(encoding="utf-8")

    assert "USER 10002:10002" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "/_stcore/health" in dockerfile


def test_streamlit_consumira_fastapi_por_la_red_interna_y_se_publicara_con_traefik(compose):
    frontend = compose["services"]["frontend"]
    assert frontend["environment"]["API_BASE_URL"] == "http://backend:8000/api/v1"
    assert "8501" in frontend["expose"]
    assert frontend["depends_on"]["backend"]["condition"] == "service_healthy"
    labels = frontend["labels"]
    assert labels["traefik.enable"] == "true"
    assert labels["traefik.http.services.nuevamente.loadbalancer.server.port"] == "8501"
    assert labels["traefik.docker.network"] in frontend["networks"]
    rule = labels["traefik.http.routers.nuevamente.rule"]
    assert rule.startswith("Host(`") and rule.endswith("`)")
    assert "${NUEVAMENTE_PUBLIC_HOST:?" in rule
    assert "PathPrefix" not in rule


def test_archivos_runtime_reales_permanecen_fuera_de_git():
    gitignore = GITIGNORE.read_text(encoding="utf-8")

    assert "deploy/oci/runtime.env" in gitignore
    assert "deploy/oci/backend.env" in gitignore
