"""Tema oscuro y piezas visuales compartidas por las páginas."""

from __future__ import annotations

import html

import streamlit as st

import tiempo_real as tr

CSS = """
<style>
.block-container{padding-top:1.2rem;padding-bottom:3rem;max-width:1440px}
h1,h2,h3{font-family:'Space Grotesk','Inter',sans-serif!important;letter-spacing:-.01em}
[data-testid="stMetric"]{background:#11161D;border:1px solid #1E2630;border-radius:14px;padding:14px 16px}
[data-testid="stMetricLabel"] p{color:#A9BACB!important;font-size:13px!important}
[data-testid="stMetricValue"]{font-family:'Space Grotesk',sans-serif;font-size:28px!important}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:16px!important;border-color:#1E2630!important;background:#11161D}
.tb-tarjeta{background:#11161D;border:1px solid #1E2630;border-radius:14px;padding:14px 16px;height:100%}
.tb-grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px}
.tb-etq{color:#A9BACB;font-size:12.5px}
.tb-grande{font-family:'Space Grotesk',sans-serif;font-size:22px;white-space:nowrap;font-weight:600;color:#FFFFFF}
.tb-chip{display:inline-block;font-size:12px;font-weight:700;border-radius:999px;padding:3px 10px;white-space:nowrap}
.tb-aviso{border-radius:12px;padding:12px 14px;font-size:14px;line-height:1.5}
.tb-fila{display:flex;justify-content:space-between;gap:8px;padding:8px 0;border-bottom:1px solid #1E2630;font-size:14px}
.tb-fila:last-child{border-bottom:none}
.tb-leyenda{display:flex;flex-wrap:wrap;gap:8px 16px;font-size:13px;color:#C9D4E0;align-items:center}
.tb-leyenda span{display:inline-flex;align-items:center;gap:6px}
.tb-sw{width:12px;height:12px;border-radius:3px;display:inline-block}
.tb-dia{display:grid;grid-template-columns:64px 92px minmax(120px,1fr);gap:6px 14px;align-items:center;padding:10px 4px;border-bottom:1px solid #1E2630}
.tb-dia .tb-extra{grid-column:2/-1;display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center}
.tb-pista{position:relative;height:8px;border-radius:4px;background:#1A212B;flex:1 1 auto}
.tb-horas{display:grid;grid-template-columns:repeat(24,minmax(0,1fr));gap:4px;min-width:620px}
.tb-scroll{overflow-x:auto}
@media (max-width:720px){
  .st-key-mapa_layout [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2){order:-1}
  .block-container{padding-left:.8rem;padding-right:.8rem}
  .tb-dia{grid-template-columns:56px 76px minmax(0,1fr)}
  [data-testid="stMetricValue"]{font-size:22px!important}
}
</style>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
"""


def aplicar_tema() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def e(texto) -> str:
    return html.escape(str(texto))


def chip(texto: str, fondo: str, color: str = "#0A0E13") -> str:
    return f'<span class="tb-chip" style="background:{fondo};color:{color}">{e(texto)}</span>'


def tarjeta(etiqueta: str, valor: str, nota: str = "", color_valor: str = "#FFFFFF") -> str:
    return (f'<div class="tb-tarjeta"><div class="tb-etq">{e(etiqueta)}</div>'
            f'<div class="tb-grande" style="color:{color_valor}">{valor}</div>'
            f'<div class="tb-etq">{e(nota)}</div></div>')


def aviso(texto_html: str, tono: str = "fuego") -> None:
    tonos = {
        "fuego": ("#2A120A", "#FF7A2F", "#FFE1D0"),
        "ciego": ("#231E0C", "#C9A227", "#F6E3A1"),
        "ok": ("#0E2A1C", "#3FB97A", "#C8F2DA"),
        "info": ("#0F2236", "#5AB0FF", "#CDE6FF"),
    }
    fondo, borde, color = tonos[tono]
    st.markdown(f'<div class="tb-aviso" style="background:{fondo};border:1px solid {borde};color:{color}">'
                f'{texto_html}</div>', unsafe_allow_html=True)


def estado_datos(origen_focos: str) -> None:
    """Línea de estado con la hora de la última consulta."""
    hora = tr.ahora().strftime("%H:%M:%S")
    intervalo = st.session_state.get("intervalo_min", 10)
    st.caption(f"{origen_focos} · Clima: Open-Meteo · Última consulta {hora} · "
               f"se actualiza sola cada {intervalo} min")
