# Despliegue de NuevaMente en OCI

Esta guía documenta el despliegue actual de NuevaMente sobre una instancia OCI
Compute de desarrollo. El backend FastAPI y el frontend Streamlit se ejecutan
como contenedores independientes administrados con Docker Compose.

## Arquitectura desplegada

```text
Internet
   |
   v
Traefik :80
   |
   v
Streamlit :8501
   |
   | red Docker nuevamente-internal
   v
FastAPI :8000
   |
   +--> Google Gemini
   +--> OCI Object Storage
```

- Solo Streamlit se publica mediante Traefik.
- FastAPI utiliza `expose` y no publica el puerto 8000 en la VM.
- Streamlit consume la API mediante `http://backend:8000/api/v1`.
- FastAPI se autentica contra OCI mediante Instance Principal.
- La clave de Gemini se almacena en OCI Vault y se materializa únicamente en
  un archivo `runtime.env` protegido dentro de la VM.
- El entorno actual es de desarrollo y utiliza HTTP. HTTPS queda pendiente de
  disponer de un dominio del equipo.

## Recursos previos

La plataforma OCI debe proporcionar:

- una instancia Compute con Docker y Docker Compose;
- una red Docker externa llamada `proxy`;
- Traefik conectado a esa red;
- el Dynamic Group y las políticas IAM de la instancia;
- acceso de Instance Principal al secreto de Gemini y al bucket privado
  `nuevamente-contenidos-educativos`;
- el archivo root-owned
  `/etc/docker-platform/apps/nuevamente/runtime.env` con permisos `0600`.

Los recursos compartidos se administran desde el repositorio de IaC. Este
repositorio contiene únicamente la configuración de la aplicación.

## Secretos en la VM

El contenedor no recibe credenciales OCI estáticas. La VM consulta Vault con su
Instance Principal y genera el archivo de entorno sin imprimir el secreto:

```bash
sudo install -d -o root -g root -m 0750 \
  /etc/docker-platform/apps/nuevamente

sudo bash -c '
  set -euo pipefail
  umask 077
  printf "GEMINI_API_KEY=" > /etc/docker-platform/apps/nuevamente/runtime.env
  oci secrets secret-bundle get-secret-bundle-by-name \
    --auth instance_principal \
    --secret-name nuevamente-gemini-api-key \
    --stage CURRENT \
    --query "data.\"secret-bundle-content\".content" \
    --raw-output \
    | base64 --decode >> /etc/docker-platform/apps/nuevamente/runtime.env
  printf "\nGEMINI_MODEL_NAME=gemini-3.1-flash-lite\n" \
    >> /etc/docker-platform/apps/nuevamente/runtime.env
  printf "GEMINI_EMBEDDING_MODEL_NAME=gemini-embedding-001\n" \
    >> /etc/docker-platform/apps/nuevamente/runtime.env
  printf "GEMINI_TIMEOUT_SECONDS=60\n" \
    >> /etc/docker-platform/apps/nuevamente/runtime.env
  printf "OCI_NAMESPACE=TU_NAMESPACE\n" \
    >> /etc/docker-platform/apps/nuevamente/runtime.env
  printf "OCI_BUCKET_NAME=nuevamente-contenidos-educativos\n" \
    >> /etc/docker-platform/apps/nuevamente/runtime.env
  printf "OCI_REGION=sa-saopaulo-1\n" \
    >> /etc/docker-platform/apps/nuevamente/runtime.env
  chmod 600 /etc/docker-platform/apps/nuevamente/runtime.env
'
```

`TU_NAMESPACE` debe reemplazarse por el namespace de Object Storage obtenido
desde OCI. El archivo no debe copiarse al repositorio ni mostrarse en logs.

## Construcción de imágenes

Desde la raíz de un release del proyecto en la VM:

```bash
sudo docker build \
  --tag nuevamente-backend:<version> \
  backend

sudo docker build \
  --tag nuevamente-frontend:<version> \
  frontend
```

Las dos imágenes se ejecutan con usuarios numéricos sin privilegios, filesystem
de solo lectura, capacidades eliminadas, límites de recursos y health checks.

## Inicio de los servicios

```bash
cd deploy/oci

sudo env \
  NUEVAMENTE_BACKEND_IMAGE=nuevamente-backend:<version-backend> \
  NUEVAMENTE_FRONTEND_IMAGE=nuevamente-frontend:<version-frontend> \
  NUEVAMENTE_BACKEND_ENV_FILE=/etc/docker-platform/apps/nuevamente/runtime.env \
  docker compose -f compose.backend.yml up -d --remove-orphans
```

Compose espera a que FastAPI esté saludable antes de iniciar Streamlit.

## Validaciones

Estado de los contenedores:

```bash
sudo docker ps --format '{{.Names}} | {{.Image}} | {{.Status}}'
```

Comunicación interna desde Streamlit hacia FastAPI:

```bash
sudo docker exec nuevamente-frontend-1 python -c \
  "import urllib.request; print(urllib.request.urlopen(
  'http://backend:8000/api/v1/health', timeout=5).read().decode())"
```

Health check público de Streamlit:

```bash
curl --fail http://IP_PUBLICA/_stcore/health
```

La respuesta esperada es `ok`. La portada debe responder HTTP 200 en:

```text
http://IP_PUBLICA/
```

FastAPI debe seguir sin puertos publicados:

```bash
sudo docker port nuevamente-backend-1
```

El comando no debe devolver ninguna asignación de puertos.

## Actualización del frontend

Cuando se integre un cambio como NM-14 no es necesario recrear la infraestructura
ni el backend:

```bash
sudo docker build \
  --tag nuevamente-frontend:<nueva-version> \
  frontend

cd deploy/oci

sudo env \
  NUEVAMENTE_BACKEND_IMAGE=nuevamente-backend:<version-backend-actual> \
  NUEVAMENTE_FRONTEND_IMAGE=nuevamente-frontend:<nueva-version> \
  NUEVAMENTE_BACKEND_ENV_FILE=/etc/docker-platform/apps/nuevamente/runtime.env \
  docker compose -f compose.backend.yml up -d
```

Después de la actualización deben repetirse el health check público y una prueba
funcional de generación contra el backend real.

## Acceso administrativo

SSH permanece restringido a una única dirección IPv4 `/32`. Si cambia la IP del
operador, primero se debe ejecutar un `terraform plan` en el repositorio IaC y
comprobar que el resultado sea únicamente una actualización en sitio de la regla
SSH, con `0 to destroy`, antes de aplicar el cambio.
