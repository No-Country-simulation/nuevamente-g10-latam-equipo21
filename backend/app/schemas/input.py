from pydantic import BaseModel, Field

from app.schemas.enums import (
    FormatoSalida,
    NichoSector,
    NivelDetalle,
    PerfilDestinatario,
)

class DiagramaSchema(BaseModel):
    description: str = Field(
        ...,
        min_length=1,
        description="Descripción técnica generada a partir del diagrama",
    )

    page_number: int = Field(
        ...,
        ge=1,
        description="Página del documento donde se encontró el diagrama",
    )

    image_index: int = Field(
        ...,
        ge=1,
        description="Posición de la imagen dentro de la página",
    )

    image_name: str = Field(
        ...,
        min_length=1,
        description="Nombre de la imagen extraída",
    )

class InputSchema(BaseModel):
    documento_titulo: str = Field(
        ...,
        min_length=3,
        description="Título del documento técnico",
    )

    documento_contenido: str = Field(
        ...,
        min_length=10,
        description="Contenido del documento técnico que será adaptado",
    )

    diagramas: list[DiagramaSchema] = Field(
        default_factory=list,
        description="Diagramas técnicos interpretados del documento original",
    )



    perfil_destinatario: PerfilDestinatario = Field(
        ...,
        description="Perfil del público destinatario del contenido adaptado",
    )

    formato_salida: FormatoSalida = Field(
        ...,
        description="Formato en el que se generará el contenido adaptado",
    )

    nicho_sector: NichoSector = Field(
        ...,
        description="Sector o nicho al que pertenece el contenido",
    )

    nivel_detalle: NivelDetalle = Field(
        ...,
        description="Nivel de profundidad requerido para el contenido adaptado",
    )
