from pydantic import BaseModel, Field

from app.schemas.enums import (
    FormatoSalida,
    NichoSector,
    NivelDetalle,
    PerfilDestinatario,
)


class AdaptarContenidoRequest(BaseModel):
    """Contrato de entrada de POST /adaptar-contenido (docs/ARCHITECTURE.md §3)."""

    documento_titulo: str = Field(..., min_length=1)
    documento_contenido: str = Field(..., min_length=1)
    perfil_destinatario: PerfilDestinatario
    formato_salida: FormatoSalida
    nicho_sector: NichoSector
    nivel_detalle: NivelDetalle
