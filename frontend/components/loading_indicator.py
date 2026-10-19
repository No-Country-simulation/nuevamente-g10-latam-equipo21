"""Indicador reutilizable para operaciones en curso."""

from collections.abc import Iterator
from contextlib import contextmanager

import streamlit as st


@contextmanager
def loading_indicator(message: str = "Procesando...") -> Iterator[None]:
    with st.spinner(message):
        yield
