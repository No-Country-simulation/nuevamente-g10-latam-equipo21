from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json


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
    GEMINI_MODEL_NAME: str = "gemini-1.5-flash"
    GEMINI_EMBEDDING_MODEL_NAME: str = "gemini-embedding-001"

    # Vector Store (ChromaDB)
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_db"

    # Oracle Cloud Infrastructure (OCI Object Storage)
    OCI_CONFIG_FILE: str = "~/.oci/config"
    OCI_PROFILE: str = "DEFAULT"
    OCI_NAMESPACE: str = ""
    OCI_BUCKET_NAME: str = "nuevamente-contenidos-educativos"
    OCI_REGION: str = "us-ashburn-1"


settings = Settings()
