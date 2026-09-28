# Curso Intensivo: Python e Inteligencia Artificial
**Nivel:** Intermedio | **Duración:** 4 Semanas | **Modalidad:** Práctica

---

## 1. Introducción al Ecosistema Python para IA
Python se ha consolidado como el lenguaje estándar de la industria para la Inteligencia Artificial y el Aprendizaje Automático debido a su sintaxis clara, versatilidad y una enorme colección de librerías especializadas.

* **NumPy y Pandas:** Fundamentales para el manejo eficiente de vectores, matrices y estructuras de datos tabulares a gran escala.
* **Scikit-Learn:** La librería insignia para Machine Learning clásico (regresiones, clasificación, árboles de decisión).

## 2. Manipulación y Preprocesamiento de Datos
El éxito de cualquier modelo de IA depende de la calidad de sus datos. Este módulo cubre las técnicas esenciales para preparar la información:
* **Limpieza de datos:** Tratamiento de valores nulos, duplicados y anomalías estadísticas.
* **Normalización y Escalamiento:** Estandarización de variables para optimizar los algoritmos de gradiente descendente.
* **Codificación de Variables Categóricas:** Transformación de texto a representaciones numéricas (One-Hot Encoding, Label Encoding).

## 3. Machine Learning Supervisado y No Supervisado
Implementación práctica de algoritmos predictivos y de agrupación utilizando librerías optimizadas.

```python
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier

# Carga y división de datos
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
modelo = RandomForestClassifier(n_estimators=100)
modelo.fit(X_train, y_train)
precision = modelo.score(X_test, y_test)
print(f"Precisión del modelo: {precision * 100:.2f}%")
```

---

## 4. Introducción al Deep Learning con PyTorch
El aprendizaje profundo permite resolver problemas complejos de visión por computadora y procesamiento de lenguaje natural simulando redes neuronales artificiales.

| Componente | Descripción | Librería Principal |
| :--- | :--- | :--- |
| **Redes Convolucionales (CNN)** | Procesamiento y clasificación de imágenes y vídeo. | PyTorch / Torchvision |
| **Redes Recurrentes (RNN/LSTM)** | Análisis de secuencias temporales y texto. | PyTorch / Hugging Face |
| **Transformers y LLMs** | Modelos avanzados de lenguaje y generación de contenido. | Transformers (Hugging Face) |

## 5. Creación de Aplicaciones con IA Generativa
Integra modelos de lenguaje avanzados (LLMs) y APIs de IA en aplicaciones reales utilizando Python.
* **Consumo de APIs:** Conexión con proveedores de modelos de lenguaje mediante peticiones seguras.
* **Ingeniería de Prompts:** Diseño de instrucciones estructuradas para obtener respuestas precisas y automatizadas.
* **Retrieval-Augmented Generation (RAG):** Conexión de bases de datos vectoriales con modelos de lenguaje para consultar documentos privados.

## 6. Proyecto Final Integrador
Los estudiantes desarrollarán un sistema inteligente completo, desde la recolección y limpieza de datos hasta el despliegue del modelo en un servidor local mediante una interfaz interactiva con Streamlit.

> **Certificación y Evaluación:** La aprobación del curso requiere la entrega del código fuente documentado en GitHub y la defensa técnica del proyecto integrador ante un panel de instructores.