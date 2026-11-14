"""Tunari Blindspot: punto de entrada de la aplicación.

Ejecutar desde la raíz del repositorio:
    streamlit run app/app.py
"""

import streamlit as st

import tema
import tiempo_real as tr

st.set_page_config(page_title="Tunari Blindspot", page_icon=":material/local_fire_department:", layout="wide",
                   initial_sidebar_state="collapsed")
tema.aplicar_tema()

paginas = [
    st.Page("paginas/mapa.py", title="Mapa en vivo", icon=":material/public:", default=True),
    st.Page("paginas/pronostico.py", title="Pronóstico", icon=":material/air:"),
    st.Page("paginas/alertas.py", title="Alertas", icon=":material/notifications_active:"),
    st.Page("paginas/analisis.py", title="Armonización y tipos", icon=":material/bar_chart:"),
    st.Page("main.py", title="Portada del equipo", icon=":material/home:"),
]
navegacion = st.navigation(paginas, position="top")

with st.sidebar:
    st.subheader("Actualización")
    st.selectbox("Consultar datos cada", [5, 10, 15, 30], index=1, key="intervalo_min",
                 format_func=lambda m: f"{m} minutos")
    if st.button("Actualizar ahora", use_container_width=True):
        tr.limpiar_cache()
        st.rerun()
    st.divider()
    st.subheader("Fuentes")
    if tr.hay_clave_firms():
        st.success("NASA FIRMS conectado")
    else:
        st.warning("Falta la clave de NASA FIRMS: los focos se muestran con datos de ejemplo.")
        st.caption("Pide una MAP_KEY gratis en firms.modaps.eosdis.nasa.gov/api/map_key y guárdala en "
                   "`.streamlit/secrets.toml` como `FIRMS_MAP_KEY = \"...\"`.")
    st.caption("Clima y relieve: Open-Meteo (sin clave). Imágenes satelitales: Esri. "
               "Relieve 3D: AWS Terrain Tiles.")

navegacion.run()
