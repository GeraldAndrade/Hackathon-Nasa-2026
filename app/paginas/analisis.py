import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import incendios as inc
import tema
import tiempo_real as tr

st.markdown("## Armonización y tipos de incendio")
st.caption("Una sola lista de focos sin duplicados, qué tan caliente es cada uno y dónde conviene vigilar más.")

unificada = tr.historico("unificada.parquet")
if unificada is None:
    st.warning("Todavía no hay detecciones armonizadas. Ejecuta `python src/ingesta.py` para descargar el "
               "historial de NASA FIRMS.")
    st.stop()
_fechas = pd.to_datetime(unificada["fecha_hora"], utc=True).dt.tz_convert("America/La_Paz")
st.caption(f"Historial real de NASA FIRMS dentro del parque: {_fechas.min():%d/%m/%Y} a {_fechas.max():%d/%m/%Y}.")

individual = tr.individual_historico()

u = unificada.assign(tipo=inc.clasificar(unificada.get("temp_brillo", pd.Series(index=unificada.index, dtype=float))),
                     anio=pd.to_datetime(unificada["fecha_hora"], utc=True).dt.tz_convert("America/La_Paz").dt.year)
conteo = u["sensor_visto"].value_counts()
n_mod = int((individual["sensor_visto"] == "MODIS").sum()) if individual is not None else 0
n_vii = int((individual["sensor_visto"] == "VIIRS").sum()) if individual is not None else 0


def miles(n):
    return f"{int(n):,}".replace(",", ".")


k = st.columns(5)
k[0].metric("Detecciones originales", miles(n_mod + n_vii), f"{miles(n_mod)} MODIS · {miles(n_vii)} VIIRS",
            delta_color="off")
k[1].metric("Focos unificados", miles(len(u)), f"{miles(n_mod + n_vii - len(u))} duplicados", delta_color="off")
k[2].metric("Vistos por ambos", miles(conteo.get("ambos", 0)), f"{conteo.get('ambos', 0) / len(u):.0%} del total",
            delta_color="off")
k[3].metric("Solo VIIRS", miles(conteo.get("VIIRS", 0)), "fuegos chicos para MODIS", delta_color="off")
k[4].metric("Solo MODIS", miles(conteo.get("MODIS", 0)), "sin pareja VIIRS", delta_color="off")

izq, der = st.columns([1.35, 1], gap="large")
with izq:
    with st.container(border=True):
        a, b = st.columns([2, 1.4], vertical_alignment="center")
        a.markdown("**Focos por temporada**, según su tipo")
        fuente = b.segmented_control("Fuente", ["Conjunto", "MODIS", "VIIRS"], default="Conjunto",
                                     key="fuente_anios", label_visibility="collapsed") or "Conjunto"
        if fuente == "Conjunto" or individual is None:
            datos = u
        else:
            datos = individual[individual["sensor_visto"] == fuente]
            datos = datos.assign(tipo=inc.clasificar(datos["temp_brillo"]),
                                 anio=pd.to_datetime(datos["fecha_hora"], utc=True).dt.tz_convert("America/La_Paz").dt.year)
        tabla = datos.groupby(["anio", "tipo"]).size().unstack(fill_value=0)
        fig = go.Figure()
        for c in inc.CLAVES:
            if c in tabla:
                fig.add_bar(x=tabla.index.astype(str), y=tabla[c], name=inc.NOMBRE[c], marker_color=inc.COLOR[c],
                            hovertemplate="%{x}: %{y} focos<extra>" + inc.NOMBRE[c] + "</extra>")
        fig.update_layout(barmode="stack", height=340, margin=dict(l=10, r=10, t=10, b=10),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#A9BACB",
                          legend=dict(orientation="h", y=-0.15), yaxis=dict(gridcolor="#1E2630"))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.caption({"Conjunto": "Los dos sensores unidos y sin duplicados.",
                    "MODIS": "MODIS ve menos focos, pero los que ve suelen ser grandes: su píxel de 1 km necesita más fuego.",
                    "VIIRS": "VIIRS ve muchos más fuegos pequeños gracias a su píxel de 375 m."}[fuente])

with der:
    with st.container(border=True):
        st.markdown("**¿Cómo se unen los dos sensores?**")
        st.markdown(
            "1. Se normalizan las dos listas: hora en UTC, coordenadas y confianza en *baja, nominal o alta*.\n"
            "2. Cada foco MODIS busca focos VIIRS a **1,5 km o menos** y **60 minutos o menos**.\n"
            "3. Si hay pareja se conserva la ubicación de VIIRS, cuyo píxel cubre unas 7 veces menos área, "
            "y se marca como **ambos**.")
        if "distancia_km" in u:
            amb = u[u["sensor_visto"] == "ambos"]
            distancia = f"{amb['distancia_km'].median():.2f}".replace(".", ",")
            st.markdown(f"Distancia típica entre parejas: **{distancia} km** · "
                        f"diferencia típica de tiempo: **{amb['desfase_min'].median():.0f} min**.")

with st.container(border=True):
    st.markdown("### Tipos de incendio según la temperatura")
    st.markdown("El satélite mide la **temperatura de brillo** del píxel: el promedio de todo el cuadro, fuego y terreno "
                "frío juntos. Por eso marca entre 40 y 100 °C aunque la llama real esté a 800 – 1.200 °C. "
                "Cuanto más alta, más grande o más intenso es el fuego.")
    fig = go.Figure()
    for i, t in enumerate(inc.TIPOS):
        desde, hasta = max(t[2], 300) - 273.15, min(t[3], 400) - 273.15
        fig.add_bar(y=[t[1]], x=[hasta - desde], base=[desde], orientation="h", marker_color=t[4],
                    text=inc.rango_texto(t[0]), textposition="inside", insidetextanchor="middle",
                    textfont_color=t[5], hovertemplate=t[6] + "<extra></extra>", showlegend=False)
    fig.add_vline(x=367 - 273.15, line_dash="dash", line_color="#8CC8FF",
                  annotation_text="VIIRS deja de medir", annotation_font_color="#8CC8FF")
    fig.update_layout(height=230, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font_color="#C9D4E0", bargap=0.35,
                      xaxis=dict(title="Temperatura del píxel (°C)", gridcolor="#1E2630", range=[27, 127]),
                      yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    cols = st.columns(4)
    frp = u.groupby("tipo")["frp"].median()
    n = u["tipo"].value_counts()
    for col, t in zip(cols, inc.TIPOS):
        c = t[0]
        col.markdown(
            f'<div class="tb-tarjeta" style="border-top:4px solid {t[4]}">'
            f'<div style="font-weight:700;color:#fff;font-size:16px">{t[1]}</div>'
            f'<div class="tb-grande" style="color:{t[4]}">{inc.rango_texto(c)}</div>'
            f'<p style="font-size:13.5px;color:#C9D4E0;margin:6px 0">{t[6]}.</p>'
            f'<div class="tb-fila"><span class="tb-etq">Potencia típica</span><b>{frp.get(c, float("nan")):.0f} MW</b></div>'
            f'<div class="tb-fila"><span class="tb-etq">Focos</span><b>{miles(n.get(c, 0))}</b></div>'
            f'<div class="tb-fila"><span class="tb-etq">Qué hacer</span><b style="text-align:right">{inc.QUE_HACER[c]}</b></div>'
            f'</div>', unsafe_allow_html=True)
    st.caption("Rangos orientativos. Con los datos reales conviene ajustarlos junto con la potencia (FRP) y separar "
               "MODIS de VIIRS, porque VIIRS se satura cerca de 94 °C (367 K).")

with st.container(border=True):
    st.markdown("### Cobertura por hora del día")
    st.caption("Cuántos satélites pasan sobre el Tunari en cada hora (hora de Bolivia). En las horas vacías nadie mira.")
    por_hora = {h: [] for h in range(24)}
    for sat, _, hhmm in tr.PASOS:
        por_hora[int(hhmm[:2])].append(sat)
    celdas = "".join(
        f'<div title="{h}:00 · {", ".join(s) or "sin observación"}" style="height:52px;border-radius:8px;display:flex;'
        f'align-items:center;justify-content:center;font-weight:700;color:#fff;'
        f'background:{"#2F7DD1" if len(s) >= 3 else "#1E4A73" if s else "#141A22"};'
        f'border:{"1px solid transparent" if s else "1px dashed #2A3441"}">{len(s) or ""}</div>'
        for h, s in por_hora.items())
    marcas = "".join(f'<span style="text-align:center" class="tb-etq">{h if h % 3 == 0 else ""}</span>' for h in range(24))
    st.markdown(f'<div class="tb-scroll"><div class="tb-horas">{celdas}</div>'
                f'<div class="tb-horas" style="margin-top:4px">{marcas}</div></div>', unsafe_allow_html=True)
    vacias = sum(1 for s in por_hora.values() if not s)
    st.markdown(f"**{vacias} de 24 horas** sin ningún paso de satélite. La peor franja va de **14:00 a 21:00**, "
                "justo cuando hace más calor y sopla más viento.")
    cob = tr.historico("cobertura.parquet", "cobertura")
    if cob is not None and "franja_local" in cob:
        franjas = cob.groupby("franja_local")["cobertura"].mean().reset_index()
        st.markdown("Cobertura media por franja según el análisis de P3:")
        st.dataframe(franjas.rename(columns={"franja_local": "Franja", "cobertura": "Cobertura media"}),
                     hide_index=True, column_config={"Cobertura media": st.column_config.ProgressColumn(
                         format="percent", min_value=0, max_value=1)})

with st.container(border=True):
    st.markdown("### Zonas prioritarias de vigilancia")
    prioridad = tr.historico("prioridad.parquet")
    sectores = dict(tr.SECTORES)

    def sector_mas_cercano(lat, lon):
        return min(sectores, key=lambda n: (sectores[n][0] - lat) ** 2 + (sectores[n][1] - lon) ** 2)

    if prioridad is None:
        st.info("Todavía no hay análisis por celda. Ejecuta `python src/ingesta.py`.")
    elif prioridad["prioridad"].notna().any():
        top = prioridad.dropna(subset=["prioridad"]).nlargest(10, "prioridad")
        tabla = pd.DataFrame({
            "Sector": [sector_mas_cercano(a, b) for a, b in zip(top.latitud, top.longitud)],
            "Coordenadas": [f"{a:.3f}, {b:.3f}" for a, b in zip(top.latitud, top.longitud)],
            "Focos": top["focos"].astype(int), "Cobertura": top["cobertura"], "Prioridad": top["prioridad"]})
        st.dataframe(tabla, hide_index=True, use_container_width=True, column_config={
            "Cobertura": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
            "Prioridad": st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=1)})
    else:
        # Sin registros independientes de observación la cobertura es desconocida (ver README_ANALISIS.md):
        # se muestran las celdas donde el fuego se repite más, sin inventar un puntaje.
        top = prioridad[prioridad["focos"] > 0].nlargest(10, ["intervalos_con_focos", "focos"])
        if top.empty:
            st.info("No hay focos registrados dentro del parque en el período descargado.")
        else:
            st.markdown("Celdas de ~1 km donde el fuego **se repite más** en el historial de FIRMS.")
            tabla = pd.DataFrame({
                "Sector": [sector_mas_cercano(a, b) for a, b in zip(top.latitud, top.longitud)],
                "Coordenadas": [f"{a:.3f}, {b:.3f}" for a, b in zip(top.latitud, top.longitud)],
                "Veces con fuego": top["intervalos_con_focos"].astype(int), "Focos": top["focos"].astype(int)})
            maximo = int(tabla["Veces con fuego"].max())
            st.dataframe(tabla, hide_index=True, use_container_width=True, column_config={
                "Veces con fuego": st.column_config.ProgressColumn(format="%d", min_value=0, max_value=maximo)})
            st.caption("«Veces con fuego» cuenta franjas de 6 h con al menos un foco. El puntaje de prioridad, que "
                       "combina recurrencia y cobertura, necesita registros independientes de observación "
                       "satelital (ver README_ANALISIS.md).")
