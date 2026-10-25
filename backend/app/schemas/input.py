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


class DiagramaSchema(PublicSchema):
    description: StrictStr = Field(
        ...,
        min_length=1,
        description="Descripción técnica generada a partir del diagrama",
    )

    page_number: StrictInt = Field(
        ...,
        ge=1,
        description="Página del documento donde se encontró el diagrama",
    )

    image_index: StrictInt = Field(
        ...,
        ge=1,
        description="Posición de la imagen dentro de la página",
    )

    image_name: StrictStr = Field(
        ...,
        min_length=1,
        description="Nombre de la imagen extraída",
    )


class InputSchema(PublicSchema):
    documento_id: Optional[StrictStr] = Field(
        default=None,
        min_length=1,
        description="Identificador estable devuelto por POST /documents/extract",
    )

    objeto_origen_id: Optional[StrictStr] = Field(
        default=None,
        min_length=1,
        description="Objeto OCI del documento original devuelto por POST /documents/extract",
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
        description="Lista de páginas del documento con su texto y número de página (NM-23)",
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
