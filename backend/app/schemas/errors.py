from typing import Literal

from pydantic import BaseModel


class ErrorDetalle(BaseModel):
    codigo: str
    mensaje: str


class ErrorResponse(BaseModel):
    """Shape de error definido en docs/ARCHITECTURE.md §4 para status='error'."""

    status: Literal["error"] = "error"
    error: ErrorDetalle
