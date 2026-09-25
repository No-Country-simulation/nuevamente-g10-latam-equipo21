from enum import Enum


class PerfilDestinatario(str, Enum):
    PRINCIPIANTE = "Principiante"
    TRANSICION_CARRERA = "Transicion de Carrera"
    DESARROLLADOR_JUNIOR = "Desarrollador Junior"
    DESARROLLADOR_SEMI_SENIOR = "Desarrollador Semi Senior"
    LIDER_TECNICO = "Lider Tecnico"
    ARQUITECTO = "Arquitecto"
    GESTOR = "Gestor"
    EJECUTIVO_NO_TECNICO = "Ejecutivo No Tecnico"


class FormatoSalida(str, Enum):

    TUTORIAL = "Tutorial"

    FLASHCARDS = "Flashcards"

    QUIZ = "Quiz"

    RESUMEN_EJECUTIVO = "Resumen Ejecutivo"

    GUION = "Guion"


class NichoSector(str, Enum):

    FINTECH = "Fintech"

    SALUD = "Salud"

    ECOMMERCE = "E-commerce"

    GENERAL = "General"


class NivelDetalle(str, Enum):

    BASICO = "Basico"

    INTERMEDIO = "Intermedio"

    AVANZADO = "Avanzado"
