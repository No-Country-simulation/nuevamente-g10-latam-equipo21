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
- Ambos servicios comparten `nuevamente-internal`. FastAPI también se conecta
  a `proxy` para disponer de egreso hacia Gemini, OCI y los metadatos de
  Instance Principal; esa conexión no publica puertos. Se deshabilita
  explícitamente su descubrimiento por Traefik con `traefik.enable=false`.
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

Este repositorio contiene únicamente la configuración de la aplicación. Los
recursos compartidos se administran en el repositorio público
[infrastructure-as-code](https://github.com/LeandroMelchiori/infrastructure-as-code).
La referencia de implementación local es `oci/docker-platform` y el caso práctico
`oci/case-studies/nuevamente-dev-oci.md` de ese repositorio. Su visibilidad pública
se confirmó el 14 de octubre de 2026. Para reproducir la plataforma sin depender
de esa IaC, los requisitos mínimos son:

1. VM Linux ARM64 con Docker Engine, Compose v2 o posterior y OCI CLI instalada.
   La instancia consultada el 12 de octubre de 2026 usa `VM.Standard.A1.Flex`,
   **1 OCPU y 6 GB de RAM**, con un boot volume de **50 GB** confirmado mediante
   la API de OCI. Construir las imágenes en la VM conserva la arquitectura ARM64.
2. Subnet con salida a Internet para Gemini, OCI y las descargas de imágenes.
   Las reglas de entrada de NuevaMente son TCP **80** público y TCP **22** solo
   desde la IP administrativa `/32`; **8000 y 8501 no se abren**. Aplicar la misma
   restricción en NSG, security lists y firewall del sistema operativo.
3. Crear la red `proxy` con `sudo docker network create proxy` si no existe.
   Traefik debe conectarse a ella, publicar `80:80`, tener el entrypoint `web`,
   el proveedor Docker y `providers.docker.exposedByDefault=false`. No publicar
   su dashboard. El Compose de la aplicación crea `nuevamente-internal`.
4. Crear un Dynamic Group limitado a la instancia, con regla
   `instance.id = '<OCID_INSTANCIA>'`. Conceder lectura de `secret-bundles` en el
   compartimento del secreto, lectura del bucket y operaciones de inspección,
   lectura, creación y sobrescritura de objetos limitadas al bucket de contenidos.
   No conceder borrado desde la aplicación. El administrador debe configurar las
   políticas en los compartimentos correspondientes antes de iniciar el backend.
5. Crear el secreto `nuevamente-gemini-api-key` en Vault y el bucket privado de
   contenidos, y preparar `runtime.env` mediante los pasos siguientes.

La VM actualmente comparte Traefik con otra aplicación. NuevaMente usa una regla
`Host` configurable: `NUEVAMENTE_PUBLIC_HOST` debe ser su IP pública o dominio,
sin `http://`, ruta ni puerto. Esto evita que NuevaMente capture peticiones
dirigidas a otros hosts. Una regla para el mismo host y ruta en otra aplicación
requiere resolver esa asignación antes de desplegar.

### Always Free y evidencia de costos

La consulta de solo lectura a OCI del 12 de octubre de 2026 confirmó:

- `sa-saopaulo-1` es la región principal y la única región suscrita.
- Una instancia no terminada: `VM.Standard.A1.Flex`, 1 OCPU y 6 GB de RAM.
- Dos volúmenes disponibles de 47 y 50 GB: 97 GB combinados. El volumen de la
  instancia utilizada por NuevaMente es el de 50 GB.
- Los cuatro buckets regionales reportan aproximadamente 13,8 MB en total;
  el bucket de NuevaMente reporta aproximadamente 13,3 MB.
- Usage API / Cost Analysis, del 1 de octubre al 12 de octubre a las 00:00 UTC
  (fin exclusivo), reporta USD 0 en las filas con importe de Compute, Block
  Storage, Object Storage, Virtual Cloud Network, Logging y Telemetry. Existe
  además una fila de Object Storage sin importe: no se interpreta como cero.

Este dimensionamiento está dentro de las cuotas publicadas de
[Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
para Compute y almacenamiento de volúmenes y objetos. No se crearon recursos
OCI adicionales para esta validación. Las cuotas son compartidas por el tenancy
y los reportes de costos pueden tener demora: la consulta no garantiza cargos
futuros nulos ni cubre el consumo posterior al período indicado. La cuota de
Gemini es independiente de Always Free de OCI.

No habilitar componentes adicionales para esta entrega. TLS, dominio propio y
CI/CD automatizado quedan fuera del alcance de NM-D2.

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
    --vault-id OCID_DEL_VAULT \
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
desde OCI y `OCID_DEL_VAULT` por el identificador del Vault que contiene el secreto.
Configurar también la región de OCI CLI para ese Vault. El archivo no debe
copiarse al repositorio ni mostrarse en logs. El bloque crea un archivo nuevo:
no ejecutarlo sobre un `runtime.env` existente sin preservar su configuración.

El modelo `gemini-3.1-flash-lite` y el timeout de 60 segundos son overrides del
entorno desplegado, confirmados por consulta el 12 de octubre de 2026. No son los
valores predeterminados del código. No se ha confirmado que la elección responda
a una limitación de cuota. Para cerrar NM-D2 se mantiene el modelo porque la
generación y persistencia del release fueron validadas con él. Según el
[calendario oficial de Gemini](https://ai.google.dev/gemini-api/docs/deprecations/)
consultado el 12 de octubre de 2026, continúa disponible y su fecha más temprana
de retirada es el 7 de mayo de 2027. La actualización se evaluará por separado
mediante pruebas de calidad, fidelidad, tiempos de respuesta y cuotas.

Se mantiene el timeout de 60 segundos utilizado en la validación del despliegue.
Su suficiencia para documentos largos queda pendiente de pruebas: una llamada
al proveedor puede exceder ese límite y hacer fallar la generación.

NM-25 exige `GEMINI_API_KEY` y `OCI_NAMESPACE` no vacíos cuando se usa el pipeline
real. Compose fija `USE_MOCK_LLM=false` y `OCI_AUTH_MODE=instance_principal`;
no se requieren claves OCI de usuario. NM-22 y NM-33 utilizan por defecto
`RETRIEVAL_MAX_VENTANAS=10`, `RETRIEVAL_VENTANA_CHARS=2000`,
`RETRIEVAL_VENTANA_CANDIDATOS=8`, `RETRIEVAL_FRAGMENTOS_POR_VENTANA=2` y
`RETRIEVAL_MAX_CONTEXT_TOKENS=6000`. Se pueden declarar en `runtime.env` si se
desea cambiarlos, sin copiar todo el `.env.example` local.

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
  NUEVAMENTE_PUBLIC_HOST=IP_PUBLICA_O_DOMINIO \
  NUEVAMENTE_BACKEND_ENV_FILE=/etc/docker-platform/apps/nuevamente/runtime.env \
  docker compose -f compose.backend.yml up -d --remove-orphans
```

Compose espera a que FastAPI esté saludable antes de iniciar Streamlit.

## Validaciones

### Regresión local antes del despliegue

Con las dependencias de backend y frontend instaladas en el entorno de pruebas:

```bash
(cd backend && USE_MOCK_LLM=true RUN_OCI_INTEGRATION=0 python -m pytest -q)
(cd frontend && python -m pytest tests -q)
```

La revisión local del 12 de octubre de 2026, después de incorporar `develop`
(`c4f92ad`), obtuvo **215 passed, 1 skipped** en backend y **55 passed** en
frontend, con Python 3.12. La prueba omitida es la integración real con OCI.
También se validó el Compose con un host de ejemplo y se comprobó que rechaza
la configuración cuando falta `NUEVAMENTE_PUBLIC_HOST`. Estos controles no
construyen imágenes ni sustituyen las pruebas del release en la VM con Python 3.11.

### Servicios en la VM

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

Desde una computadora externa a la VM, comprobar primero que la interfaz
responde y que el acceso directo a FastAPI falla:

```bash
curl --fail --max-time 10 http://IP_PUBLICA/_stcore/health
curl --connect-timeout 5 --max-time 10 http://IP_PUBLICA:8000/api/v1/health
```

El primero debe devolver `ok`; el segundo debe fallar por conexión rechazada o
timeout. Un timeout aislado no demuestra aislamiento si la interfaz tampoco
responde. Las rutas `/docs` y `/api/v1/health` del host público no deben entregar
Swagger ni el JSON de FastAPI (Streamlit puede devolver su propio HTML).

### Reinicio automático

En una ventana coordinada sin generaciones activas, simular la caída de cada
proceso por separado. Para el backend:

```bash
sudo docker inspect --format '{{.RestartCount}} {{.State.StartedAt}}' nuevamente-backend-1
sudo docker exec nuevamente-backend-1 python -c '
import os, signal
from pathlib import Path
children = Path("/proc/1/task/1/children").read_text().split()
assert len(children) == 1, "Abortado: se esperaba un único proceso hijo del init"
pid = int(children[0])
command = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
assert any(b"uvicorn" in arg or arg == b"streamlit" for arg in command), "Abortado: proceso inesperado"
os.kill(pid, signal.SIGKILL)
'
sudo docker ps --filter name=nuevamente-backend-1
sudo docker inspect --format '{{.RestartCount}} {{.State.StartedAt}} {{.State.Health.Status}}' nuevamente-backend-1
```

Esperar a que vuelva a `healthy`, comprobar el incremento de `RestartCount` y
repetir con `nuevamente-frontend-1`. Después verificar la URL pública y una
generación. El procedimiento termina únicamente el proceso de la aplicación,
hijo del init que configura `init: true`, desde dentro del contenedor. Si cambia
esa estructura, aborta antes de enviar la señal. No usar `docker stop` ni
`docker kill`: Docker puede registrar una parada manual y suprimir la política
de reinicio. Ver la [política de reinicio de Docker](https://docs.docker.com/engine/containers/start-containers-automatically/).

Se verificó la recuperación ante la caída de los procesos de la aplicación.
No se probó la recuperación tras reiniciar el daemon de Docker ni la VM.
Esas pruebas requieren una ventana coordinada porque la instancia aloja otra
aplicación.

### Evidencia de validación del release de NM-D2

El 12 de octubre de 2026 se desplegó y validó el release
`c5cc1be990b8b98c723e70824bd78741d2821c5f`, construido en la VM desde un archivo
de los archivos versionados de esa revisión. No se copiaron archivos `.env` ni
credenciales del equipo local; se conservó el `runtime.env` existente.

Ese release ya incluía la regla `Host` parametrizada con
`NUEVAMENTE_PUBLIC_HOST`. La comparación con `db40875`, revisado en el PR #60,
solo muestra cambios posteriores en esta guía: no cambió el código de la
aplicación, los Dockerfiles ni el Compose. La evidencia siguiente corresponde
a ese release y no representa una nueva comprobación del estado de la VM.

Imágenes utilizadas:

| Servicio | Tag | ID de imagen |
|---|---|---|
| Backend | `nuevamente-backend:nm-d2-c5cc1be` | `sha256:92d6326c9e7b4becd2d2777cd3c8f54b3ba6baafd8e1f4814601b36da1ccadca` |
| Frontend | `nuevamente-frontend:nm-d2-c5cc1be` | `sha256:4221ca3b082f62e49ec2ef98e6c15f54589a1e2b3d8488c07b700e1a8e922b6b` |

| Comprobación | Resultado |
|---|---|
| Backend y frontend | Ambos `healthy`; etiqueta de revisión completa coincidente con el release. |
| `docker port nuevamente-backend-1` | Salida vacía. |
| Puertos publicados de ambos contenedores | `PortBindings={}`. |
| Recuperación automática | Se terminó el proceso hijo de cada servicio por separado. Cada `RestartCount` pasó de 0 a 1, manteniendo el ID del contenedor y recuperando `healthy`, sin reinicio manual. |
| Configuración del backend | `USE_MOCK_LLM=false`, autenticación Instance Principal y modelo real `gemini-3.1-flash-lite`. |
| Portada pública | HTTP 200 desde fuera de la VM, con la regla `Host` de `NUEVAMENTE_PUBLIC_HOST` aplicada, tras la recuperación. Durante la caída simulada hubo indisponibilidad transitoria, esperable en una sola réplica. |
| Acceso externo directo a 8000 y 8501 | Timeout de conexión, sin respuesta HTTP. |
| Routing | Frontend con regla `Host` de NuevaMente; backend sin router Traefik. |
| Persistencia vectorial | Se conservó el volumen `nuevamente-chroma-data` en `/app/chroma_db`. |
| Servicios compartidos | Traefik y la otra aplicación conservaron sus contenedores y hora de inicio. |

La API de OCI confirmó una security list sin reglas de ingreso y un NSG con
SSH limitado a `/32`, HTTP 80 y HTTPS 443 públicos. El 443 pertenece a la
plataforma compartida y no se modificó. `firewalld` reportó servicios
`dhcpv6-client http ssh`, sin puertos adicionales configurados en la zona
predeterminada. La comprobación externa complementa esta inspección.

Durante el trabajo cambió la IP pública del operador. Con autorización se
actualizó únicamente el origen `/32` de SSH mediante Terraform: plan y apply
con **0 added, 1 changed, 0 destroyed**, y plan posterior sin cambios. No se
ampliaron permisos IAM ni se modificaron otros recursos.

Se conservaron el release y las imágenes anteriores para rollback. Después de
construir ambas imágenes quedaron aproximadamente **2,8 GB libres de 30 GB** en
el filesystem raíz. Antes de acumular más builds, revisar el espacio y acordar
una limpieza controlada; esta validación no eliminó imágenes ni volúmenes.

### Prueba end-to-end y persistencia en Object Storage

La validación del release `c5cc1be` se realizó con `AppTest` dentro del
contenedor frontend, ejecutando `/app/app.py` sin mocks: carga de Markdown
sintético de 1112 bytes, selección predeterminada Principiante/Tutorial y envío
del formulario contra el backend real. La generación tardó **35,97 segundos**,
devolvió tres pasos y `status_upload=completado`. Se verificaron mediante
Instance Principal los dos objetos exactos:

```text
originales/6d4f3140e9c6006c-nm-d2-validacion-c5cc1be.md
contenido-nm-d2-validacion-c5cc1be-principiante-tutorial-419fa2c7a531.json
```

El original descargado coincidió con su SHA-256 y el JSON almacenado validó
contra `OutputSchema`, con título coincidente y carga completada. Esto verifica
el recorrido funcional frontend → API → Gemini → OCI. `AppTest` no atraviesa
Traefik: el acceso público se comprobó por HTTP por separado, con resultado 200
y la regla `Host` aplicada. No se realizó una generación completa desde el
navegador ni una prueba de documentos largos. Ambos artefactos sintéticos se
conservaron como evidencia.

Con `USE_MOCK_LLM=false`, cargar un documento admitido desde la URL pública de
Streamlit y solicitar una generación. La interfaz debe confirmar que la
adaptación se completó correctamente.

Desde la instancia se puede comprobar la persistencia mediante Instance
Principal, sin utilizar credenciales OCI estáticas:

```bash
oci os object list \
  --auth instance_principal \
  --bucket-name nuevamente-contenidos-educativos \
  --all \
  --query 'data[].{nombre:name,creado:"time-created",tamano:size}' \
  --output table
```

### Evidencia histórica: 5 de octubre de 2026

Esta prueba es anterior a las integraciones de NM-22, NM-24 y NM-25. Se conserva
como antecedente y no sustituye la validación del release `c5cc1be` descrita arriba.
Las capturas de la descripción inicial del PR #60 corresponden a esta prueba.

La validación end-to-end realizada el 5 de octubre de 2026 con el documento
`Learn Python in Y Minutes.pdf` confirmó la persistencia de ambos artefactos:

```text
originales/1277c3810f7d1324-learn-python-in-y-minutes.pdf
contenido-learn-python-in-y-minutes-lider-tecnico-arquitecto-resumen-ejecutivo-aa4ad01391c5.json
```

El documento original y el paquete educativo generado deben aparecer en el
mismo bucket. Una respuesta exitosa de la interfaz sin el JSON correspondiente
no se considera una validación completa del despliegue.

## Actualización del frontend

Cuando se integre un cambio del frontend no es necesario recrear la infraestructura
ni el backend:

```bash
sudo docker build \
  --tag nuevamente-frontend:<nueva-version> \
  frontend

cd deploy/oci

sudo env \
  NUEVAMENTE_BACKEND_IMAGE=nuevamente-backend:<version-backend-actual> \
  NUEVAMENTE_FRONTEND_IMAGE=nuevamente-frontend:<nueva-version> \
  NUEVAMENTE_PUBLIC_HOST=IP_PUBLICA_O_DOMINIO \
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

El único puerto público de NuevaMente es HTTP 80 a través de Traefik. La VM
compartida puede tener reglas adicionales para otras aplicaciones; no se deben
cerrar ni modificar como parte de NM-D2. Revisar las reglas efectivas del NSG,
security lists y firewall antes de afirmar que la VM completa solo expone 80.

## Limitaciones de la demo

La URL de NuevaMente usa HTTP y no exige autenticación; cualquier visitante puede
consumir cuota de Gemini y almacenar objetos. La protección del acceso y limpieza
administrativa se siguen en NM-39. No cargar documentos privados o credenciales.

La VM comparte Traefik, CPU, memoria y disco con otra aplicación; la carga o el
mantenimiento de la plataforma pueden afectar a ambas. Las cuotas Always Free
de OCI se comparten en el tenancy. No se ha confirmado que las dos aplicaciones
compartan también el proyecto o la cuota de Gemini.

Una prueba con documento corto verifica el despliegue, pero no demuestra el
comportamiento con documentos largos ni sustituye las demos de NM-17. Los límites
de embeddings y latencia del proveedor deben registrarse por separado si aparecen.
