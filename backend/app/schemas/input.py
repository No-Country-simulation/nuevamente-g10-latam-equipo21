from pydantic import Field

from app.schemas.base import ContractSchema
from app.schemas.enums import (
    FormatoSalida,
    NichoSector,
    NivelDetalle,
    PerfilDestinatario,
)

class InputSchema(ContractSchema):
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



    perfil_destinatario: PerfilDestinatario = Field(
        ...,
        strict=False,
        description="Perfil del público destinatario del contenido adaptado",
    )

    formato_salida: FormatoSalida = Field(
        ...,
        strict=False,
        description="Formato en el que se generará el contenido adaptado",
    )

    nicho_sector: NichoSector = Field(
        ...,
        strict=False,
        description="Sector o nicho al que pertenece el contenido",
    )

    nivel_detalle: NivelDetalle = Field(
        ...,
        strict=False,
        description="Nivel de profundidad requerido para el contenido adaptado",
    )
