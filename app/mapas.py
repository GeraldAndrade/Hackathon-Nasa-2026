"""Mapa 2D (satélite, relieve u oscuro) con Folium y mapa 3D del relieve con pydeck."""

from __future__ import annotations

import folium
import numpy as np
import pandas as pd
import pydeck as pdk

import incendios as inc
import tiempo_real as tr

TEXTURA_SATELITE = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
ATRIB_SATELITE = "Imágenes: Esri, Maxar, Earthstar Geographics"
RELIEVE_TERRARIUM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"

BASES = {
    "Satélite": (TEXTURA_SATELITE, ATRIB_SATELITE),
    "Relieve": ("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
                "Mapa: © OpenStreetMap, SRTM | Estilo: © OpenTopoMap (CC-BY-SA)"),
    "Oscuro": ("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", "© OpenStreetMap © CARTO"),
}

COCHABAMBA = (-17.3895, -66.157)
CERRO_TUNARI = (-17.2856, -66.3858)


def _texto_foco(f) -> str:
    hora = pd.to_datetime(f.fecha_hora, utc=True).tz_convert("America/La_Paz").strftime("%d/%m %H:%M")
    temp = f"{inc.k_a_c(f.temp_brillo):.0f} °C" if pd.notna(f.temp_brillo) else "sin dato"
    visto = {"ambos": "MODIS y VIIRS", "VIIRS": "solo VIIRS", "MODIS": "solo MODIS"}.get(f.sensor_visto, f.sensor_visto)
    return (f"<b>{inc.NOMBRE.get(f.tipo, 'Sin dato de temperatura')}</b><br>"
            f"Temperatura del píxel: {temp}<br>Potencia: {f.frp:.1f} MW<br>"
            f"Visto por: {visto}<br>{hora} (hora de Bolivia)")


def preparar_focos(focos: pd.DataFrame) -> pd.DataFrame:
    if focos is None or focos.empty:
        return pd.DataFrame(columns=["latitud", "longitud", "tipo", "sensor_visto", "frp", "temp_brillo", "fecha_hora"])
    f = focos.copy()
    if "temp_brillo" not in f.columns:
        f["temp_brillo"] = np.nan
    f["tipo"] = inc.clasificar(f["temp_brillo"])
    return f


# ---------------------------------------------------------------------------
# 2D
# ---------------------------------------------------------------------------

def mapa_2d(focos: pd.DataFrame, base: str, capas: set[str], grilla: pd.DataFrame | None,
            prioridad: pd.DataFrame | None, celdas: dict | None) -> folium.Map:
    m = folium.Map(location=tr.CENTRO, zoom_start=10, tiles=None, control_scale=True)
    for nombre, (url, atrib) in BASES.items():
        folium.TileLayer(url, attr=atrib, name=nombre, overlay=False, control=True,
                         show=(nombre == base), max_zoom=18).add_to(m)

    anillo = tr.limite_parque()
    if anillo:
        folium.PolyLine([(la, lo) for lo, la in anillo], color="#86E0A0", weight=2.5,
                        tooltip="Parque Nacional Tunari").add_to(m)

    if "temperatura" in capas and grilla is not None:
        g = folium.FeatureGroup(name="Temperatura del aire", show=True)
        dla, dlo = grilla.attrs.get("paso_lat", 0.1) / 2, grilla.attrs.get("paso_lon", 0.1) / 2
        for p in grilla.itertuples():
            folium.Rectangle(bounds=[(p.lat - dla, p.lon - dlo), (p.lat + dla, p.lon + dlo)],
                             color=None, weight=0, fill=True, fill_color=inc.color_aire(p.temp), fill_opacity=0.38,
                             tooltip=f"{p.temp:.0f} °C a {p.elevacion:.0f} m").add_to(g)
        g.add_to(m)

    if "viento" in capas and grilla is not None:
        g = folium.FeatureGroup(name="Viento", show=True)
        for p in grilla.itertuples():
            hacia = (p.dir + 180) % 360  # el viento "del norte" sopla hacia el sur
            largo = 14 + min(p.viento, 50) * 0.6
            svg = (f'<svg width="40" height="40" viewBox="-20 -20 40 40" style="transform:rotate({hacia}deg)">'
                   f'<line x1="0" y1="{largo/2}" x2="0" y2="{-largo/2}" stroke="white" stroke-width="2.2" stroke-linecap="round"/>'
                   f'<path d="M0 {-largo/2 - 3} L-5 {-largo/2 + 5} L5 {-largo/2 + 5} Z" fill="white"/></svg>')
            folium.Marker((p.lat, p.lon), icon=folium.DivIcon(html=svg, icon_size=(40, 40), icon_anchor=(20, 20)),
                          tooltip=f"Viento del {inc.punto_cardinal(p.dir)}, {p.viento:.0f} km/h").add_to(g)
        g.add_to(m)

    if "prioridad" in capas and prioridad is not None and celdas is not None:
        p = prioridad.dropna(subset=["prioridad"])
        if len(p):
            corte = p["prioridad"].quantile(0.9)
            top = p[p["prioridad"] >= corte].set_index("celda_id")["prioridad"]
            maximo = top.max()
            feats = [f for f in celdas["features"] if f["properties"]["celda_id"] in top.index]
            for f in feats:
                f["properties"]["prioridad"] = round(float(top[f["properties"]["celda_id"]]), 2)
            folium.GeoJson(
                {"type": "FeatureCollection", "features": feats}, name="Zonas prioritarias",
                style_function=lambda f: {"color": "#FF7A2F", "weight": 1.2, "fillColor": "#FF7A2F",
                                          "fillOpacity": 0.15 + 0.45 * f["properties"]["prioridad"] / maximo},
                tooltip=folium.GeoJsonTooltip(["prioridad"], aliases=["Prioridad de vigilancia"]),
            ).add_to(m)

    if "focos" in capas:
        g = folium.FeatureGroup(name="Focos de calor", show=True)
        for f in focos.itertuples():
            color = inc.COLOR.get(f.tipo, "#A9BACB")
            popup = folium.Popup(_texto_foco(f), max_width=260)
            if f.sensor_visto == "MODIS":
                rombo = (f'<div style="width:11px;height:11px;background:{color};border:1px solid #0A0E13;'
                         f'transform:rotate(45deg)"></div>')
                folium.Marker((f.latitud, f.longitud), popup=popup,
                              icon=folium.DivIcon(html=rombo, icon_size=(13, 13), icon_anchor=(6, 6))).add_to(g)
            else:
                ambos = f.sensor_visto == "ambos"
                folium.CircleMarker((f.latitud, f.longitud), radius=6 if ambos else 4.5,
                                    color="#FFFFFF" if ambos else "#0A0E13", weight=2 if ambos else 1,
                                    fill=True, fill_color=color, fill_opacity=0.95, popup=popup).add_to(g)
        g.add_to(m)

    folium.CircleMarker(COCHABAMBA, radius=6, color="#FFFFFF", fill=True, fill_opacity=1,
                        tooltip="Cochabamba").add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    return m


# ---------------------------------------------------------------------------
# 3D
# ---------------------------------------------------------------------------

def mapa_3d(focos: pd.DataFrame, exageracion: float = 1.6, textura: str = "Satélite") -> pdk.Deck:
    k = exageracion
    capas = [pdk.Layer(
        "TerrainLayer",
        elevation_decoder={"rScaler": 256 * k, "gScaler": 1 * k, "bScaler": k / 256, "offset": -32768 * k},
        elevation_data=RELIEVE_TERRARIUM,
        texture=TEXTURA_SATELITE if textura == "Satélite" else None,
        color=[60, 70, 80],
        max_zoom=14,
    )]

    anillo = tr.limite_parque()
    if anillo:
        paso = max(1, len(anillo) // 250)
        pts = anillo[::paso] + [anillo[0]]
        alturas = tr.elevaciones(tuple(p[1] for p in pts), tuple(p[0] for p in pts))
        camino = [[p[0], p[1], z * k + 40] for p, z in zip(pts, alturas)]
        capas.append(pdk.Layer("PathLayer", data=[{"camino": camino}], get_path="camino",
                               get_color=[134, 224, 160], width_min_pixels=3))

    if focos is not None and len(focos):
        f = focos.head(800).copy()
        z = tr.elevaciones(tuple(f["latitud"].round(4)), tuple(f["longitud"].round(4)))
        f["z"] = np.asarray(z) * k + 20
        f["alto"] = 250 + f["frp"].fillna(5).clip(0, 150) * 25
        f["color"] = [_rgb(inc.COLOR.get(t, "#A9BACB")) for t in f["tipo"]]
        f["base"] = f.apply(lambda r: [r.longitud, r.latitud, r.z], axis=1)
        f["punta"] = f.apply(lambda r: [r.longitud, r.latitud, r.z + r.alto], axis=1)
        f["nombre"] = f["tipo"].map(inc.NOMBRE).fillna("Sin dato")
        f["temp_c"] = (f["temp_brillo"] - 273.15).round(0)
        f["visto"] = f["sensor_visto"].map({"ambos": "MODIS y VIIRS", "VIIRS": "solo VIIRS", "MODIS": "solo MODIS"})
        f = f.drop(columns=["fecha_hora"], errors="ignore")
        capas.append(pdk.Layer("ColumnLayer", data=f, get_position="base", get_elevation="alto",
                               get_fill_color="color", radius=110, disk_resolution=12, extruded=True,
                               elevation_scale=1, pickable=True))
        capas.append(pdk.Layer("ScatterplotLayer", data=f, get_position="punta", get_fill_color="color",
                               get_line_color=[255, 255, 255], stroked=True, line_width_min_pixels=1,
                               get_radius=180, radius_min_pixels=4, pickable=True))

    etiquetas = [
        {"pos": [COCHABAMBA[1], COCHABAMBA[0], 2560 * k + 300], "texto": "Cochabamba"},
        {"pos": [CERRO_TUNARI[1], CERRO_TUNARI[0], 5035 * k + 400], "texto": "Cerro Tunari · 5.035 m"},
    ]
    capas.append(pdk.Layer("TextLayer", data=etiquetas, get_position="pos", get_text="texto", get_size=15,
                           get_color=[255, 255, 255], get_alignment_baseline="'bottom'",
                           background=True, get_background_color=[10, 14, 19, 200]))

    vista = pdk.ViewState(latitude=-17.36, longitude=-66.36, zoom=10.1, pitch=60, bearing=-20, max_pitch=75)
    return pdk.Deck(layers=capas, initial_view_state=vista, map_style=None,
                    tooltip={"html": "<b>{nombre}</b><br>{temp_c} °C · {frp} MW<br>Visto por: {visto}",
                             "style": {"backgroundColor": "#11161D", "color": "#E8EEF4"}})


def _rgb(hexa: str) -> list[int]:
    hexa = hexa.lstrip("#")
    return [int(hexa[i:i + 2], 16) for i in (0, 2, 4)] + [235]
