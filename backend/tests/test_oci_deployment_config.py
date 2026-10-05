from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = PROJECT_ROOT / "backend" / "Dockerfile"
FRONTEND_DOCKERFILE = PROJECT_ROOT / "frontend" / "Dockerfile"
COMPOSE_FILE = PROJECT_ROOT / "deploy" / "oci" / "compose.backend.yml"
GITIGNORE = PROJECT_ROOT / ".gitignore"


def test_imagen_del_backend_se_ejecuta_sin_root_y_con_healthcheck():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "USER 10001:10001" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "/api/v1/health" in dockerfile


def test_compose_no_publica_fastapi_y_habilita_reinicio_automatico():
    compose = COMPOSE_FILE.read_text(encoding="utf-8")

    assert "restart: unless-stopped" in compose
    assert "read_only: true" in compose
    assert "no-new-privileges:true" in compose
    assert "cap_drop:\n      - ALL" in compose
    assert "\n    ports:" not in compose
    assert 'expose:\n      - "8000"' in compose


def test_compose_usa_instance_principal_y_red_interna():
    compose = COMPOSE_FILE.read_text(encoding="utf-8")

    assert "OCI_AUTH_MODE: instance_principal" in compose
    assert "backend_internal:" in compose
    assert "internal: true" in compose
    assert "name: nuevamente-internal" in compose


def test_imagen_de_streamlit_se_ejecuta_sin_root_y_con_healthcheck():
    dockerfile = FRONTEND_DOCKERFILE.read_text(encoding="utf-8")

    assert "USER 10002:10002" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "/_stcore/health" in dockerfile


def test_streamlit_consumira_fastapi_por_la_red_interna_y_se_publicara_con_traefik():
    compose = COMPOSE_FILE.read_text(encoding="utf-8")

    assert "API_BASE_URL: http://backend:8000/api/v1" in compose
    assert 'expose:\n      - "8501"' in compose
    assert "traefik.enable: \"true\"" in compose
    assert "traefik.http.services.nuevamente.loadbalancer.server.port: \"8501\"" in compose


def test_archivos_runtime_reales_permanecen_fuera_de_git():
    gitignore = GITIGNORE.read_text(encoding="utf-8")

    assert "deploy/oci/runtime.env" in gitignore
    assert "deploy/oci/backend.env" in gitignore
