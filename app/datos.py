from pathlib import Path

import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parent.parent / "data"

COLUMNAS = {
    "limpio.parquet": ["id", "latitud", "longitud", "fecha_hora", "sensor", "confianza", "frp"],
    "unificada.parquet": ["id_unificado", "latitud", "longitud", "fecha_hora", "sensor_visto", "confianza", "frp"],
    "prioridad.parquet": ["celda_id", "latitud", "longitud", "focos", "cobertura", "prioridad"],
}


def _leer(nombre):
    archivo = RAIZ / "processed" / nombre
    return _leer_archivo(nombre, archivo.stat().st_mtime if archivo.exists() else 0.0)


@st.cache_data
def _leer_archivo(nombre, version):
    archivo = RAIZ / "processed" / nombre
    if not archivo.exists():
        return None
    datos = pd.read_parquet(archivo)
    if datos.empty:  # un archivo vacío no sirve para mostrar nada
        return None
    if nombre == "limpio.parquet" and "latitud" not in datos.columns:
        datos = _normalizar_limpio(datos)
    return datos


def _normalizar_limpio(datos):
    """limpio.parquet llega con las columnas crudas de FIRMS: se pasan al formato del contrato."""
    import sys

    sys.path.insert(0, str(RAIZ.parent / "src"))
    from armonizacion import normalizar

    return normalizar(datos)


def cargar(nombre):
    datos = _leer(nombre)

    if datos is None:
        st.warning(f"No hay datos en {nombre}. Ejecuta `python src/ingesta.py` para descargarlos de NASA FIRMS.")
        return None

    faltantes = [c for c in COLUMNAS.get(nombre, []) if c not in datos.columns]
    if faltantes:
        st.error(f"Al archivo {nombre} le faltan las columnas: {', '.join(faltantes)}")
        return None

    return datos