# NM-D4 — Interpretación de diagramas técnicos

## 1. Objetivo

Incorporar interpretación multimodal de imágenes presentes en
documentos PDF, conservando la compatibilidad con el procesamiento
tradicional de documentos sin imágenes.

## 2. Arquitectura implementada

Flujo de procesamiento:

1. El usuario envía un documento PDF.
2. document_ingestion.py extrae texto e imágenes.
3. Cada imagen conserva su página, índice, nombre y tipo MIME.
4. diagram_interpretation_service.py envía las imágenes a Gemini.
5. Gemini genera una descripción técnica.
6. La descripción se incorpora como un TextChunk de tipo "diagram".
7. ChromaStore indexa los chunks de texto y diagramas.
8. ChromaVectorStore recupera los fragmentos relevantes.
9. retrieval_service.py incorpora las descripciones al contexto.
10. El sistema de generación puede utilizar esa información.

## 3. Compatibilidad

Los documentos sin imágenes mantienen el comportamiento anterior.

La respuesta de /documents/extract conserva los campos:

- text
- metadata

Cuando existen imágenes interpretadas, se agrega:

- diagramas

El esquema InputSchema admite diagramas como campo opcional,
con una lista vacía por defecto.

## 4. Trazabilidad

Cada diagrama conserva:

- source_type: "diagram"
- page_number: página de origen
- image_index: posición de la imagen
- image_name: nombre de la imagen

Estos metadatos permiten identificar el origen de la información
recuperada desde Chroma.

## 5. Modelo multimodal

Modelo configurado:

gemini-3.8-flash

Variable de configuración:

GEMINI_MODEL_NAME

Credencial requerida para interpretar imágenes:

GEMINI_API_KEY

Los documentos sin imágenes no necesitan activar el servicio
multimodal.

## 6. Costos adicionales

Cada imagen interpretada produce una solicitud adicional a Gemini.

Tarifas estándar de pago de Gemini 3.8 Flash,
vigentes hasta el 31 de diciembre de 2026:

- Entrada: USD 0,75 por millón de tokens.
- Salida: USD 3,75 por millón de tokens.

A partir del 1 de enero de 2027, las tarifas publicadas son:

- Entrada: USD 1,50 por millón de tokens.
- Salida: USD 7,50 por millón de tokens.

El consumo depende de:

- Cantidad de imágenes.
- Resolución de las imágenes.
- Tokens utilizados en las instrucciones.
- Longitud de las descripciones generadas.
- Tokens de razonamiento utilizados por el modelo.

Estos valores corresponden al nivel estándar de pago y deben
verificarse nuevamente antes de utilizar el servicio en producción.

## 7. Límites y consideraciones

Gemini 3.8 Flash admite:

- Hasta 1.048.576 tokens de entrada.
- Hasta 65.536 tokens de salida.
- Imágenes como entrada y texto como salida.

La implementación actual envía cada imagen individualmente.

Los límites de solicitudes por minuto, tokens por minuto y
solicitudes diarias dependen del proyecto, modelo y nivel de uso.

Consideraciones operativas:

- Un documento con muchas imágenes aumenta las solicitudes.
- Las imágenes grandes pueden incrementar el consumo de tokens.
- El procesamiento multimodal requiere conectividad con Gemini.
- Sin GEMINI_API_KEY no se pueden interpretar imágenes.
- Los tests utilizan clientes falsos y no consumen tokens reales.
- La implementación actual no establece un límite propio de
  imágenes por documento ni calcula previamente su costo.

## 8. Dependencias

Dependencias utilizadas:

- pypdf==6.19.0
- Pillow==12.3.0
- google-genai==2.25.0

## 9. Pruebas

Se implementaron pruebas para verificar:

- Extracción de imágenes desde PDF.
- Conservación de la posición de origen.
- Interpretación multimodal mediante cliente falso.
- Indexación de descripciones como TextChunk.
- Persistencia de metadatos en Chroma.
- Recuperación semántica de diagramas.
- Incorporación de descripciones al contexto.
- Compatibilidad con documentos sin imágenes.

## 10. Referencias oficiales

Precios:
https://ai.google.dev/gemini-api/docs/pricing

Modelo:
https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash

Procesamiento de imágenes:
https://ai.google.dev/gemini-api/docs/image-understanding

Límites de solicitudes:
https://ai.google.dev/gemini-api/docs/rate-limits