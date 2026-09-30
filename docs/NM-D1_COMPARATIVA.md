# NM-D1 — Comparativa de calidad antes y después del refactor multi-agente

## Objetivo

Documentar el comportamiento del pipeline antes y después de incorporar
la orquestación multi-agente con LangGraph.

La comparación evalúa principalmente:

- score de anclaje a fuente;
- claridad pedagógica;
- comportamiento del Agente Crítico;
- cantidad de iteraciones del Redactor.

## Documento utilizado

Documento provisional de prueba:

`backend/tests/fixtures/Curso Python e Inteligencia Artificial.pdf`

Este documento se utiliza mientras el equipo confirma el documento
técnico oficial para la demo de NM-17.

El script permite reemplazar posteriormente la ruta, identificador y
título del documento sin modificar la lógica de comparación.

## Configuración

- Perfil: `Principiante`
- Formato: `Flashcards`
- Nicho: `General`
- Nivel de detalle: `Didactico`
- Umbral productivo de fidelidad: `0.7`
- Máximo de iteraciones del Redactor: `3`

Para la ejecución local se utilizó temporalmente
`gemini-3.5-flash-lite` debido a una respuesta HTTP 503 por alta demanda
de `gemini-3.8-flash`.

La configuración oficial del proyecto no fue modificada por esta prueba.

## Pipeline anterior

El flujo previo al refactor corresponde a:

1. Recuperación de contexto RAG.
2. Generación de contenido mediante NM-08.
3. Evaluación de fidelidad mediante NM-09.
4. Finalización de la respuesta.

No existe una regeneración automática cuando la evaluación de fidelidad
queda por debajo del umbral.

## Pipeline multi-agente NM-D1

El nuevo flujo implementado con LangGraph contiene tres nodos:

1. `investigador`: recupera y ensambla el contexto RAG.
2. `redactor`: genera el contenido pedagógico reutilizando NM-08.
3. `critico`: evalúa la fidelidad reutilizando NM-09.

Cuando el score queda debajo del umbral, el Crítico devuelve sus
observaciones al Redactor y se genera una nueva versión.

El número máximo de iteraciones es configurable para evitar ciclos
infinitos.

## Resultados de ejecución real

### Ejecución con umbral productivo

Resultado observado:

| Métrica | Antes | Multi-agente |
|---|---:|---:|
| Score de anclaje | 1.00 | 0.91 |
| Claridad pedagógica | Alta | Alta |
| Iteraciones del Redactor | 1 | 1 |

El score `0.91` se mantuvo por encima del umbral productivo `0.7`,
por lo que el Agente Crítico no solicitó una nueva generación.

La revisión detectó una afirmación no completamente respaldada:
la introducción indicaba que el contenido se explicaría "desde cero",
mientras que el documento fuente establece un nivel intermedio.

### Segunda ejecución

Resultado observado:

| Métrica | Antes | Multi-agente |
|---|---:|---:|
| Score de anclaje | 1.00 | 1.00 |
| Claridad pedagógica | Alta | Alta |
| Iteraciones del Redactor | 1 | 1 |

En esta ejecución ambos contenidos quedaron totalmente respaldados.

El grafo finalizó después de la primera revisión, evitando una
regeneración innecesaria.

## Variabilidad del LLM

Las ejecuciones antes y después realizan generaciones independientes
mediante un LLM, por lo que los resultados pueden variar entre llamadas.

Por este motivo, una diferencia puntual de score no debe interpretarse
por sí sola como una mejora o degradación del mecanismo.

Los tests automatizados verifican de manera determinista las decisiones
del grafo.

## Validación automatizada

La suite específica de NM-D1 valida:

- existencia de los tres nodos;
- finalización inmediata con score suficiente;
- retorno del Crítico al Redactor cuando el score es bajo;
- límite máximo de iteraciones;
- transferencia de observaciones del Crítico al siguiente intento;
- mejora de score en un escenario controlado;
- mantenimiento del contrato público definido por NM-07.

Estado al momento de esta comparación:

`108 passed`

## Cómo ejecutar la comparativa

La comparativa debe ejecutarse desde el directorio `backend`.

Prerrequisitos:

- Python 3.11.
- Entorno virtual activado.
- Dependencias instaladas con `pip install -r requirements.txt`.
- `GEMINI_API_KEY` configurada en `backend/.env`.
- Documento de prueba disponible en la ruta configurada dentro del script.

Desde `backend`:

```powershell
python -m scripts.comparar_nm_d1

## Integración con el flujo productivo

NM-D1 implementa y valida la orquestación multi-agente como servicio
independiente.

La conexión del grafo con el endpoint y la pipeline integral corresponde
al trabajo de NM-12. Por este motivo, en este ticket el grafo es consumido
por los tests automatizados y por el script de comparación, sin modificar
todavía el contrato ni el endpoint público.

## Conclusión

El refactor multi-agente mantiene el contrato público existente y agrega
un mecanismo de revisión iterativa sin afectar las respuestas que ya
alcanzan el nivel de fidelidad configurado.

Cuando el contenido no supera el umbral, LangGraph permite que el
Agente Crítico devuelva observaciones al Redactor y controle una nueva
iteración hasta alcanzar el límite configurado.

El documento utilizado en esta comparación es provisional y será
reemplazado por el documento oficial de NM-17 cuando el equipo lo
confirme.