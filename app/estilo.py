import folium
import pandas as pd
import streamlit as st

COLORES = {
    "primario": "#0B5C8C",
    "alta": "#D55E00",
    "media": "#E69F00",
    "baja": "#0072B2",
}

COLORES_SENSOR = {
    "MODIS": "#0072B2",
    "VIIRS": "#E69F00",
    "ambos": "#CC79A7",
}

ETIQUETAS_SENSOR = {
    "MODIS": "Solo MODIS",
    "VIIRS": "Solo VIIRS",
    "ambos": "Ambos satélites",
}

NIVELES = [
    (0.66, "Alta", COLORES["alta"]),
    (0.33, "Media", COLORES["media"]),
    (0.0, "Baja", COLORES["baja"]),
]

ZONA_HORARIA = "America/La_Paz"
CENTRO = (-17.30, -66.25)


def nivel_prioridad(valor):
    for minimo, etiqueta, color in NIVELES:
        if valor >= minimo:
            return etiqueta, color
    return "Baja", COLORES["baja"]


def hora_local(serie):
    return pd.to_datetime(serie, utc=True).dt.tz_convert(ZONA_HORARIA)


def aplicar_estilo():
    st.markdown(
        "<style>.block-container{padding-top:2rem;max-width:1200px;}</style>",
        unsafe_allow_html=True,
    )


def descripcion_accesible(texto):
    with st.expander("Descripción en texto de este gráfico"):
        st.write(texto)


def leyenda(items):
    partes = [f"<span style='color:{color};font-size:1.3em'>●</span> {etiqueta}" for etiqueta, color in items]
    st.markdown("&nbsp;&nbsp;&nbsp;&nbsp;".join(partes), unsafe_allow_html=True)


def mapa_base():
    return folium.Map(location=CENTRO, zoom_start=11, tiles="OpenStreetMap", control_scale=True)


def mapa_detecciones(datos, columna, etiquetas=None):
    mapa = mapa_base()
    for fila in datos.itertuples():
        valor = getattr(fila, columna)
        texto = etiquetas.get(valor, valor) if etiquetas else valor
        folium.CircleMarker(
            location=(fila.latitud, fila.longitud),
            radius=6,
            color=COLORES_SENSOR[valor],
            fill=True,
            fill_opacity=0.8,
            tooltip=texto,
        ).add_to(mapa)
    return mapa


def mapa_prioridad(datos):
    mapa = mapa_base()
    for fila in datos.itertuples():
        etiqueta, color = nivel_prioridad(fila.prioridad)
        folium.CircleMarker(
            location=(fila.latitud, fila.longitud),
            radius=8 + fila.prioridad * 14,
            color=color,
            fill=True,
            fill_opacity=0.65,
            tooltip=f"Prioridad {etiqueta.lower()} ({fila.prioridad:.2f})",
        ).add_to(mapa)
    return mapa