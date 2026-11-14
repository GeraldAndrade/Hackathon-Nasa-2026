import pandas as pd
import streamlit as st

import incendios as inc
import tema
import tiempo_real as tr

ORDEN_TIPOS = {c: i for i, c in enumerate(inc.CLAVES)}
st.session_state.setdefault("regla", dict(inc.REGLA_RECOMENDADA))
st.session_state.setdefault("atendidas", set())
st.session_state.setdefault("enviadas", set())
for _k, _v in inc.REGLA_RECOMENDADA.items():
    st.session_state.setdefault(f"r_{_k}", st.session_state["regla"][_k])

st.markdown("## Alertas")
st.caption("Avisos automáticos cuando el clima se vuelve peligroso o aparece un foco en el parque.")


def _usar_recomendados():
    for k, v in inc.REGLA_RECOMENDADA.items():
        st.session_state[f"r_{k}"] = v


with st.container(border=True):
    titulo, boton = st.columns([4, 1.3], vertical_alignment="bottom")
    titulo.markdown("### Cuándo enviar una alerta de clima")
    titulo.markdown("Se envía cuando se cumplen **las tres condiciones a la vez**. El valor prudente recomendado "
                    "es la **regla 30-30-30**: más de 30 °C, menos de 30 % de humedad y viento de más de 30 km/h.")
    boton.button("Usar valores recomendados", on_click=_usar_recomendados, use_container_width=True)
    c1, c2, c3 = st.columns(3, gap="large")
    t = c1.slider("Temperatura del aire, desde (°C)", 15, 40, key="r_temp")
    h = c2.slider("Humedad relativa, hasta (%)", 10, 60, step=5, key="r_humedad")
    v = c3.slider("Viento, desde (km/h)", 10, 60, step=5, key="r_viento")
    st.session_state["regla"] = {"temp": t, "humedad": h, "viento": v}
    c1.markdown(f'<div style="height:6px;border-radius:3px;background:{inc.DEGRADADO_AIRE}"></div>',
                unsafe_allow_html=True)

    sector_cal = st.selectbox("Calibrar con el clima real de la temporada 2025 en", list(tr.SECTORES),
                              key="sector_cal")
    hist = tr.clima_historico(*tr.SECTORES[sector_cal], "2025-07-01", "2025-10-31")
    if hist is not None:
        cumple = (hist.temperature_2m_max >= t) & (hist.relative_humidity_2m_min <= h) & (hist.wind_speed_10m_max >= v)
        dos_de_tres = ((hist.temperature_2m_max >= t).astype(int) + (hist.relative_humidity_2m_min <= h).astype(int)
                       + (hist.wind_speed_10m_max >= v).astype(int)) >= 2
        if cumple.sum() == 0:
            consejo = (f"Con esta regla no habría sonado ninguna alerta en {sector_cal}: la máxima de la temporada fue "
                       f"{hist.temperature_2m_max.max():.0f} °C. En zonas altas conviene bajar la temperatura.")
        elif cumple.sum() > 40:
            consejo = "Son muchas alertas: la gente puede dejar de leerlas."
        else:
            consejo = "Equilibrio razonable entre avisar a tiempo y no saturar."
        tema.aviso(f"Entre julio y octubre de 2025 esta regla se habría cumplido <b>{int(cumple.sum())} días</b> "
                   f"en {sector_cal} (y {int(dos_de_tres.sum())} días con 2 de 3 condiciones). {consejo}", "info")
    else:
        st.caption("No se pudo consultar el clima histórico para calibrar.")

izq, der = st.columns([1.7, 1], gap="large")

with der:
    with st.container(border=True):
        st.markdown("**Quién recibe y cómo**")
        if tr.hay_telegram():
            st.success("Telegram conectado")
        else:
            st.info("Para enviar de verdad, crea un bot con @BotFather y guarda `TELEGRAM_BOT_TOKEN` y "
                    "`TELEGRAM_CHAT_ID` en `.streamlit/secrets.toml`. Mientras tanto se muestra la vista previa.")
        minimo = st.selectbox("Avisar de focos desde", inc.CLAVES, index=1, key="tipo_min",
                              format_func=lambda c: f"{inc.NOMBRE[c]} ({inc.rango_texto(c)})")
        sectores = st.multiselect("Sectores para el clima", list(tr.SECTORES),
                                  default=["Sur · Quillacollo alto", "Norte · Tiquipaya alto"], key="sectores_alerta")
        auto = st.toggle("Enviar automáticamente las alertas nuevas", value=False, key="auto_envio",
                         disabled=not tr.hay_telegram())
        if st.button("Enviar alerta de prueba", type="primary", use_container_width=True):
            ok, msg = tr.enviar_telegram("🔥 <b>Prueba · Tunari Blindspot</b>\nLas alertas están configuradas.")
            (st.success if ok else st.warning)(msg)


def _ventanas(horas: pd.DataFrame, regla: dict) -> list[dict]:
    """Agrupa horas consecutivas que cumplen la regla completa."""
    ok = horas[(horas.temperature_2m >= regla["temp"]) & (horas.relative_humidity_2m <= regla["humedad"])
               & (horas.wind_speed_10m >= regla["viento"])]
    ventanas, actual = [], None
    for fila in ok.itertuples():
        if actual and fila.time - actual["fin"] <= pd.Timedelta(hours=1):
            actual["fin"] = fila.time
            actual["tmax"] = max(actual["tmax"], fila.temperature_2m)
            actual["hmin"] = min(actual["hmin"], fila.relative_humidity_2m)
            actual["vmax"] = max(actual["vmax"], fila.wind_gusts_10m)
        else:
            actual = {"inicio": fila.time, "fin": fila.time, "tmax": fila.temperature_2m,
                      "hmin": fila.relative_humidity_2m, "vmax": fila.wind_gusts_10m}
            ventanas.append(actual)
    return ventanas


@st.fragment(run_every=f"{st.session_state.get('intervalo_min', 10)}m")
def historial():
    regla = st.session_state["regla"]
    alertas = []

    # 1. Clima: ventanas de las próximas 48 h que cumplen la regla
    for sector in st.session_state.get("sectores_alerta", []):
        p = tr.pronostico(*tr.SECTORES[sector])
        if p is None:
            continue
        horas = p["horas"][p["horas"]["time"] >= pd.Timestamp(tr.ahora().replace(tzinfo=None)).floor("h")].head(48)
        for w in _ventanas(horas, regla):
            alertas.append({
                "id": f"clima-{sector}-{w['inicio']:%Y%m%d%H}", "orden": 1, "chip": ("Clima", "#33404F", "#FFFFFF"),
                "tipo": "Clima", "cuando": w["inicio"],
                "titulo": f"Regla de clima superada en {sector}",
                "detalle": f"Del {w['inicio']:%d/%m %H:%M} al {w['fin']:%H:%M}: hasta {w['tmax']:.0f} °C, humedad de "
                           f"{w['hmin']:.0f} % y ráfagas de {w['vmax']:.0f} km/h. Evita quemas y reporta humo al 119."})

    # 2. Focos nuevos de las últimas 24 h (solo con FIRMS conectado)
    if tr.hay_clave_firms():
        r = tr.focos_en_vivo(1)
        focos = r.get("datos")
        if focos is not None and len(focos):
            focos = focos.assign(tipo=inc.clasificar(focos.get("temp_brillo", pd.Series(dtype=float))))
            for f in focos.itertuples():
                if f.tipo == "sin_dato" or ORDEN_TIPOS[f.tipo] < ORDEN_TIPOS[st.session_state.get("tipo_min", "baja")]:
                    continue
                cuando = pd.to_datetime(f.fecha_hora, utc=True).tz_convert("America/La_Paz")
                visto = {"ambos": "MODIS y VIIRS", "VIIRS": "VIIRS", "MODIS": "MODIS"}[f.sensor_visto]
                alertas.append({
                    "id": f"foco-{f.id_unificado}-{cuando:%Y%m%d%H%M}", "orden": 0,
                    "chip": (f"{inc.NOMBRE[f.tipo]} · {inc.k_a_c(f.temp_brillo):.0f} °C", inc.COLOR[f.tipo],
                             inc.COLOR_TEXTO[f.tipo]),
                    "tipo": "Foco nuevo", "cuando": cuando.tz_localize(None),
                    "titulo": f"{inc.NOMBRE[f.tipo]} en ({f.latitud:.3f}, {f.longitud:.3f})",
                    "detalle": f"Visto por {visto} a las {cuando:%H:%M}. Potencia {f.frp:.0f} MW. "
                               f"{inc.SUELE_SER[f.tipo]}. Qué hacer: {inc.QUE_HACER[f.tipo].lower()}."})

    # 3. Punto ciego con riesgo
    horas_sin = (tr.ahora() - tr.ultimo_paso()).total_seconds() / 3600
    p0 = tr.pronostico(*tr.SECTORES["Sur · Quillacollo alto"])
    if p0 is not None and horas_sin >= 2:
        a = p0["actual"]
        pts = inc.puntos_riesgo(a["temperature_2m"], a["relative_humidity_2m"], a["wind_speed_10m"], regla)
        if pts >= 2:
            prox = tr.proximos_pasos(1)[0]
            alertas.append({
                "id": f"ciego-{tr.ahora():%Y%m%d%H}", "orden": 2, "chip": ("Punto ciego", "#C9A227", "#0A0E13"),
                "tipo": "Punto ciego", "cuando": tr.ahora().replace(tzinfo=None),
                "titulo": "Riesgo alto y ningún satélite mirando",
                "detalle": f"Último paso hace {horas_sin:.0f} h; el próximo es {prox['satelite']} a las "
                           f"{prox['hora']:%H:%M}. Se sugiere un recorrido en terreno."})

    # Envío automático de lo nuevo
    if st.session_state.get("auto_envio") and tr.hay_telegram():
        for a in alertas:
            if a["id"] not in st.session_state["enviadas"]:
                ok, _ = tr.enviar_telegram(f"<b>{a['titulo']}</b>\n{a['detalle']}")
                if ok:
                    st.session_state["enviadas"].add(a["id"])

    filtro = st.segmented_control("Filtrar", ["Todas", "Focos", "Clima", "Puntos ciegos"], default="Todas",
                                  key="filtro_alertas") or "Todas"
    mapa_filtro = {"Focos": "Foco nuevo", "Clima": "Clima", "Puntos ciegos": "Punto ciego"}
    lista = [a for a in alertas if filtro == "Todas" or a["tipo"] == mapa_filtro[filtro]]
    lista.sort(key=lambda a: (a["orden"], a["cuando"]))

    pendientes = sum(a["id"] not in st.session_state["atendidas"] for a in alertas)
    st.markdown(f"**{pendientes} pendientes** de {len(alertas)} alertas activas")
    if not tr.hay_clave_firms():
        st.caption("Las alertas de focos nuevos aparecen cuando se configura la clave de NASA FIRMS.")
    if not lista:
        tema.aviso("No hay alertas activas con tus reglas en este momento.", "ok")
    for a in lista:
        hecha = a["id"] in st.session_state["atendidas"]
        with st.container(border=True):
            st.markdown(f'{tema.chip(*a["chip"])} <span class="tb-etq">{a["tipo"]} · {a["cuando"]:%d/%m %H:%M}'
                        f' · {"Atendida" if hecha else "Pendiente"}'
                        f'{" · enviada" if a["id"] in st.session_state["enviadas"] else ""}</span>',
                        unsafe_allow_html=True)
            st.markdown(f"**{a['titulo']}**  \n{a['detalle']}")
            if not hecha and st.button("Marcar como atendida", key=f"at-{a['id']}"):
                st.session_state["atendidas"].add(a["id"])
                st.rerun(scope="fragment")
    tema.estado_datos("Focos: NASA FIRMS" if tr.hay_clave_firms() else "Focos: sin clave de FIRMS")


with izq:
    st.markdown("### Historial")
    historial()

with der:
    with st.container(border=True):
        st.markdown("**Así llega el mensaje**")
        r = st.session_state["regla"]
        st.markdown(f'<div style="background:#18202A;border-radius:14px 14px 14px 4px;padding:12px 14px;'
                    f'font-size:14px;line-height:1.55"><b>Alerta de clima · Tunari</b><br>'
                    f'Mañana a las 15:00: {r["temp"] + 1} °C, {max(r["humedad"] - 10, 5)} % de humedad y viento de '
                    f'{r["viento"] + 4} km/h. Supera tu regla de {r["temp"]} °C · {r["humedad"]} % · {r["viento"]} km/h.'
                    f'<br>Evita quemas y reporta humo al 119.</div>', unsafe_allow_html=True)
