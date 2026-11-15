import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

from datos import cargar
from estilo import (
    COLORES_SENSOR,
    ETIQUETAS_SENSOR,
    NIVELES,
    aplicar_estilo,
    descripcion_accesible,
    leyenda,
    mapa_detecciones,
    mapa_prioridad,
)

st.set_page_config(page_title="Tunari Blindspot", layout="wide")
aplicar_estilo()

st.title("Tunari Blindspot")
st.caption("Armonización de detecciones MODIS y VIIRS para priorizar la vigilancia en el Parque Nacional Tunari")

st.markdown(
    "Esta plataforma une las detecciones de calor de dos satélites, mide cuánto se observa cada zona "
    "y señala los sectores que merecen mayor vigilancia."
)

limpio = cargar("limpio.parquet")
unificada = cargar("unificada.parquet")
prioridad = cargar("prioridad.parquet")

if limpio is None or unificada is None or prioridad is None:
    st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("Detecciones unificadas", len(unificada))
col2.metric("Vistas por ambos satélites", int((unificada["sensor_visto"] == "ambos").sum()))
hay_prioridad = prioridad["prioridad"].notna().any()
col3.metric("Zonas de prioridad alta", int((prioridad["prioridad"] >= 0.66).sum()) if hay_prioridad else "—")

st.header("Armonización de los satélites")
izquierda, derecha = st.columns(2)

with izquierda:
    st.subheader("Antes: cada satélite por separado")
    leyenda([(nombre, COLORES_SENSOR[nombre]) for nombre in ("MODIS", "VIIRS")])
    st_folium(
        mapa_detecciones(limpio, "sensor"),
        height=420,
        use_container_width=True,
        returned_objects=[],
        key="mapa_antes",
    )

with derecha:
    st.subheader("Después: detecciones unificadas")
    leyenda([(ETIQUETAS_SENSOR[clave], color) for clave, color in COLORES_SENSOR.items()])
    st_folium(
        mapa_detecciones(unificada, "sensor_visto", ETIQUETAS_SENSOR),
        height=420,
        use_container_width=True,
        returned_objects=[],
        key="mapa_despues",
    )

descripcion_accesible(
    f"Dos mapas del Parque Nacional Tunari. El primero muestra {len(limpio)} detecciones de calor "
    "coloreadas según el satélite que las registró. El segundo muestra las detecciones unificadas, "
    "indicando si fueron vistas por ambos satélites o solo por uno."
)

conteo = unificada["sensor_visto"].map(ETIQUETAS_SENSOR).value_counts().reset_index()
conteo.columns = ["Visto por", "Detecciones"]
figura = px.bar(
    conteo,
    x="Visto por",
    y="Detecciones",
    color="Visto por",
    color_discrete_map={ETIQUETAS_SENSOR[clave]: color for clave, color in COLORES_SENSOR.items()},
)
figura.update_layout(showlegend=False, height=300, margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(figura)

st.header("Zonas prioritarias de vigilancia")
if hay_prioridad:
    zonas = prioridad.dropna(subset=["prioridad"])
    leyenda([(f"Prioridad {etiqueta.lower()}", color) for _, etiqueta, color in NIVELES])
    st_folium(
        mapa_prioridad(zonas),
        height=450,
        use_container_width=True,
        returned_objects=[],
        key="mapa_prioridad",
    )
    descripcion_accesible(
        f"Mapa con {len(zonas)} zonas del Tunari. Cada círculo es una zona: mientras más grande y más "
        "anaranjado, mayor es la prioridad de vigilancia. Al pasar el cursor se muestra el nivel."
    )
else:
    st.info("El puntaje de prioridad necesita registros independientes de observación satelital "
            "(ver README_ANALISIS.md). La página «Armonización y tipos» muestra dónde se repite más el fuego.")

st.info("Usa el menú superior para ver el mapa en vivo, el pronóstico, las alertas y el análisis.")