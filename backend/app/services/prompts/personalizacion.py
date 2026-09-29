"""
Instrucciones de personalización versionadas para el prompt de adaptación de contenido (NM-08).

Las claves de estos diccionarios son exactamente los valores del contrato publicado en
docs/ARCHITECTURE.md (`perfil_destinatario`, `formato_salida`, `nicho_sector`,
`nivel_detalle`). Se consumen como strings literales a propósito: NM-08 no define un Enum de
Python propio para no duplicar los enums formales que va a aportar NM-07.
"""

from __future__ import annotations

INSTRUCCIONES_PERFIL: dict[str, str] = {
    "Principiante": (
        "Escribí para alguien sin experiencia previa en el tema. Definí cada término técnico la "
        "primera vez que aparece, evitá jerga innecesaria y apoyate en analogías cotidianas."
    ),
    "Desarrollador_Junior_SemiSenior": (
        "Escribí para una persona desarrolladora con experiencia básica a intermedia. Podés usar "
        "terminología técnica estándar sin redefinirla, con foco en la aplicación práctica y en "
        "buenas prácticas."
    ),
    "Lider_Tecnico_Arquitecto": (
        "Escribí para una persona con expertise técnico profundo. Priorizá trade-offs de "
        "diseño, implicancias de arquitectura, escalabilidad y mantenibilidad. Podés ser denso "
        "y directo, sin explicar conceptos básicos."
    ),
    "Gestor_Ejecutivo_No_Tecnico": (
        "Escribí para una persona sin formación técnica que toma decisiones de negocio. Evitá "
        "jerga técnica por completo y enfocate en impacto de negocio, riesgo, costo y tiempos."
    ),
}

INSTRUCCIONES_NICHO: dict[str, str] = {
    "Fintech": (
        "Usá ejemplos y analogías del sector financiero: pagos, banca, riesgo crediticio y "
        "cumplimiento regulatorio."
    ),
    "Salud": (
        "Usá ejemplos y analogías del sector salud: atención al paciente, historias clínicas y "
        "privacidad de datos médicos."
    ),
    "Ecommerce": (
        "Usá ejemplos y analogías de comercio electrónico: catálogos de productos, checkout, "
        "inventario y comportamiento de compra."
    ),
    "General": "Usá ejemplos neutros, no atados a un sector de aplicación específico.",
}

INSTRUCCIONES_NIVEL_DETALLE: dict[str, str] = {
    "Introductorio": (
        "Cubrí el tema a alto nivel: qué es y para qué sirve. No entres en casos borde ni en "
        "detalles de implementación."
    ),
    "Didactico": (
        "Explicá el tema con profundidad media: el cómo además del qué, apoyado en ejemplos "
        "guiados paso a paso."
    ),
    "Tecnico_Profundo": (
        "Cubrí el tema en profundidad máxima: casos borde, funcionamiento interno, trade-offs "
        "de performance y de escalabilidad."
    ),
}

# Cada formato define su propia instrucción de forma para "items" y un ejemplo mínimo de UN
# item en ese formato (few-shot puntual), reflejando el contrato de docs/ARCHITECTURE.md §5.
INSTRUCCIONES_FORMATO: dict[str, dict[str, str]] = {
    "Tutorial": {
        "instrucciones": (
            'Cada elemento de "items" es un paso de una guía secuencial, con las claves '
            '"paso_numero" (entero), "titulo_paso", "contenido" y "codigo_ejemplo" '
            "(string o null si no aplica)."
        ),
        "ejemplo_item": (
            '{"paso_numero": 1, "titulo_paso": "Crear el índice", '
            '"contenido": "...", "codigo_ejemplo": "CREATE INDEX ..."}'
        ),
    },
    "Flashcards": {
        "instrucciones": (
            'Cada elemento de "items" es una tarjeta de estudio, con las claves "frente", '
            '"dorso" y "pista_didactica".'
        ),
        "ejemplo_item": '{"frente": "...", "dorso": "...", "pista_didactica": "..."}',
    },
    "Quiz": {
        "instrucciones": (
            'Cada elemento de "items" es una pregunta de opción múltiple, con las claves '
            '"pregunta", "opciones" (array de exactamente 4 strings), "respuesta_correcta" y '
            '"justificacion".'
        ),
        "ejemplo_item": (
            '{"pregunta": "...", "opciones": ["A", "B", "C", "D"], '
            '"respuesta_correcta": "A", "justificacion": "..."}'
        ),
    },
    "Resumen_Ejecutivo": {
        "instrucciones": (
            'Cada elemento de "items" es un punto clave para una audiencia ejecutiva, con las '
            'claves "punto_clave", "descripcion" e "impacto_negocio".'
        ),
        "ejemplo_item": '{"punto_clave": "...", "descripcion": "...", "impacto_negocio": "..."}',
    },
    "Guion_Clase": {
        "instrucciones": (
            'Cada elemento de "items" es una sección de un guion de clase o video, con las '
            'claves "seccion", "tiempo_estimado_minutos" (número), "narracion" y '
            '"notas_visuales".'
        ),
        "ejemplo_item": (
            '{"seccion": "...", "tiempo_estimado_minutos": 5, "narracion": "...", '
            '"notas_visuales": "..."}'
        ),
    },
}
