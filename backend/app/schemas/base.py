from pydantic import BaseModel, ConfigDict


class PublicSchema(BaseModel):
    """Configuración común para los contratos públicos de la API."""

    model_config = ConfigDict(extra="forbid")
