import json
from typing import List, Literal, Union

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuración global de la aplicación validada con Pydantic v2.
    Lee automáticamente las variables de entorno o el archivo .env.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Configuración general de la API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "NuevaMente API"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str

    # Feature flag: activa el endpoint mock de adaptación (NM-18) mientras
    # NM-12 no implemente la pipeline real.
    USE_MOCK_LLM: bool = False
    
    # CORS: Orígenes permitidos (Frontend Streamlit)
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return []

    # Configuración de Google Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL_NAME: str = "gemini-3.8-flash"
    GEMINI_EMBEDDING_MODEL_NAME: str = "gemini-embedding-001"
    GEMINI_TIMEOUT_SECONDS: float = 30.0

    # Vector Store (ChromaDB)
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_db"

    # Recuperación semántica (NM-06)
    RETRIEVAL_TOP_K: int = 5
    RETRIEVAL_SCORE_THRESHOLD: float = 0.35
    RETRIEVAL_MAX_CONTEXT_TOKENS: int = 2000

    # Cobertura del documento completo en la recuperación (NM-22)
    RETRIEVAL_MAX_VENTANAS: int = 5
    RETRIEVAL_VENTANA_CHARS: int = 2000

    # Verificación de fidelidad (NM-09)
    FIDELITY_SCORE_THRESHOLD: float = 0.7

    # Orquestación multi-agente con LangGraph (NM-D1)
    MULTI_AGENT_MAX_ITERATIONS: int = 3

    # Usa el grafo multi-agente en el endpoint de adaptación (NM-28).
    # False = orquestación lineal (NM-08 + NM-09), que queda como fallback.
    USE_MULTIAGENT: bool = False

    # Oracle Cloud Infrastructure (OCI Object Storage)
    OCI_AUTH_MODE: Literal["instance_principal", "api_key"] = "instance_principal"
    OCI_NAMESPACE: str = ""
    OCI_BUCKET_NAME: str = "nuevamente-contenidos-educativos"
    OCI_REGION: str = "sa-saopaulo-1"
    OCI_USER_OCID: str = ""
    OCI_TENANCY_OCID: str = ""
    OCI_FINGERPRINT: str = ""
    OCI_KEY_FILE: str = ""
    OCI_KEY_PASSPHRASE: SecretStr | None = None

    @model_validator(mode="after")
    def validate_required_configuration(self):
        """
        Valida la configuración mínima necesaria para ejecutar
        el pipeline real.
        """
        if self.USE_MOCK_LLM:
            return self

        missing = []

        if not self.GEMINI_API_KEY.strip():
            missing.append("GEMINI_API_KEY")

        if not self.OCI_NAMESPACE.strip():
            missing.append("OCI_NAMESPACE")

        if missing:
            raise ValueError(
                "Faltan variables de configuración obligatorias "
                f"cuando USE_MOCK_LLM=false: {', '.join(missing)}"
            )

        return self

settings = Settings()
