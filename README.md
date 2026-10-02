# NuevaMente

Sistema inteligente de adaptacion y generacion de contenido educativo desarrollado para el Hackathon ONE G10 de Oracle Next Education y Alura.

NuevaMente transforma documentacion tecnica en materiales didacticos adaptados al perfil de quien aprende, el formato deseado, el sector de aplicacion y el nivel de detalle. El proyecto combina recuperacion semantica (RAG), Google Gemini, evaluacion de fidelidad y persistencia en OCI Object Storage.

## Problema que resuelve

La documentacion tecnica suele asumir conocimientos previos y presentar el mismo contenido a publicos con necesidades distintas. NuevaMente permite convertir una fuente tecnica en tutoriales, flashcards, cuestionarios, resumenes ejecutivos o guiones de clase, manteniendo el contenido anclado al documento original.

El caso de uso principal pertenece al sector **EdTech**, con contextualizacion adicional para Fintech, Salud, Ecommerce o un dominio general.

## Funcionalidades

- Extraccion y normalizacion de documentos PDF, Markdown y TXT.
- Segmentacion, embeddings e indexacion local con ChromaDB.
- Recuperacion de contexto relevante antes de generar contenido.
- Adaptacion mediante Google Gemini con salida estructurada.
- Flujo multi-agente experimental con Investigador RAG, Redactor Pedagogico y Critico/Revisor.
- Cinco formatos pedagogicos: Tutorial, Flashcards, Quiz, Resumen Ejecutivo y Guion de Clase.
- Evaluacion de fidelidad y claridad pedagogica.
- Metadatos de aprendizaje y estimacion del tiempo de estudio.
- Persistencia de documentos y resultados en OCI Object Storage.
- API REST con FastAPI y contratos validados mediante Pydantic v2.

## Arquitectura

```mermaid
flowchart TD
    A[Documento PDF / MD / TXT] --> B[Extraccion y normalizacion]
    B --> C[Chunking]
    C --> D[Embeddings]
    D --> E[(ChromaDB)]
    E --> F[Retrieval semantico]
    F --> G[Orquestacion lineal del MVP]
    G --> H[Google Gemini]
    H --> I[Evaluacion de fidelidad]
    F -. flujo multi-agente disponible .-> N1[Investigador RAG]
    N1 --> N2[Redactor Pedagogico]
    N2 --> N3[Critico / Revisor]
    N3 -- score bajo y quedan reintentos --> N2
    N3 --> J
    I --> J[Metadatos pedagogicos]
    J --> K[Respuesta JSON]
    B --> L[(OCI Object Storage)]
    K --> L
    K --> M[Cliente / Streamlit]
```

El backend mantiene separadas las capas HTTP, los contratos y la logica de negocio:

```text
endpoint -> servicio de adaptacion -> RAG / Gemini / evaluacion / metadatos
                                \-> servicio de almacenamiento -> OCI
```

El flujo lineal es el recorrido principal del endpoint del MVP. El servicio multi-agente implementado con LangGraph reutiliza retrieval, generacion y evaluacion para permitir ciclos de revision controlados, pero todavia se ejecuta mediante un script de comparacion y no esta seleccionable desde el endpoint integral.

La descripcion completa y los contratos de datos se encuentran en [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Tecnologias principales

| Componente | Tecnologia |
|---|---|
| API | FastAPI + Python 3.11+ |
| Validacion | Pydantic v2 |
| LLM y embeddings | Google Gemini |
| Orquestacion | LangChain (endpoint del MVP) + LangGraph (flujo experimental) |
| Base vectorial | ChromaDB |
| Persistencia | OCI Object Storage |
| Pruebas | Pytest |

### Estado actual de los componentes

| Componente | Estado |
|---|---|
| Backend FastAPI | Implementado: ingesta, RAG, generacion, fidelidad, metadatos y persistencia OCI. |
| Pipeline lineal | Integrado en `POST /api/v1/adaptar-contenido`. |
| Flujo multi-agente | Implementado y probado mediante script; pendiente de exponer desde el endpoint. |
| Frontend Streamlit | Definido por la arquitectura; todavia no esta implementado en `develop`. |
| Despliegue OCI Compute | Infraestructura base preparada; despliegue completo de los servicios pendiente. |

## Estructura del repositorio

```text
backend/
├── app/
│   ├── api/v1/endpoints/   # Rutas HTTP
│   ├── core/               # Configuracion global
│   ├── schemas/            # Contratos Pydantic
│   ├── services/           # Ingesta, RAG, Gemini y reglas de negocio
│   └── main.py             # Aplicacion FastAPI
├── scripts/                # Utilidades y benchmarks
├── tests/                  # Pruebas automatizadas
├── .env.example            # Plantilla de configuracion sin secretos
└── requirements.txt        # Dependencias fijadas
docs/
└── ARCHITECTURE.md         # Arquitectura y contratos oficiales
```

## Requisitos

- Python 3.11 o superior.
- Git.
- Una API key de Google Gemini para probar el pipeline real.
- Una cuenta de OCI con Object Storage para probar la persistencia real.

El modo mock permite probar el contrato de adaptacion sin consumir Gemini ni escribir objetos en OCI.

## Instalacion local

Clonar el repositorio y entrar al backend:

```powershell
git clone https://github.com/No-Country-simulation/nuevamente-g10-latam-equipo21.git
cd nuevamente-g10-latam-equipo21/backend
```

Crear y activar un entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

En Linux o macOS, la activacion equivalente es:

```bash
source .venv/bin/activate
```

Instalar las dependencias:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Crear la configuracion local a partir de la plantilla:

```powershell
Copy-Item .env.example .env
```

En Linux o macOS:

```bash
cp .env.example .env
```

El archivo `.env` contiene configuracion local y secretos: **nunca debe agregarse a Git**.

## Configuracion

Las variables disponibles se encuentran en [`backend/.env.example`](backend/.env.example).

### Aplicacion

| Variable | Valor de ejemplo | Uso |
|---|---|---|
| `ENVIRONMENT` | `development` | Entorno de ejecucion. |
| `API_V1_STR` | `/api/v1` | Prefijo de las rutas de la API. |
| `PROJECT_NAME` | `NuevaMente API` | Nombre expuesto por FastAPI. |
| `VERSION` | `0.1.0` | Version informativa de la API. |
| `USE_MOCK_LLM` | `true` | Activa la respuesta mock sin llamadas externas. |
| `CORS_ORIGINS` | `["http://localhost:8501"]` | Origenes autorizados para el frontend. |

### Gemini y RAG

| Variable | Valor de ejemplo | Uso |
|---|---|---|
| `GEMINI_API_KEY` | `tu_api_key_aqui` | Credencial de Gemini; obligatoria para el pipeline real. |
| `GEMINI_MODEL_NAME` | `gemini-3.8-flash` | Modelo generativo. |
| `GEMINI_EMBEDDING_MODEL_NAME` | `gemini-embedding-001` | Modelo de embeddings. |
| `GEMINI_TIMEOUT_SECONDS` | `30` | Tiempo maximo por llamada al proveedor. |
| `CHROMA_PERSIST_DIRECTORY` | `./chroma_db` | Directorio local de ChromaDB. |
| `RETRIEVAL_TOP_K` | `5` | Cantidad maxima de fragmentos recuperados. |
| `RETRIEVAL_SCORE_THRESHOLD` | `0.35` | Umbral minimo de similitud. |
| `RETRIEVAL_MAX_CONTEXT_TOKENS` | `2000` | Limite del contexto ensamblado. |
| `FIDELITY_SCORE_THRESHOLD` | `0.7` | Umbral de fidelidad contra la fuente. |
| `MULTI_AGENT_MAX_ITERATIONS` | `3` | Maximo de iteraciones Redactor-Critico del flujo multi-agente. |

### OCI Object Storage

| Variable | Valor de ejemplo | Uso |
|---|---|---|
| `OCI_AUTH_MODE` | `api_key` | Metodo de autenticacion: `api_key` en local o `instance_principal` en OCI Compute. |
| `OCI_NAMESPACE` | `tu_namespace_oci_aqui` | Namespace de Object Storage. |
| `OCI_BUCKET_NAME` | `nuevamente-contenidos-educativos` | Bucket privado del proyecto. |
| `OCI_REGION` | `sa-saopaulo-1` | Region de OCI. |
| `OCI_USER_OCID` | valor local | Usuario tecnico para autenticacion por API key. |
| `OCI_TENANCY_OCID` | valor local | Tenancy de OCI. |
| `OCI_FINGERPRINT` | valor local | Fingerprint de la clave publica. |
| `OCI_KEY_FILE` | `~/.oci/oci_api_key.pem` | Ruta local a la clave privada. |
| `OCI_KEY_PASSPHRASE` | vacio | Passphrase, si la clave privada utiliza una. |

No compartas el archivo `.env`, `~/.oci/config`, claves `.pem` ni credenciales reales.

## Configuracion de OCI Object Storage

1. Seleccionar la region donde se ejecutara el proyecto; el entorno actual utiliza Sao Paulo (`sa-saopaulo-1`).
2. Crear un bucket **privado** llamado `nuevamente-contenidos-educativos` o definir otro nombre mediante `OCI_BUCKET_NAME`.
3. Crear un grupo IAM para el servicio y asignarle una politica limitada al bucket requerido.
4. Crear un usuario tecnico, agregarlo al grupo y registrar su clave publica de API.
5. Guardar la clave privada solamente en el equipo o instancia que ejecuta el backend.
6. En local, completar `OCI_AUTH_MODE=api_key` y las variables de la credencial dentro del `.env`.
7. En OCI Compute, utilizar `OCI_AUTH_MODE=instance_principal` y dejar vacias las variables de API key.
8. Verificar permisos de carga y lectura sin otorgar acceso a otros buckets.

Para despliegues sobre una instancia de OCI debe utilizarse la autenticacion mediante principal de instancia, evitando claves de usuario almacenadas en el servidor.

NM-11 proporciona la carga del documento original y del paquete generado. Su adaptador ya esta conectado al pipeline integral de NM-12. Si OCI falla, la generacion no se descarta: el endpoint conserva HTTP 200 y devuelve `almacenamiento_oci.status_upload="error"`.

## Ejecucion

Todos los comandos siguientes deben ejecutarse desde `backend/`, con el entorno virtual activo.

### Modo mock

Permite comprobar el contrato HTTP sin utilizar Gemini, ChromaDB ni OCI:

```dotenv
USE_MOCK_LLM=true
```

### Pipeline real

Ejecuta recuperacion, Gemini, evaluacion, metadatos y persistencia en OCI:

```dotenv
USE_MOCK_LLM=false
GEMINI_API_KEY=tu_api_key
OCI_AUTH_MODE=api_key
OCI_NAMESPACE=tu_namespace
```

En el pipeline real tambien deben completarse las variables OCI restantes descritas en la seccion de configuracion. Dentro de OCI Compute debe utilizarse `OCI_AUTH_MODE=instance_principal` y no deben copiarse credenciales de usuario a la instancia.

Iniciar la API en modo desarrollo:

```powershell
python -m uvicorn app.main:app --reload
```

Servicios disponibles:

- API: <http://127.0.0.1:8000>
- Estado: <http://127.0.0.1:8000/api/v1/health>
- Swagger UI: <http://127.0.0.1:8000/api/v1/docs>
- Acceso corto a Swagger: <http://127.0.0.1:8000/docs>.
- OpenAPI: <http://127.0.0.1:8000/api/v1/openapi.json>

Ejecutar las pruebas:

```powershell
python -m pytest tests -q
```

La prueba contra el bucket real es opt-in para evitar escrituras accidentales durante una ejecucion normal:

```powershell
$env:RUN_OCI_INTEGRATION = "1"
python -m pytest tests/test_storage_oci_integration.py -v -s
Remove-Item Env:RUN_OCI_INTEGRATION
```

La politica IAM del proyecto permite crear y leer objetos, pero no eliminarlos. Por ese motivo, el objeto pequeño generado por la prueba puede permanecer en el bucket y requerir limpieza manual desde una identidad administrativa.

## Uso de la API

### 1. Extraer texto de un documento

`POST /api/v1/documents/extract` recibe un archivo PDF, Markdown o TXT como `multipart/form-data`.

Ejemplo con `curl`:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/documents/extract" \
  -F "file=@documento.pdf"
```

La respuesta entrega el texto normalizado en `text` y los datos del archivo en `metadata`. Ese texto puede utilizarse como `documento_contenido` en la solicitud de adaptacion.

### 2. Adaptar el contenido

`POST /api/v1/adaptar-contenido` recibe texto previamente extraido y los cuatro ejes de personalizacion.

Request de ejemplo:

```json
{
  "documento_titulo": "Introduccion a las redes VCN",
  "documento_contenido": "Una Virtual Cloud Network es una red privada y configurable dentro de Oracle Cloud Infrastructure.",
  "perfil_destinatario": "Principiante",
  "formato_salida": "Flashcards",
  "nicho_sector": "General",
  "nivel_detalle": "Didactico"
}
```

Response de ejemplo:

```json
{
  "status": "exito",
  "metadatos": {
    "perfil_aplicado": "Principiante",
    "formato_generado": "Flashcards",
    "tiempo_estimado_estudio_minutos": 5,
    "conceptos_clave": ["VCN", "Subredes", "Internet Gateway"],
    "prerrequisitos": []
  },
  "contenido_adaptado": {
    "titulo": "Introduccion a las redes VCN",
    "introduccion_contextualizada": "Estas tarjetas resumen los conceptos principales del documento.",
    "items": [
      {
        "frente": "¿Que es una VCN?",
        "dorso": "Una red privada configurable dentro de OCI.",
        "pista_didactica": "Imagina una red aislada propia dentro de la nube."
      }
    ]
  },
  "evaluacion_calidad": {
    "anclaje_fuente_score": 0.95,
    "claridad_pedagogica": "Alta",
    "observaciones": "El contenido se encuentra respaldado por la fuente."
  },
  "almacenamiento_oci": {
    "bucket": "nuevamente-contenidos-educativos",
    "objeto_id": "contenido-introduccion-a-las-redes-vcn-principiante-flashcards-a1b2c3d4e5f6.json",
    "status_upload": "completado"
  }
}
```

Valores admitidos:

- `perfil_destinatario`: `Principiante`, `Desarrollador_Junior_SemiSenior`, `Lider_Tecnico_Arquitecto`, `Gestor_Ejecutivo_No_Tecnico`.
- `formato_salida`: `Tutorial`, `Flashcards`, `Quiz`, `Resumen_Ejecutivo`, `Guion_Clase`.
- `nicho_sector`: `Fintech`, `Salud`, `Ecommerce`, `General`.
- `nivel_detalle`: `Introductorio`, `Didactico`, `Tecnico_Profundo`.

> Con `USE_MOCK_LLM=true`, el endpoint devuelve datos de prueba respetando el contrato y no ejecuta servicios externos. Con `USE_MOCK_LLM=false`, utiliza el pipeline real y persiste el paquete generado mediante OCI Object Storage.

### Comportamiento ante errores

- Una entrada invalida devuelve HTTP 422 con `status: "error"` y el bloque `error` (`codigo`, `mensaje`).
- Un fallo del LLM o del vector store devuelve HTTP 502 sin exponer trazas ni credenciales.
- Un fallo de OCI no invalida el contenido generado: devuelve HTTP 200 con `almacenamiento_oci.status_upload: "error"`.
- Los errores quedan asociados a un identificador de peticion en los logs del backend.

Ejemplo de entrada invalida:

```json
{
  "status": "error",
  "error": {
    "codigo": "ENTRADA_INVALIDA",
    "mensaje": "Campo 'perfil_destinatario': valor no permitido"
  }
}
```

## Seguridad

- No versionar `.env`, claves privadas, tokens ni archivos `.pem`.
- No incluir credenciales reales en capturas, issues, logs o pull requests.
- Utilizar usuarios tecnicos y permisos de minimo privilegio en OCI.
- Rotar inmediatamente cualquier credencial que haya sido expuesta.

## Contribuciones

Las ramas de funcionalidad se crean desde `develop` con el formato `feature/NM-XX-descripcion`. Los cambios ingresan mediante pull request y requieren revision de otro integrante.

Los mensajes siguen Conventional Commits, por ejemplo:

```text
docs(NM-16): documentar arquitectura e instalacion local
```

Consulta [`CONTRIBUTING.md`](CONTRIBUTING.md) para conocer la convencion completa.

El historial de implementacion y las contribuciones individuales pueden consultarse en [Commits](https://github.com/No-Country-simulation/nuevamente-g10-latam-equipo21/commits/develop/) y [Contributors](https://github.com/No-Country-simulation/nuevamente-g10-latam-equipo21/graphs/contributors). Cada cambio funcional debe conservar la referencia a su ticket en la rama, el commit o el pull request.

## Estado de la validacion de NM-16

- [x] Descripcion del proyecto, problema y sector.
- [x] Diagrama de arquitectura embebido.
- [x] Guia inicial de instalacion y ejecucion.
- [x] Inventario inicial de variables de entorno.
- [x] Configuracion inicial de OCI Object Storage.
- [x] Ejemplo de request y response.
- [x] Actualizar variables y configuracion despues de integrar NM-11.
- [x] Actualizar la guia despues de integrar NM-11 con NM-12.
- [x] Aclarar el estado del frontend y del flujo multi-agente.
- [x] Actualizar `docs/ARCHITECTURE.md` con el contrato y el estado implementado.
- [ ] Validar la instalacion desde cero con una persona que no haya escrito esta documentacion.
- [ ] Verificar el historial y las contribuciones del equipo antes de la entrega.

## Documentacion adicional

- [Arquitectura y contratos](docs/ARCHITECTURE.md)
- [Guia de contribucion](CONTRIBUTING.md)
