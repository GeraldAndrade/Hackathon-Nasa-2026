"""Datos en tiempo real: focos de NASA FIRMS, clima de Open-Meteo y relieve.

Cada consulta se guarda en caché un tiempo corto (TTL) para que la app se
actualice sola sin saturar los servicios. Ningún servicio necesita datos
personales; FIRMS necesita una MAP_KEY gratuita que se configura como secreto.
"""

from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
from armonizacion import armonizar, normalizar  # noqa: E402

ZONA = ZoneInfo("America/La_Paz")
TTL = 300  # segundos: los datos se vuelven a pedir como mucho cada 5 minutos

# Rectángulo que cubre todo el parque (oeste, sur, este, norte)
BBOX = (-66.75, -17.56, -65.90, -16.90)
CENTRO = (-17.27, -66.33)
FUENTES_FIRMS = ["MODIS_NRT", "VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"]

SECTORES = {
    "Sur · Quillacollo alto": (-17.46, -66.46),
    "Oeste · Sipe Sipe": (-17.26, -66.62),
    "Norte · Tiquipaya alto": (-17.14, -66.38),
    "Noreste · Sacaba alto": (-17.06, -66.18),
    "Centro · Cerro Tunari": (-17.29, -66.39),
}

# Pasos aproximados sobre el Tunari en hora local. Para horarios exactos se
# necesitarían las órbitas del día (TLE); esto alcanza para avisar puntos ciegos.
PASOS = [
    ("NOAA-20", "VIIRS", "00:50"), ("NOAA-21", "VIIRS", "01:15"), ("Aqua", "MODIS", "01:30"),
    ("S-NPP", "VIIRS", "01:35"), ("Terra", "MODIS", "10:30"), ("NOAA-20", "VIIRS", "12:50"),
    ("NOAA-21", "VIIRS", "13:15"), ("Aqua", "MODIS", "13:30"), ("S-NPP", "VIIRS", "13:35"),
    ("Terra", "MODIS", "22:30"),
]

_SESION = requests.Session()
_SESION.headers["User-Agent"] = "TunariBlindspot/1.0 (NASA Space Apps)"


def ahora() -> datetime:
    return datetime.now(ZONA)


def _secreto(nombre: str) -> str | None:
    try:
        valor = st.secrets.get(nombre)
    except Exception:  # sin archivo de secretos
        valor = None
    if not valor:  # la app puede lanzarse desde otra carpeta: leer el secrets.toml del repo
        ruta = RAIZ / ".streamlit" / "secrets.toml"
        if ruta.exists():
            import tomllib
            try:
                valor = tomllib.loads(ruta.read_text(encoding="utf-8")).get(nombre)
            except Exception:
                valor = None
    return valor or os.environ.get(nombre)


# ---------------------------------------------------------------------------
# Límite del parque
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def limite_parque() -> list[list[float]]:
    """Anillo exterior del parque como lista de [lon, lat]."""
    for ruta in (RAIZ / "data" / "processed" / "limite.geojson", RAIZ / "firms" / "limite.geojson"):
        if ruta.exists():
            geo = json.loads(ruta.read_text(encoding="utf-8"))["features"][0]["geometry"]
            anillo = geo["coordinates"][0] if geo["type"] == "Polygon" else geo["coordinates"][0][0]
            return [list(map(float, p[:2])) for p in anillo]
    return []


def dentro_del_parque(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    anillo = np.asarray(limite_parque())
    if len(anillo) == 0:
        return np.ones(len(lon), dtype=bool)
    x1, y1, x2, y2 = anillo[:-1, 0], anillo[:-1, 1], anillo[1:, 0], anillo[1:, 1]
    res = np.zeros(len(lon), dtype=bool)
    for i, (x, y) in enumerate(zip(lon, lat)):
        cruza = ((y1 > y) != (y2 > y)) & (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-15) + x1)
        res[i] = cruza.sum() % 2 == 1
    return res


# ---------------------------------------------------------------------------
# Focos en vivo (NASA FIRMS)
# ---------------------------------------------------------------------------

def hay_clave_firms() -> bool:
    return bool(_secreto("FIRMS_MAP_KEY"))


@st.cache_data(ttl=TTL, show_spinner=False)
def _descargar_firms(clave: str, dias: int) -> tuple[pd.DataFrame, list[str]]:
    area = ",".join(str(v) for v in BBOX)
    partes, errores = [], []
    for fuente in FUENTES_FIRMS:
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{clave}/{fuente}/{area}/{dias}"
        try:
            r = _SESION.get(url, timeout=25)
            r.raise_for_status()
            texto = r.text.strip()
            if not texto or texto.lower().startswith(("invalid", "error")):
                errores.append(f"{fuente}: {texto[:80]}")
                continue
            df = pd.read_csv(io.StringIO(texto))
            if not df.empty:
                df["sensor_origen"] = fuente.lower()
                partes.append(df)
        except Exception as e:  # red caída, clave inválida, límite de consultas
            errores.append(f"{fuente}: {type(e).__name__}")
    crudo = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
    return crudo, errores


def focos_en_vivo(dias: int = 1) -> dict:
    """Focos de los últimos `dias` días dentro del parque, ya armonizados."""
    clave = _secreto("FIRMS_MAP_KEY")
    if not clave:
        return {"ok": False, "motivo": "sin_clave", "datos": None, "errores": []}
    crudo, errores = _descargar_firms(clave, dias)
    if crudo.empty:
        return {"ok": not errores, "motivo": "sin_focos" if not errores else "error",
                "datos": _vacio(), "individual": _vacio(), "errores": errores, "crudos": 0}
    crudo = crudo[dentro_del_parque(crudo["longitude"].to_numpy(), crudo["latitude"].to_numpy())]
    if crudo.empty:
        return {"ok": True, "motivo": "sin_focos", "datos": _vacio(), "individual": _vacio(),
                "errores": errores, "crudos": 0}
    return {"ok": True, "motivo": "ok", "datos": armonizar(crudo), "individual": individual(crudo),
            "errores": errores, "crudos": len(crudo)}


def individual(crudo: pd.DataFrame) -> pd.DataFrame:
    """Detecciones originales de cada sensor, sin unir (para ver MODIS o VIIRS por separado)."""
    d = normalizar(crudo).rename(columns={"sensor": "sensor_visto", "id": "id_unificado"})
    return d


def _vacio() -> pd.DataFrame:
    return pd.DataFrame(columns=["id_unificado", "latitud", "longitud", "fecha_hora", "sensor_visto",
                                 "confianza", "frp", "satelite", "temp_brillo"])


# ---------------------------------------------------------------------------
# Datos históricos (salidas de P2 y P3)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def historico(nombre: str, columna_util: str | None = None) -> tuple[pd.DataFrame | None, str]:
    """Lee data/processed/<nombre> si tiene datos útiles; si no, el ejemplo de data/mock.

    `columna_util`: si se indica, el archivo solo sirve cuando esa columna tiene algún valor.
    """
    for carpeta in ("processed", "mock"):
        ruta = RAIZ / "data" / carpeta / nombre
        if ruta.exists():
            df = pd.read_parquet(ruta)
            if len(df) and (columna_util is None or df[columna_util].notna().any()):
                return df, carpeta
    return None, "ninguno"


@st.cache_data(show_spinner=False)
def focos_historicos(anio: int, mes: int) -> dict:
    """Focos armonizados e individuales de un mes, desde los archivos de P1/P2 (o el ejemplo)."""
    unificada, origen = historico("unificada.parquet")
    if unificada is None:
        return {"datos": _vacio(), "individual": _vacio(), "origen": "ninguno"}
    local = pd.to_datetime(unificada["fecha_hora"], utc=True).dt.tz_convert(ZONA)
    conjunto = unificada[(local.dt.year == anio) & (local.dt.month == mes)]
    limpio = None
    for carpeta in ([origen, "mock"] if origen != "mock" else ["mock"]):
        ruta = RAIZ / "data" / carpeta / "limpio.parquet"
        if ruta.exists() and len(pd.read_parquet(ruta)):
            limpio = pd.read_parquet(ruta)
            break
    ind = individual(limpio) if limpio is not None else _vacio()
    if len(ind):
        loc = pd.to_datetime(ind["fecha_hora"], utc=True).dt.tz_convert(ZONA)
        ind = ind[(loc.dt.year == anio) & (loc.dt.month == mes)]
    return {"datos": conjunto, "individual": ind, "origen": origen}


@st.cache_data(show_spinner=False)
def celdas_geojson() -> dict | None:
    for carpeta in ("processed", "mock"):
        ruta = RAIZ / "data" / carpeta / "celdas_analisis.geojson"
        if ruta.exists():
            return json.loads(ruta.read_text(encoding="utf-8"))
    return None


# ---------------------------------------------------------------------------
# Clima (Open-Meteo, sin clave)
# ---------------------------------------------------------------------------

_HORARIAS = "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_gusts_10m,wind_direction_10m,precipitation"
_DIARIAS = ("temperature_2m_max,temperature_2m_min,relative_humidity_2m_min,wind_speed_10m_max,"
            "wind_gusts_10m_max,wind_direction_10m_dominant,precipitation_sum")


@st.cache_data(ttl=TTL, show_spinner=False)
def pronostico(lat: float, lon: float) -> dict | None:
    params = {"latitude": lat, "longitude": lon, "timezone": "America/La_Paz", "forecast_days": 7,
              "current": _HORARIAS, "hourly": _HORARIAS, "daily": _DIARIAS, "wind_speed_unit": "kmh"}
    try:
        r = _SESION.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=20)
        r.raise_for_status()
        j = r.json()
    except Exception:
        return None
    horas = pd.DataFrame(j["hourly"])
    horas["time"] = pd.to_datetime(horas["time"])
    dias = pd.DataFrame(j["daily"])
    dias["time"] = pd.to_datetime(dias["time"])
    return {"actual": j["current"], "horas": horas, "dias": dias, "elevacion": j.get("elevation"),
            "consultado": ahora()}


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def clima_historico(lat: float, lon: float, inicio: str, fin: str) -> pd.DataFrame | None:
    """Clima diario observado (reanálisis ERA5) para calibrar las reglas de alerta."""
    params = {"latitude": lat, "longitude": lon, "start_date": inicio, "end_date": fin,
              "timezone": "America/La_Paz", "wind_speed_unit": "kmh",
              "daily": "temperature_2m_max,relative_humidity_2m_min,wind_speed_10m_max"}
    try:
        r = _SESION.get("https://archive-api.open-meteo.com/v1/archive", params=params, timeout=30)
        r.raise_for_status()
        d = pd.DataFrame(r.json()["daily"])
    except Exception:
        return None
    d["time"] = pd.to_datetime(d["time"])
    return d


def enviar_telegram(texto: str) -> tuple[bool, str]:
    """Envía un mensaje al chat o grupo configurado en los secretos."""
    token, chat = _secreto("TELEGRAM_BOT_TOKEN"), _secreto("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return False, "Falta configurar TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID"
    try:
        r = _SESION.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         json={"chat_id": chat, "text": texto, "parse_mode": "HTML"}, timeout=15)
        ok = r.ok and r.json().get("ok", False)
        return ok, "Enviado" if ok else r.text[:120]
    except Exception as e:
        return False, type(e).__name__


def hay_telegram() -> bool:
    return bool(_secreto("TELEGRAM_BOT_TOKEN") and _secreto("TELEGRAM_CHAT_ID"))


@st.cache_data(ttl=TTL, show_spinner=False)
def clima_en_grilla(filas: int = 6, columnas: int = 8) -> pd.DataFrame | None:
    """Temperatura y viento actuales en una grilla sobre el parque (una sola consulta)."""
    oeste, sur, este, norte = BBOX
    lats = np.linspace(sur, norte, filas)
    lons = np.linspace(oeste, este, columnas)
    puntos = [(la, lo) for la in lats for lo in lons]
    params = {"latitude": ",".join(f"{p[0]:.4f}" for p in puntos),
              "longitude": ",".join(f"{p[1]:.4f}" for p in puntos),
              "current": "temperature_2m,wind_speed_10m,wind_direction_10m", "timezone": "America/La_Paz"}
    try:
        r = _SESION.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=25)
        r.raise_for_status()
        j = r.json()
    except Exception:
        return None
    j = j if isinstance(j, list) else [j]
    df = pd.DataFrame([{"lat": p[0], "lon": p[1], "temp": d["current"]["temperature_2m"],
                        "viento": d["current"]["wind_speed_10m"], "dir": d["current"]["wind_direction_10m"],
                        "elevacion": d.get("elevation")} for p, d in zip(puntos, j)])
    df.attrs["paso_lat"] = float(lats[1] - lats[0])
    df.attrs["paso_lon"] = float(lons[1] - lons[0])
    return df


@st.cache_data(show_spinner=False)
def elevaciones(lats: tuple, lons: tuple) -> list[float]:
    """Altura (m) de cada punto, en lotes de 100 (Open-Meteo, modelo Copernicus 90 m)."""
    salida: list[float] = []
    for i in range(0, len(lats), 100):
        params = {"latitude": ",".join(f"{v:.5f}" for v in lats[i:i + 100]),
                  "longitude": ",".join(f"{v:.5f}" for v in lons[i:i + 100])}
        try:
            r = _SESION.get("https://api.open-meteo.com/v1/elevation", params=params, timeout=20)
            r.raise_for_status()
            salida.extend(float(v) for v in r.json()["elevation"])
        except Exception:
            salida.extend([3000.0] * len(lats[i:i + 100]))
    return salida


# ---------------------------------------------------------------------------
# Pasos de satélite y puntos ciegos
# ---------------------------------------------------------------------------

def proximos_pasos(n: int = 5) -> list[dict]:
    t = ahora()
    lista = []
    for dia in (0, 1):
        base = (t + timedelta(days=dia)).date()
        for sat, sensor, hhmm in PASOS:
            h, m = map(int, hhmm.split(":"))
            cuando = datetime(base.year, base.month, base.day, h, m, tzinfo=ZONA)
            if cuando > t:
                lista.append({"satelite": sat, "sensor": sensor, "hora": cuando})
    return sorted(lista, key=lambda p: p["hora"])[:n]


def ultimo_paso() -> datetime:
    t = ahora()
    candidatos = []
    for dia in (0, -1):
        base = (t + timedelta(days=dia)).date()
        for _, _, hhmm in PASOS:
            h, m = map(int, hhmm.split(":"))
            cuando = datetime(base.year, base.month, base.day, h, m, tzinfo=ZONA)
            if cuando <= t:
                candidatos.append(cuando)
    return max(candidatos)


def limpiar_cache() -> None:
    _descargar_firms.clear()
    pronostico.clear()
    clima_en_grilla.clear()
