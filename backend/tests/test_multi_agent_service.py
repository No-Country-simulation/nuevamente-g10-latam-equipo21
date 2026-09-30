from app.schemas.content import FlashcardItem
from app.schemas.output import (
    ContenidoAdaptadoSchema,
    EvaluacionCalidadSchema,
    OutputSchema,
)
from app.services.fidelity_service import VerificacionFidelidadLLMSchema
from app.services.multi_agent_service import crear_grafo_multiagente
from app.services.vector_store import FragmentoRecuperado


class VectorStoreFake:
    """
    Vector store falso para probar el grafo sin ChromaDB ni embeddings reales.
    """

    def __init__(self):
        self.consultas = []

    def buscar_similares(
        self,
        *,
        texto_consulta,
        top_k,
        documento_id=None,
    ):
        self.consultas.append(texto_consulta)

        return [
            FragmentoRecuperado(
                chunk_id="doc-001:0",
                documento_id="doc-001",
                texto=(
                    "Un índice de base de datos permite acelerar "
                    "las búsquedas sobre una tabla."
                ),
                score=0.95,
                metadatos={"pagina": 1},
            )
        ]


class LLMProviderFake:
    """
    Simula tanto al Redactor como al Crítico.

    Cada elemento de respuestas_fidelidad representa una revisión:
    True  = afirmación respaldada.
    False = afirmación no respaldada.
    """

    def __init__(self, respuestas_fidelidad):
        self.respuestas_fidelidad = respuestas_fidelidad
        self.generaciones = 0
        self.revisiones = 0
        self.mensajes_redactor = []

    def generate_structured(
        self,
        messages,
        schema,
    ):
        # --------------------------------------------
        # REDACTOR
        # --------------------------------------------
        if schema is ContenidoAdaptadoSchema:
            self.generaciones += 1
            self.mensajes_redactor.append(messages)

            return ContenidoAdaptadoSchema(
                titulo="Índices",
                introduccion_contextualizada=(
                    f"Versión {self.generaciones} del contenido."
                ),
                items=[
                    FlashcardItem(
                        frente="¿Para qué sirve un índice?",
                        dorso=(
                            "Permite acelerar búsquedas "
                            "sobre una tabla."
                        ),
                        pista_didactica=(
                            "Pensalo como el índice de un libro."
                        ),
                    )
                ],
            )

        # --------------------------------------------
        # CRÍTICO
        # --------------------------------------------
        if schema is VerificacionFidelidadLLMSchema:
            indice = min(
                self.revisiones,
                len(self.respuestas_fidelidad) - 1,
            )

            respaldadas = self.respuestas_fidelidad[indice]

            self.revisiones += 1

            return schema.model_validate(
                {
                    "afirmaciones": [
                        {
                            "item": posicion + 1,
                            "texto": f"Afirmación {posicion + 1}",
                            "respaldada": respaldada,
                        }
                        for posicion, respaldada
                        in enumerate(respaldadas)
                    ],
                    "claridad_pedagogica": "Alta",
                    "observaciones": (
                        "Evaluación realizada por el crítico."
                    ),
                }
            )

        raise AssertionError(
            f"Schema inesperado en test: {schema}"
        )


def estado_inicial():
    return {
        "documento_id": "doc-001",
        "documento_titulo": "Índices en bases de datos",
        "consulta_recuperacion": (
            "¿Para qué sirve un índice de base de datos?"
        ),
        "perfil_destinatario": "Principiante",
        "formato_salida": "Flashcards",
        "nicho_sector": "General",
        "nivel_detalle": "Introductorio",
        "iteracion": 0,
    }


def test_grafo_tiene_los_tres_agentes():
    store = VectorStoreFake()
    provider = LLMProviderFake([[True]])

    grafo = crear_grafo_multiagente(
        vector_store=store,
        llm_provider=provider,
    )

    nodos = set(grafo.get_graph().nodes)

    assert "investigador" in nodos
    assert "redactor" in nodos
    assert "critico" in nodos


def test_score_alto_finaliza_en_primer_intento():
    store = VectorStoreFake()
    provider = LLMProviderFake(
        [
            [True, True],
        ]
    )

    grafo = crear_grafo_multiagente(
        vector_store=store,
        llm_provider=provider,
        max_iterations=3,
        fidelity_threshold=0.7,
    )

    resultado = grafo.invoke(
        estado_inicial()
    )

    assert resultado["iteracion"] == 1

    assert (
        resultado["evaluacion_calidad"]
        .anclaje_fuente_score
        == 1.0
    )

    assert provider.generaciones == 1
    assert provider.revisiones == 1


def test_score_bajo_vuelve_al_redactor():
    store = VectorStoreFake()

    provider = LLMProviderFake(
        [
            [True, False],
            [True, True],
        ]
    )

    grafo = crear_grafo_multiagente(
        vector_store=store,
        llm_provider=provider,
        max_iterations=3,
        fidelity_threshold=0.7,
    )

    resultado = grafo.invoke(
        estado_inicial()
    )

    assert resultado["iteracion"] == 2

    assert (
        resultado["evaluacion_calidad"]
        .anclaje_fuente_score
        == 1.0
    )

    assert provider.generaciones == 2
    assert provider.revisiones == 2


def test_score_siempre_bajo_respeta_maximo_iteraciones():
    store = VectorStoreFake()

    provider = LLMProviderFake(
        [
            [False],
            [False],
            [False],
        ]
    )

    grafo = crear_grafo_multiagente(
        vector_store=store,
        llm_provider=provider,
        max_iterations=3,
        fidelity_threshold=0.7,
    )

    resultado = grafo.invoke(
        estado_inicial()
    )

    assert resultado["iteracion"] == 3

    assert (
        resultado["evaluacion_calidad"]
        .anclaje_fuente_score
        == 0.0
    )

    assert provider.generaciones == 3
    assert provider.revisiones == 3

def test_segundo_intento_recibe_feedback_del_critico():
    store = VectorStoreFake()

    provider = LLMProviderFake(
        [
            [True, False],
            [True, True],
        ]
    )

    grafo = crear_grafo_multiagente(
        vector_store=store,
        llm_provider=provider,
        max_iterations=3,
        fidelity_threshold=0.7,
    )

    resultado = grafo.invoke(
        estado_inicial()
    )

    assert resultado["iteracion"] == 2
    assert len(provider.mensajes_redactor) == 2

    primer_intento = "\n".join(
        mensaje.content
        for mensaje in provider.mensajes_redactor[0]
    )

    segundo_intento = "\n".join(
        mensaje.content
        for mensaje in provider.mensajes_redactor[1]
    )

    assert (
        "Evaluación realizada por el crítico."
        not in primer_intento
    )

    assert (
        "Evaluación realizada por el crítico."
        in segundo_intento
    )

    assert (
        "corrigiendo específicamente"
        in segundo_intento
    )

def test_multiagente_mantiene_contrato_publico_nm07():
    store = VectorStoreFake()

    provider = LLMProviderFake(
        [
            [True, True],
        ]
    )

    grafo = crear_grafo_multiagente(
        vector_store=store,
        llm_provider=provider,
        max_iterations=3,
        fidelity_threshold=0.7,
    )

    resultado = grafo.invoke(
        estado_inicial()
    )

    assert isinstance(
        resultado["contenido_adaptado"],
        ContenidoAdaptadoSchema,
    )

    assert isinstance(
        resultado["evaluacion_calidad"],
        EvaluacionCalidadSchema,
    )

    assert set(OutputSchema.model_fields) == {
        "status",
        "metadatos",
        "contenido_adaptado",
        "evaluacion_calidad",
        "almacenamiento_oci",
    }

def test_multiagente_mejora_score_despues_de_revision():
    store = VectorStoreFake()

    provider = LLMProviderFake(
        [
            # Primera revisión:
            # una afirmación respaldada y otra no.
            [True, False],

            # Segunda revisión:
            # ambas afirmaciones quedan respaldadas.
            [True, True],
        ]
    )

    grafo = crear_grafo_multiagente(
        vector_store=store,
        llm_provider=provider,
        max_iterations=3,
        fidelity_threshold=0.7,
    )

    resultado = grafo.invoke(
        estado_inicial()
    )

    assert resultado["iteracion"] == 2

    # El flujo terminó después de corregir
    # el contenido rechazado en la primera revisión.
    assert (
        resultado["evaluacion_calidad"]
        .anclaje_fuente_score
        == 1.0
    )

    assert provider.generaciones == 2
    assert provider.revisiones == 2

    # La segunda generación recibió feedback
    # específico del agente crítico.
    segundo_intento = "\n".join(
        mensaje.content
        for mensaje in provider.mensajes_redactor[1]
    )

    assert (
        "Evaluación realizada por el crítico."
        in segundo_intento
    )