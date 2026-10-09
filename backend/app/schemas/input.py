from typing import Optional
from pydantic import Field, StrictInt, StrictStr

from app.schemas.base import PublicSchema
from app.schemas.enums import (
    FormatoSalida,
    NichoSector,
    NivelDetalle,
    PerfilDestinatario,
)


class DocumentoPaginaSchema(PublicSchema):
    page_number: StrictInt = Field(
        ...,
        ge=1,
        description="Número de página de origen (1-indexado)",
    )

    text: StrictStr = Field(
        ...,
        min_length=1,
        description="Texto extraído de esa página",
    )


class InputSchema(PublicSchema):
    documento_id: Optional[StrictStr] = Field(
        default=None,
        description="Identificador único del documento original extraído previamente",
    )

    documento_titulo: StrictStr = Field(
        ...,
        min_length=3,
        description="Título del documento técnico",
    )

    documento_contenido: StrictStr = Field(
        ...,
        min_length=10,
        description="Contenido del documento técnico que será adaptado",
    )

    documento_paginas: Optional[list[DocumentoPaginaSchema]] = Field(
        default=None,
        description="Lista de páginas del documento con su texto y número de página",
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