import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import incendios as inc
import tema
import tiempo_real as tr

DIAS_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

encabezado, selector = st.columns([3, 1.2], vertical_alignment="bottom")
encabezado.markdown("## Pronóstico para el Tunari")
encabezado.caption("Próximos 7 días, hora por hora. Fuente: Open-Meteo (modelos meteorológicos globales).")
sector = selector.selectbox("Sector del parque", list(tr.SECTORES), key="sector_pron")


@st.fragment(run_every=f"{st.session_state.get('intervalo_min', 10)}m")
def contenido():
    p = tr.pronostico(*tr.SECTORES[sector])
    if p is None:
        st.error("No se pudo consultar el pronóstico. Se reintentará en la próxima actualización.")
        return
    regla = st.session_state.get("regla", inc.REGLA_RECOMENDADA)
    dias, horas = p["dias"], p["horas"]

    izq, der = st.columns([1.25, 1], gap="large")
    with izq:
        with st.container(border=True):
            st.markdown("**7 días** · rango de temperatura del día, de la mínima a la máxima")
            lo, hi = min(dias["temperature_2m_min"].min(), 0), max(dias["temperature_2m_max"].max(), 34)
            filas = []
            for d in dias.itertuples():
                tmin, tmax = d.temperature_2m_min, d.temperature_2m_max
                nivel, fondo, texto = inc.nivel_riesgo(tmax, d.relative_humidity_2m_min, d.wind_speed_10m_max, regla)
                izq_pct = (tmin - lo) / (hi - lo) * 100
                ancho = max(2, (tmax - tmin) / (hi - lo) * 100)
                nombre = "Hoy" if d.Index == 0 else DIAS_SEMANA[d.time.weekday()]
                filas.append(
                    f'<div class="tb-dia"><div><b style="color:#fff">{nombre}</b><div class="tb-etq">{d.time:%d/%m}</div></div>'
                    f'<div style="font-size:13px">{d.wind_speed_10m_max:.0f} km/h<div class="tb-etq">del '
                    f'{inc.punto_cardinal(d.wind_direction_10m_dominant)}</div></div>'
                    f'<div style="display:flex;align-items:center;gap:10px">'
                    f'<span style="width:34px;text-align:right;color:{inc.color_aire(tmin)};font-weight:600">{tmin:.0f}°</span>'
                    f'<div class="tb-pista"><div style="position:absolute;top:0;bottom:0;border-radius:4px;left:{izq_pct:.1f}%;'
                    f'width:{ancho:.1f}%;background:linear-gradient(90deg,{inc.color_aire(tmin)},{inc.color_aire(tmax)})"></div></div>'
                    f'<span style="width:34px;color:{inc.color_aire(tmax)};font-weight:700">{tmax:.0f}°</span></div>'
                    f'<div class="tb-extra">{tema.chip("Riesgo " + nivel, fondo, texto)}<span class="tb-etq">Humedad mín. '
                    f'{d.relative_humidity_2m_min:.0f} % · lluvia {d.precipitation_sum:.1f} mm</span></div></div>')
            st.markdown("".join(filas), unsafe_allow_html=True)
            st.markdown(f'<div style="display:flex;align-items:center;gap:10px;margin-top:10px" class="tb-etq">0 °C'
                        f'<div style="flex:1;height:6px;border-radius:3px;background:{inc.DEGRADADO_AIRE}"></div>36 °C</div>',
                        unsafe_allow_html=True)

    with der:
        futuro = horas[horas["time"] >= pd.Timestamp(tr.ahora().replace(tzinfo=None)).floor("h")].copy()
        futuro["puntos"] = [inc.puntos_riesgo(t, h, v, regla) for t, h, v in
                            zip(futuro.temperature_2m, futuro.relative_humidity_2m, futuro.wind_speed_10m)]
        peor = futuro.sort_values(["puntos", "temperature_2m"], ascending=False).iloc[0]
        nivel, _, _ = inc.NIVELES_RIESGO[int(peor.puntos)]
        tema.aviso(
            f'<span style="font-size:12px;font-weight:700;letter-spacing:.5px">PEOR MOMENTO DE LA SEMANA</span>'
            f'<div style="font-family:Space Grotesk,sans-serif;font-size:24px;font-weight:700;color:#fff;margin:4px 0">'
            f'{DIAS_SEMANA[peor.time.weekday()]} {peor.time:%d/%m}, {peor.time:%H:%M}</div>'
            f'{peor.temperature_2m:.0f} °C, {peor.relative_humidity_2m:.0f} % de humedad, viento de '
            f'{peor.wind_speed_10m:.0f} km/h (ráfagas de {peor.wind_gusts_10m:.0f}). Riesgo {nivel}: '
            f'se cumplen {int(peor.puntos)} de 3 condiciones de tu regla.',
            "fuego" if peor.puntos >= 2 else "info")
        st.write("")
        with st.container(border=True):
            st.markdown("**Viento en las próximas 48 horas**")
            prox = futuro.head(48)
            rosa = go.Figure(go.Barpolar(
                r=prox["wind_speed_10m"], theta=prox["wind_direction_10m"],
                marker=dict(color=prox["wind_speed_10m"], colorscale=[[0, "#1E4A73"], [1, "#FF7A2F"]], line_width=0),
                opacity=0.9, hovertemplate="%{r:.0f} km/h desde %{theta:.0f}°<extra></extra>"))
            rosa.update_layout(height=290, margin=dict(l=20, r=20, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)",
                               polar=dict(bgcolor="#0A0E13", angularaxis=dict(direction="clockwise", rotation=90,
                                          tickvals=[0, 90, 180, 270], ticktext=["N", "E", "S", "O"], color="#A9BACB"),
                                          radialaxis=dict(color="#A9BACB", showticklabels=False, gridcolor="#1E2630")), font_color="#E8EEF4")
            st.plotly_chart(rosa, use_container_width=True, config={"displayModeBar": False})
            dominante = inc.punto_cardinal(prox["wind_direction_10m"].median())
            st.caption(f"Sopla sobre todo del {dominante}. Hacia allá iría el humo y avanzaría un fuego.")

    with st.container(border=True):
        variable = st.segmented_control("Variable", ["Temperatura", "Viento", "Humedad", "Lluvia"],
                                        default="Temperatura", key="var_pron")
        variable = variable or "Temperatura"
        h48 = futuro.head(48)
        col = {"Temperatura": "temperature_2m", "Viento": "wind_speed_10m",
               "Humedad": "relative_humidity_2m", "Lluvia": "precipitation"}[variable]
        unidad = {"Temperatura": "°C", "Viento": "km/h", "Humedad": "%", "Lluvia": "mm"}[variable]
        if variable == "Temperatura":
            colores = [inc.color_aire(v) for v in h48[col]]
        else:
            colores = {"Viento": "#5AB0FF", "Humedad": "#7BD88F", "Lluvia": "#9F8CFF"}[variable]
        fig = go.Figure(go.Bar(x=h48["time"], y=h48[col], marker_color=colores, marker_line_width=0,
                               hovertemplate="%{x|%a %d %H:%M}<br>%{y:.1f} " + unidad + "<extra></extra>"))
        umbral = {"Temperatura": regla["temp"], "Viento": regla["viento"], "Humedad": regla["humedad"]}.get(variable)
        if umbral is not None:
            fig.add_hline(y=umbral, line_dash="dash", line_color="#FF7A2F",
                          annotation_text=f"tu regla: {umbral} {unidad}", annotation_font_color="#FFB27A")
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(0,0,0,0)", font_color="#A9BACB", bargap=0.15,
                          xaxis=dict(gridcolor="#1E2630"), yaxis=dict(gridcolor="#1E2630", title=unidad))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    tema.estado_datos(f"Pronóstico para {sector} ({p['elevacion']:.0f} m)")


contenido()
