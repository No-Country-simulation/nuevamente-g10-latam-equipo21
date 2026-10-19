from pathlib import Path
import re

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
    assert "deploy/oci/*.htpasswd" in gitignore
    assert "deploy/oci/letsencrypt/" in gitignore


def test_http_solo_redirige_y_nunca_solicita_credenciales(compose):
    labels = compose["services"]["frontend"]["labels"]
    assert labels["traefik.http.routers.nuevamente.entrypoints"] == "web"
    assert labels["traefik.http.routers.nuevamente.service"] == "noop@internal"
    assert labels["traefik.http.routers.nuevamente.middlewares"] == "nuevamente-https"
    assert labels["traefik.http.middlewares.nuevamente-https.redirectscheme.scheme"] == "https"
    assert labels["traefik.http.middlewares.nuevamente-https.redirectscheme.port"] == "443"
    assert labels["traefik.http.middlewares.nuevamente-https.redirectscheme.permanent"] == "true"


def test_https_protege_todas_las_rutas_de_streamlit(compose):
    labels = compose["services"]["frontend"]["labels"]
    router = "traefik.http.routers.nuevamente-secure"
    assert labels[f"{router}.entrypoints"] == "websecure"
    assert labels[f"{router}.tls"] == "true"
    assert labels[f"{router}.tls.certresolver"] == "letsencrypt"
    assert labels[f"{router}.service"] == "nuevamente"
    assert labels[f"{router}.middlewares"] == "nuevamente-demo-auth"
    assert labels[f"{router}.rule"] == labels["traefik.http.routers.nuevamente.rule"]
    routers = {key.split(".")[3] for key in labels if key.startswith("traefik.http.routers.")}
    assert routers == {"nuevamente", "nuevamente-secure", "nuevamente-www", "nuevamente-www-secure"}
    assert all("PathPrefix" not in value for key, value in labels.items() if key.endswith(".rule"))


def test_credenciales_solo_en_archivo_privado_del_proxy(compose):
    frontend = compose["services"]["frontend"]
    labels = frontend["labels"]
    auth = "traefik.http.middlewares.nuevamente-demo-auth.basicauth"
    assert labels[f"{auth}.usersfile"] == "/run/secrets/nuevamente-demo/users.htpasswd"
    assert labels[f"{auth}.removeheader"] == "true"
    assert f"{auth}.users" not in labels
    assert not frontend.get("volumes")
    assert not any("PASSWORD" in key or "HTPASSWD" in key for key in frontend["environment"])


def test_alias_www_solo_redirige_al_host_canonico_y_tiene_tls(compose):
    labels = compose["services"]["frontend"]["labels"]
    for name, entrypoint in (("nuevamente-www", "web"), ("nuevamente-www-secure", "websecure")):
        router = f"traefik.http.routers.{name}"
        assert labels[f"{router}.rule"].startswith("Host(`www.${NUEVAMENTE_PUBLIC_HOST:?")
        assert labels[f"{router}.entrypoints"] == entrypoint
        assert labels[f"{router}.service"] == "noop@internal"
        assert labels[f"{router}.middlewares"] == "nuevamente-canonical"
    assert labels["traefik.http.routers.nuevamente-www-secure.tls"] == "true"
    assert labels["traefik.http.routers.nuevamente-www-secure.tls.certresolver"] == "letsencrypt"


@pytest.mark.parametrize("scheme", ["http", "https"])
@pytest.mark.parametrize("path", ["", "_stcore/stream", "media/archivo.pdf?download=1"])
def test_redireccion_www_conserva_ruta_y_query(compose, scheme, path):
    labels = compose["services"]["frontend"]["labels"]
    prefix = "traefik.http.middlewares.nuevamente-canonical.redirectregex"
    match = re.match(labels[f"{prefix}.regex"], f"{scheme}://www.nuevamente.example.com/{path}")
    assert match is not None
    assert match.group(1) == path
    # Compose deja ${1} para la expansión de Traefik, no para el entorno.
    assert labels[f"{prefix}.replacement"].startswith("https://${NUEVAMENTE_PUBLIC_HOST:?")
    assert labels[f"{prefix}.replacement"].endswith("/$${1}")
    assert labels[f"{prefix}.permanent"] == "true"


def test_nm39_no_configura_redireccion_global_ni_dashboard(compose):
    # La configuración de la aplicación no administra el Traefik compartido.
    assert set(compose["services"]) == {"backend", "frontend"}
    labels = compose["services"]["frontend"]["labels"]
    assert not any("entrypoints." in key or "api@internal" in str(value) for key, value in labels.items())
