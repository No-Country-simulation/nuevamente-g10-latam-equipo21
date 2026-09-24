"""
Enums del contrato funcional definido en docs/ARCHITECTURE.md (NM-01), §3.
"""

from enum import Enum


class PerfilDestinatario(str, Enum):
    PRINCIPIANTE = "Principiante"
    DESARROLLADOR_JUNIOR_SEMISENIOR = "Desarrollador_Junior_SemiSenior"
    LIDER_TECNICO_ARQUITECTO = "Lider_Tecnico_Arquitecto"
    GESTOR_EJECUTIVO_NO_TECNICO = "Gestor_Ejecutivo_No_Tecnico"


class FormatoSalida(str, Enum):
    TUTORIAL = "Tutorial"
    FLASHCARDS = "Flashcards"
    QUIZ = "Quiz"
    RESUMEN_EJECUTIVO = "Resumen_Ejecutivo"
    GUION_CLASE = "Guion_Clase"


class NichoSector(str, Enum):
    FINTECH = "Fintech"
    SALUD = "Salud"
    ECOMMERCE = "Ecommerce"
    GENERAL = "General"


class NivelDetalle(str, Enum):
    INTRODUCTORIO = "Introductorio"
    DIDACTICO = "Didactico"
    TECNICO_PROFUNDO = "Tecnico_Profundo"
