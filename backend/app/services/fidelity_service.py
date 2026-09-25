"""
Verificación de fidelidad del contenido generado contra el documento fuente (NM-09).

Puntúa cuánto de lo que generó el LLM (NM-08) está respaldado por el documento original y devuelve
el bloque `evaluacion_calidad` del contrato (docs/ARCHITECTURE.md, sección 4) como `dict`. La
validación formal contra los esquemas de NM-07 la aplica quien integre el pipeline (NM-12).

Método de cálculo de `anclaje_fuente_score`
-------------------------------------------
1. Evidencia. Por cada unidad de texto del contenido (la introducción y cada item) se buscan en el
   documento, con la recuperación de NM-06, los fragmentos más parecidos. La búsqueda se restringe a
   `documento_id` y no usa umbral de similitud: quien decide qué está respaldado es el verificador,
   no la similitud.
2. Verificación. Un único pedido al LLM (`LLMProvider`, NM-08) recibe el contenido y la evidencia. El
   modelo extrae las afirmaciones factuales, marca cada una como respaldada o no por la evidencia,
   califica la claridad pedagógica y escribe observaciones.
3. Score. Se calcula acá, no en el modelo: afirmaciones respaldadas sobre afirmaciones totales, entre
   0 y 1 y redondeado a dos decimales. Si el modelo no encuentra afirmaciones, el score es 0.0.
4. Umbral. Si el score queda por debajo de `FIDELITY_SCORE_THRESHOLD` se registra un warning con el
   id del documento.

No reintenta la generación cuando el score es bajo: queda fuera del alcance del ticket.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import PromptTemplate

from app.core.config import settings
from app.services.llm_provider import LLMProvider, LLMProviderError
from app.services.retrieval_service import ensamblar_contexto, recuperar_contexto
from app.services.vector_store import FragmentoRecuperado, VectorStore

logger = logging.getLogger(__name__)

FRAGMENTOS_POR_UNIDAD = 3
MAX_TOKENS_EVIDENCIA = 8000
_MAX_CARACTERES_CONSULTA = 2000
_CLARIDAD_VALIDA = ("Alta", "Media", "Baja")
_DIRECTORIO_PROMPTS = Path(__file__).parent / "prompts"


@lru_cache(maxsize=1)
def _cargar_prompt_base() -> str:
    return (_DIRECTORIO_PROMPTS / "verificacion_base.md").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _cargar_plantilla_usuario() -> PromptTemplate:
    # Sin el salto de línea final del archivo, para que el mensaje no lo arrastre.
    texto = (_DIRECTORIO_PROMPTS / "verificacion_usuario.md").read_text(encoding="utf-8")
    return PromptTemplate.from_template(texto.rstrip("\n"))


def _cadenas(valor: Any) -> list[str]:
    """Todas las cadenas de un valor JSON, en cualquier nivel de anidación."""
    if isinstance(valor, str):
        return [valor]
    if isinstance(valor, dict):
        return [texto for elemento in valor.values() for texto in _cadenas(elemento)]
    if isinstance(valor, list):
        return [texto for elemento in valor for texto in _cadenas(elemento)]
    return []


def _unidades(contenido_adaptado: dict[str, Any]) -> list[tuple[int, str]]:
    """Pares (número, texto) de la introducción (0) y de cada item con texto (1, 2, ...)."""
    items = contenido_adaptado.get("items")
    if not isinstance(items, list):
        raise ValueError("`contenido_adaptado` debe tener `items` como lista.")

    unidades: list[tuple[int, str]] = []
    introduccion = contenido_adaptado.get("introduccion_contextualizada")
    if isinstance(introduccion, str) and introduccion.strip():
        unidades.append((0, introduccion.strip()))
    for numero, item in enumerate(items, start=1):
        texto = " ".join(_cadenas(item)).strip()
        if texto:
            unidades.append((numero, texto))

    if not unidades:
        raise ValueError("El contenido no tiene texto para verificar.")
    return unidades


def _reunir_evidencia(
    unidades: list[tuple[int, str]],
    *,
    documento_id: str,
    vector_store: VectorStore,
    top_k: int,
) -> list[FragmentoRecuperado]:
    """Fragmentos del documento más parecidos a cada unidad, sin repetidos y de mayor a menor score."""
    mejores: dict[str, FragmentoRecuperado] = {}
    for _, texto in unidades:
        fragmentos = recuperar_contexto(
            consulta=texto[:_MAX_CARACTERES_CONSULTA],
            vector_store=vector_store,
            top_k=top_k,
            umbral=0.0,
            documento_id=documento_id,
        )
        for fragmento in fragmentos:
            previo = mejores.get(fragmento.chunk_id)
            if previo is None or fragmento.score > previo.score:
                mejores[fragmento.chunk_id] = fragmento
    return sorted(mejores.values(), key=lambda fragmento: fragmento.score, reverse=True)


def _presentar_contenido(contenido_adaptado: dict[str, Any]) -> str:
    """Contenido numerado como lo ve el verificador: título, introducción (0) e items (1, 2, ...)."""
    lineas: list[str] = []
    titulo = contenido_adaptado.get("titulo")
    if isinstance(titulo, str) and titulo.strip():
        lineas.append(f"Título: {titulo.strip()}")
    introduccion = contenido_adaptado.get("introduccion_contextualizada")
    if isinstance(introduccion, str) and introduccion.strip():
        lineas.append(f"Introducción: {introduccion.strip()}")
    for numero, item in enumerate(contenido_adaptado["items"], start=1):
        lineas.append(f"Item {numero}: {json.dumps(item, ensure_ascii=False)}")
    return "\n".join(lineas)


def _construir_mensajes(
    *, perfil_destinatario: str | None, evidencia: str, contenido: str
) -> list[BaseMessage]:
    mensaje_humano = _cargar_plantilla_usuario().format(
        perfil_destinatario=perfil_destinatario or "no especificado",
        evidencia=evidencia or "(no se recuperaron fragmentos del documento)",
        contenido=contenido,
    )
    return [
        SystemMessage(content=_cargar_prompt_base()),
        HumanMessage(content=mensaje_humano),
    ]


def _interpretar_respuesta(respuesta: Any) -> tuple[list[bool], str, str]:
    """Devuelve (veredictos, claridad, observaciones) o levanta `LLMProviderError` si no tiene la forma."""
    if isinstance(respuesta, dict):
        afirmaciones = respuesta.get("afirmaciones")
        claridad = respuesta.get("claridad_pedagogica")
        observaciones = respuesta.get("observaciones")
        forma_valida = (
            isinstance(afirmaciones, list)
            and all(
                isinstance(afirmacion, dict) and isinstance(afirmacion.get("respaldada"), bool)
                for afirmacion in afirmaciones
            )
            and claridad in _CLARIDAD_VALIDA
            and isinstance(observaciones, str)
            and bool(observaciones.strip())
        )
        if forma_valida:
            return [a["respaldada"] for a in afirmaciones], claridad, observaciones.strip()
    raise LLMProviderError("La respuesta del verificador de fidelidad no tiene la forma esperada.")


def calcular_score(respaldadas: list[bool]) -> float:
    """Afirmaciones respaldadas sobre afirmaciones totales (0.0 si no hay ninguna)."""
    if not respaldadas:
        return 0.0
    return round(sum(respaldadas) / len(respaldadas), 2)


def evaluar_fidelidad(
    *,
    documento_id: str,
    contenido_adaptado: dict[str, Any],
    vector_store: VectorStore,
    llm_provider: LLMProvider,
    perfil_destinatario: str | None = None,
    top_k: int = FRAGMENTOS_POR_UNIDAD,
    umbral: float | None = None,
) -> dict[str, Any]:
    """
    Evalúa qué tan respaldado está `contenido_adaptado` por el documento `documento_id`.

    Devuelve `{"anclaje_fuente_score", "claridad_pedagogica", "observaciones"}`, el bloque
    `evaluacion_calidad` del contrato. `perfil_destinatario`, si se conoce, orienta la valoración de
    la claridad. `umbral` reemplaza a `settings.FIDELITY_SCORE_THRESHOLD` solo para el registro en
    logs; no altera el score.

    Levanta `ValueError` si el contenido no tiene texto para verificar y `LLMProviderError` (o su
    subclase `LLMTimeoutError`) si el verificador falla o responde con una forma inesperada. Los
    fallos del almacén vectorial se propagan como `VectorStoreError` (ver vector_store.py).
    """
    unidades = _unidades(contenido_adaptado)
    fragmentos = _reunir_evidencia(
        unidades, documento_id=documento_id, vector_store=vector_store, top_k=top_k
    )
    evidencia = ensamblar_contexto(fragmentos, max_tokens=MAX_TOKENS_EVIDENCIA)
    mensajes = _construir_mensajes(
        perfil_destinatario=perfil_destinatario,
        evidencia=evidencia,
        contenido=_presentar_contenido(contenido_adaptado),
    )

    respaldadas, claridad, observaciones = _interpretar_respuesta(llm_provider.generate_json(mensajes))
    score = calcular_score(respaldadas)

    minimo = settings.FIDELITY_SCORE_THRESHOLD if umbral is None else umbral
    if score < minimo:
        logger.warning(
            "Fidelidad baja: documento_id=%s anclaje_fuente_score=%.2f umbral=%.2f",
            documento_id,
            score,
            minimo,
        )

    return {
        "anclaje_fuente_score": score,
        "claridad_pedagogica": claridad,
        "observaciones": observaciones,
    }
