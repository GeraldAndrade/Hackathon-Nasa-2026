from pathlib import Path

import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parent.parent / "data"

COLUMNAS = {
    "limpio.parquet": ["id", "latitud", "longitud", "fecha_hora", "sensor", "confianza", "frp"],
    "unificada.parquet": ["id_unificado", "latitud", "longitud", "fecha_hora", "sensor_visto", "confianza", "frp"],
    "prioridad.parquet": ["celda_id", "latitud", "longitud", "focos", "cobertura", "prioridad"],
}


@st.cache_data
def _leer(nombre):
    for carpeta in ("processed", "mock"):
        archivo = RAIZ / carpeta / nombre
        if archivo.exists():
            return pd.read_parquet(archivo), carpeta
    return None, None


def cargar(nombre):
    datos, origen = _leer(nombre)

    if datos is None:
        st.warning(f"No se encontró el archivo {nombre}. Avisa a la persona responsable de generarlo.")
        return None

    faltantes = [c for c in COLUMNAS.get(nombre, []) if c not in datos.columns]
    if faltantes:
        st.error(f"Al archivo {nombre} le faltan las columnas: {', '.join(faltantes)}")
        return None

    if origen == "mock":
        st.caption("Mostrando datos de ejemplo")

    return datos