"""
Orquestación multi-agente con LangGraph (NM-D1).

Agentes:
1. Investigador RAG:
   recupera contexto relevante del documento.
2. Redactor Pedagógico:
   genera contenido adaptado reutilizando NM-08.
3. Crítico/Revisor:
   evalúa fidelidad reutilizando NM-09.

Si el score de fidelidad queda debajo del umbral,
el flujo vuelve al Redactor hasta alcanzar el máximo
de iteraciones configurado.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.core.config import settings
from app.schemas.output import (
    ContenidoAdaptadoSchema,
    EvaluacionCalidadSchema,
)
from app.services.fidelity_service import evaluar_fidelidad
from app.services.llm_provider import LLMProvider
from app.services.orchestration_service import generar_contenido_adaptado
from app.services.retrieval_service import (
    ensamblar_contexto,
    recuperar_contexto,
)
from app.services.vector_store import (
    FragmentoRecuperado,
    VectorStore,
)


class EstadoMultiAgente(TypedDict, total=False):
    """
    Estado compartido por todos los nodos del grafo.
    """

    documento_id: str
    documento_titulo: str
    consulta_recuperacion: str

    perfil_destinatario: str
    formato_salida: str
    nicho_sector: str
    nivel_detalle: str

    fragmentos: list[FragmentoRecuperado]
    contexto_recuperado: str

    contenido_adaptado: ContenidoAdaptadoSchema
    evaluacion_calidad: EvaluacionCalidadSchema
    feedback_critico: str

    iteracion: int


def crear_grafo_multiagente(
    *,
    vector_store: VectorStore,
    llm_provider: LLMProvider,
    max_iterations: int | None = None,
    fidelity_threshold: float | None = None,
):
    """
    Construye y compila el grafo multi-agente de NM-D1.
    """

    max_iter = (
        settings.MULTI_AGENT_MAX_ITERATIONS
        if max_iterations is None
        else max_iterations
    )

    threshold = (
        settings.FIDELITY_SCORE_THRESHOLD
        if fidelity_threshold is None
        else fidelity_threshold
    )

    if max_iter <= 0:
        raise ValueError(
            "max_iterations debe ser mayor que 0."
        )

    if not 0 <= threshold <= 1:
        raise ValueError(
            "fidelity_threshold debe estar entre 0 y 1."
        )

    # -------------------------------------------------
    # AGENTE 1: INVESTIGADOR RAG
    # -------------------------------------------------
    def investigador(
        state: EstadoMultiAgente,
    ) -> dict:
        # NM-28: si el servicio ya recuperó el contexto (con cobertura por
        # ventanas, NM-22), no se recupera de nuevo.
        if state.get("contexto_recuperado"):
            return {}

        fragmentos = recuperar_contexto(
            consulta=state["consulta_recuperacion"],
            vector_store=vector_store,
            documento_id=state["documento_id"],
        )

        contexto = ensamblar_contexto(
            fragmentos
        )

        return {
            "fragmentos": fragmentos,
            "contexto_recuperado": contexto,
        }

    # -------------------------------------------------
    # AGENTE 2: REDACTOR PEDAGÓGICO
    # -------------------------------------------------
    def redactor(
        state: EstadoMultiAgente,
    ) -> dict:
        iteracion = state.get("iteracion", 0) + 1

        contenido = generar_contenido_adaptado(
            documento_titulo=state["documento_titulo"],
            contexto_recuperado=state["contexto_recuperado"],
            perfil_destinatario=state[
                "perfil_destinatario"
            ],
            formato_salida=state["formato_salida"],
            nicho_sector=state["nicho_sector"],
            nivel_detalle=state["nivel_detalle"],
            llm_provider=llm_provider,
            feedback_critico=state.get("feedback_critico"),
            contenido_anterior=state.get("contenido_adaptado"),
        )

        return {
            "contenido_adaptado": contenido,
            "iteracion": iteracion,
        }

    # -------------------------------------------------
    # AGENTE 3: CRÍTICO / REVISOR
    # -------------------------------------------------
    def critico(
        state: EstadoMultiAgente,
    ) -> dict:
        evaluacion = evaluar_fidelidad(
            documento_id=state["documento_id"],
            contenido_adaptado=state[
                "contenido_adaptado"
            ],
            vector_store=vector_store,
            llm_provider=llm_provider,
            perfil_destinatario=state[
                "perfil_destinatario"
            ],
            umbral=threshold,
        )

        return {
            "evaluacion_calidad": evaluacion,
            "feedback_critico": evaluacion.observaciones,
        }

    # -------------------------------------------------
    # DECISIÓN DEL CRÍTICO
    # -------------------------------------------------
    def decidir_despues_del_critico(
        state: EstadoMultiAgente,
    ) -> str:
        score = state[
            "evaluacion_calidad"
        ].anclaje_fuente_score

        iteracion = state.get(
            "iteracion",
            0,
        )

        if score >= threshold:
            return "finalizar"

        if iteracion >= max_iter:
            return "finalizar"

        return "reescribir"

    # -------------------------------------------------
    # CONSTRUCCIÓN DEL GRAFO
    # -------------------------------------------------
    graph = StateGraph(
        EstadoMultiAgente
    )

    graph.add_node(
        "investigador",
        investigador,
    )

    graph.add_node(
        "redactor",
        redactor,
    )

    graph.add_node(
        "critico",
        critico,
    )

    graph.add_edge(
        START,
        "investigador",
    )

    graph.add_edge(
        "investigador",
        "redactor",
    )

    graph.add_edge(
        "redactor",
        "critico",
    )

    graph.add_conditional_edges(
        "critico",
        decidir_despues_del_critico,
        {
            "reescribir": "redactor",
            "finalizar": END,
        },
    )

    return graph.compile()