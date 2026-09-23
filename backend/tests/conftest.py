import os
import pytest

# Aseguramos que para la suite de tests exista una variable ENVIRONMENT por defecto
# si no existe un archivo .env local, evitando que falle la carga inicial de app.
os.environ.setdefault("ENVIRONMENT", "test")
