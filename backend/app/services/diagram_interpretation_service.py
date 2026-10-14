"""Interpretación multimodal de diagramas técnicos extraídos de documentos."""

from dataclasses import dataclass

from google import genai
from google.genai import types

from app.core.config import settings
from app.services.document_ingestion import ExtractedImage


class DiagramInterpretationError(Exception):
    """Error al interpretar una imagen mediante el modelo multimodal."""


@dataclass(frozen=True)
class InterpretedDiagram:
    """Descripción textual de un diagrama y su posición de origen."""

    description: str
    page_number: int
    image_index: int
    image_name: str


class DiagramInterpretationService:
    """Convierte imágenes extraídas de documentos en descripciones textuales."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        client=None,
    ):
        self.model_name = model_name or settings.GEMINI_MODEL_NAME

        # Permite utilizar un cliente falso durante los tests
        # sin realizar llamadas reales a Gemini.
        if client is not None:
            self.client = client
            return

                # Si api_key es None, utiliza la configurada en settings.
        key = (
            settings.GEMINI_API_KEY
            if api_key is None
            else api_key
        )

        self.client = genai.Client(api_key=key) if key else None

    def interpret(
        self,
        image: ExtractedImage,
    ) -> InterpretedDiagram:
        """Genera una descripción técnica de una imagen extraída."""

        if not image.data:
            raise DiagramInterpretationError(
                "La imagen extraída no contiene datos."
            )
        
        if self.client is None:
            raise DiagramInterpretationError(
                "No se configuró GEMINI_API_KEY."
            )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Part.from_text(
                        text=(
                            "Describe este diagrama técnico de forma precisa. "
                            "Identifica componentes, relaciones, etiquetas, "
                            "flujo y cualquier información técnica relevante. "
                            "Devuelve únicamente la descripción del diagrama."
                        )
                    ),
                    types.Part.from_bytes(
                        data=image.data,
                        mime_type=image.mime_type,
                    ),
                ],
            )

            description = (response.text or "").strip()

            if not description:
                raise DiagramInterpretationError(
                    "Gemini no devolvió una descripción del diagrama."
                )

            return InterpretedDiagram(
                description=description,
                page_number=image.page_number,
                image_index=image.image_index,
                image_name=image.name,
            )

        except DiagramInterpretationError:
            raise

        except Exception as exc:
            raise DiagramInterpretationError(
                f"Error interpretando diagrama: {exc}"
            ) from exc

def get_diagram_interpretation_service() -> DiagramInterpretationService:
    """Crea el servicio utilizado para interpretar diagramas técnicos."""
    return DiagramInterpretationService()