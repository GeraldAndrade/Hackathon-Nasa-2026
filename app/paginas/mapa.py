import pandas as pd
import pydeck as pdk  # noqa: F401  (lo usa st.pydeck_chart)
import streamlit as st
from streamlit_folium import st_folium

import incendios as inc
import mapas
import tema
import tiempo_real as tr

MESES = {7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre"}

st.markdown("## Mapa en vivo")

@st.fragment(run_every=f"{st.session_state.get('intervalo_min', 10)}m")
def mapa_y_situacion():
    izq, centro, der = st.container(key="mapa_layout").columns([1.05, 3, 1.25], gap="medium")

    with izq:
        with st.container(border=True):
            st.markdown("**Focos**")
            fuente = st.segmented_control("Fuente", ["En vivo", "Histórico"], default="En vivo",
                                          key="fuente", label_visibility="collapsed")
            if fuente == "Histórico":
                mes = st.selectbox("Mes de la temporada 2025", list(MESES), index=2,
                                   format_func=lambda m: MESES[m].capitalize(), key="mes")
            else:
                dias = st.selectbox("Ventana", [1, 2, 5], key="dias",
                                    format_func=lambda d: "Últimas 24 horas" if d == 1 else f"Últimos {d} días")
            vista = st.segmented_control("Ver datos", ["Conjunto", "MODIS", "VIIRS"], default="Conjunto", key="vista",
                                         help="Conjunto: los dos sensores unidos y sin duplicados. "
                                              "MODIS o VIIRS: las detecciones originales de cada uno.")
        with st.container(border=True):
            st.markdown("**Tipo de incendio**")
            st.caption("Según la temperatura que mide el satélite en el píxel")
            tipos = st.pills("Tipos", inc.CLAVES, default=inc.CLAVES, selection_mode="multi", key="tipos",
                             format_func=lambda c: f"{inc.NOMBRE[c]} · {inc.rango_texto(c)}",
                             label_visibility="collapsed")
        with st.container(border=True):
            st.markdown("**Mapa**")
            tipo_mapa = st.segmented_control("Tipo de mapa", ["Satélite", "Relieve", "Oscuro", "3D"],
                                             default="Satélite", key="tipo_mapa", label_visibility="collapsed")
            if tipo_mapa == "3D":
                exageracion = st.slider("Exagerar el relieve", 1.0, 3.0, 1.6, 0.1, key="exag")
                textura3d = st.segmented_control("Superficie", ["Satélite", "Sombreado"], default="Satélite",
                                                 key="textura3d")
            else:
                capas = st.pills("Capas", ["focos", "temperatura", "viento", "prioridad"],
                                 default=["focos", "temperatura", "viento"], selection_mode="multi", key="capas",
                                 format_func=lambda c: {"focos": "Focos", "temperatura": "Temperatura del aire",
                                                        "viento": "Viento", "prioridad": "Zonas prioritarias"}[c])


    # ---- focos ----
    if st.session_state.get("fuente", "En vivo") == "En vivo" and tr.hay_clave_firms():
        r = tr.focos_en_vivo(st.session_state.get("dias", 1))
        origen = "Focos: NASA FIRMS en vivo"
        conjunto, individual = r.get("datos"), r.get("individual")
        if r["errores"]:
            st.toast("Algunas fuentes de FIRMS no respondieron: " + "; ".join(r["errores"])[:200])
    else:
        mes_sel = st.session_state.get("mes", 9)
        h = tr.focos_historicos(2025, mes_sel)
        conjunto, individual = h["datos"], h["individual"]
        origen = ("Focos: datos de ejemplo" if h["origen"] == "mock" else "Focos: historial procesado") + \
            f", {MESES[mes_sel]} 2025"
        if st.session_state.get("fuente", "En vivo") == "En vivo":
            origen += " (falta la clave de FIRMS para ver focos en vivo)"

    vista_sel = st.session_state.get("vista") or "Conjunto"
    if vista_sel == "Conjunto":
        focos = conjunto
    else:
        focos = individual[individual["sensor_visto"] == vista_sel] if individual is not None else None
    focos = mapas.preparar_focos(focos)
    sel = st.session_state.get("tipos") or []
    visibles = focos[focos["tipo"].isin(sel) | ((focos["tipo"] == "sin_dato") & (len(sel) == len(inc.CLAVES)))]

    with centro:
        conteo = visibles["tipo"].value_counts()
        chips = " ".join(inc_chip(c, int(conteo.get(c, 0))) for c in inc.CLAVES)
        st.markdown(f'<div class="tb-leyenda"><strong style="color:#FFFFFF;font-size:16px">{len(visibles):,}'
                    f' focos</strong> {chips}</div>'.replace(",", "."), unsafe_allow_html=True)
        tipo_mapa_sel = st.session_state.get("tipo_mapa") or "Satélite"
        if tipo_mapa_sel == "3D":
            st.pydeck_chart(mapas.mapa_3d(visibles, st.session_state.get("exag", 1.6),
                                          st.session_state.get("textura3d") or "Satélite"),
                            height=640, use_container_width=True)
            st.caption("Arrastra con clic derecho (o dos dedos) para girar e inclinar. La altura de cada columna "
                       "indica la potencia del fuego (FRP). Relieve: AWS Terrain Tiles · Imagen: Esri.")
        else:
            capas_sel = set(st.session_state.get("capas") or [])
            grilla = tr.clima_en_grilla() if capas_sel & {"temperatura", "viento"} else None
            prioridad, _ = tr.historico("prioridad.parquet", "prioridad")
            m = mapas.mapa_2d(visibles, tipo_mapa_sel, capas_sel, grilla, prioridad, tr.celdas_geojson())
            st_folium(m, height=640, use_container_width=True, returned_objects=[], key=f"mapa2d_{tipo_mapa_sel}")
            if "temperatura" in capas_sel:
                st.markdown(f'<div style="display:flex;align-items:center;gap:10px" class="tb-etq">0 °C'
                            f'<div style="flex:1;height:8px;border-radius:4px;background:{inc.DEGRADADO_AIRE}"></div>'
                            f'36 °C · temperatura del aire ahora</div>', unsafe_allow_html=True)
        st.markdown('<div class="tb-leyenda" style="margin-top:6px">'
                    '<span><svg width="14" height="14"><circle cx="7" cy="7" r="5" fill="#F97316" stroke="#fff" '
                    'stroke-width="2"/></svg>Ambos sensores</span>'
                    '<span><svg width="14" height="14"><circle cx="7" cy="7" r="4" fill="#F97316"/></svg>VIIRS · 375 m</span>'
                    '<span><svg width="14" height="14"><rect x="2" y="2" width="10" height="10" fill="#F97316" '
                    'transform="rotate(45 7 7)"/></svg>MODIS · 1 km</span></div>', unsafe_allow_html=True)
        tema.estado_datos(origen)

    # ---- situación actual ----
    with der:
        sector = st.selectbox("Sector", list(tr.SECTORES), key="sector")
        p = tr.pronostico(*tr.SECTORES[sector])
        if p is None:
            st.warning("No se pudo consultar el clima. Se reintentará en la próxima actualización.")
        else:
            a = p["actual"]
            t, hr, v = a["temperature_2m"], a["relative_humidity_2m"], a["wind_speed_10m"]
            st.markdown('<div class="tb-grid2">' + "".join([
                tema.tarjeta("Temperatura", f"{t:.0f} °C", f"a {p['elevacion']:.0f} m", inc.color_aire(t)),
                tema.tarjeta("Humedad", f"{hr:.0f} %", "muy seca" if hr < 30 else "normal"),
                tema.tarjeta("Viento", f"{v:.0f} km/h", f"del {inc.punto_cardinal(a['wind_direction_10m'])}"),
                tema.tarjeta("Ráfagas", f"{a['wind_gusts_10m']:.0f} km/h", f"lluvia {a['precipitation']:.1f} mm"),
            ]) + "</div>", unsafe_allow_html=True)
            regla = st.session_state.get("regla", inc.REGLA_RECOMENDADA)
            nivel, fondo, _ = inc.nivel_riesgo(t, hr, v, regla)
            st.write("")
            tono = "fuego" if nivel in ("muy alto", "alto") else "ok"
            tema.aviso(f"<b>Riesgo {nivel}</b><br>Regla: {regla['temp']} °C · {regla['humedad']} % · "
                       f"{regla['viento']} km/h. Se cumplen {inc.puntos_riesgo(t, hr, v, regla)} de 3.", tono)

        st.write("")
        with st.container(border=True):
            st.markdown("**¿Quién está mirando?**")
            horas_sin = (tr.ahora() - tr.ultimo_paso()).total_seconds() / 3600
            proximos = tr.proximos_pasos(4)
            if horas_sin >= 2:
                tema.aviso(f"Punto ciego: el último paso fue hace {horas_sin:.0f} h. El próximo es a las "
                           f"{proximos[0]['hora']:%H:%M}.", "ciego")
            filas = "".join(f'<div class="tb-fila"><span>{x["satelite"]} · {x["sensor"]}</span>'
                            f'<strong style="color:#8CC8FF">{x["hora"]:%H:%M}</strong></div>' for x in proximos)
            st.markdown(filas, unsafe_allow_html=True)
            st.caption("Horarios aproximados de paso sobre el parque.")


def inc_chip(clave: str, n: int) -> str:
    return tema.chip(f"{inc.NOMBRE[clave]}: {n}", inc.COLOR[clave], inc.COLOR_TEXTO[clave])


mapa_y_situacion()
