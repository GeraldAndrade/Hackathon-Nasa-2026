"""Genera datos de ejemplo (falsos) con la misma forma que FIRMS para el Tunari.

Sirve para desarrollar y probar la armonización, el análisis y la interfaz
mientras P1 descarga el historial real.

Qué simula
----------
* Incendios dentro del límite real del parque (firms/limite.geojson), más
  frecuentes en algunos sectores "calientes" para que haya recurrencia.
* Temporada seca: casi todos entre julio y octubre.
* Pasos reales de cada satélite (hora de Bolivia = UTC-4):
    Terra (MODIS)   ~10:30 y ~22:30
    Aqua  (MODIS)   ~13:30 y ~01:30
    S-NPP / NOAA-20 / NOAA-21 (VIIRS) ~13:30 y ~01:30, separados por 25-50 min
* Nubes o fuera de franja: cada paso puede no observar.
* Incendios chicos: VIIRS (375 m) los ve, MODIS (1 km) muchas veces no.
* Algunas falsas alarmas aisladas de un solo sensor.

Salidas en data/mock/
---------------------
* limpio.parquet     mismo formato que el de P1 (columnas crudas de FIRMS +
                     sensor_origen). Incluye `id` y `_evento` (el incendio
                     real que causó cada detección, para validar).
* unificada.parquet  resultado de src/armonizacion.py sobre el mock.

Uso:  python src/generar_mock.py [--semilla 42] [--anios 2021 2025]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from armonizacion import armonizar, resumen

RAIZ = Path(__file__).resolve().parents[1]
LIMITE = RAIZ / "firms" / "limite.geojson"
SALIDA = RAIZ / "data" / "mock"

KM_POR_GRADO = 111.0

# Hora UTC aproximada (en horas decimales) de cada paso y su satélite
PASOS = [
    # sensor_origen,   satélite, instrumento, hora UTC
    ("modis",        "T", "MODIS", 14.5),   # Terra día   10:30 local
    ("modis",        "T", "MODIS", 2.5),    # Terra noche 22:30 local (día siguiente UTC)
    ("modis",        "A", "MODIS", 17.5),   # Aqua día    13:30 local
    ("modis",        "A", "MODIS", 5.5),    # Aqua noche  01:30 local
    ("viirs_snpp",   "N", "VIIRS", 17.6),
    ("viirs_snpp",   "N", "VIIRS", 5.6),
    ("viirs_noaa20", "1", "VIIRS", 16.8),
    ("viirs_noaa20", "1", "VIIRS", 4.8),
    ("viirs_noaa21", "2", "VIIRS", 17.2),
    ("viirs_noaa21", "2", "VIIRS", 5.2),
]
# NOAA-21 empezó a entregar datos a inicios de 2023
INICIO_SATELITE = {"2": pd.Timestamp("2023-01-01")}

# Probabilidad de que un paso observe la zona (nubes, borde de franja, etc.)
P_OBSERVA = 0.65
# Probabilidad de detección según tamaño del incendio
P_DETECTA = {
    "chico":   {"MODIS": 0.25, "VIIRS": 0.85},
    "mediano": {"MODIS": 0.70, "VIIRS": 0.95},
    "grande":  {"MODIS": 0.95, "VIIRS": 0.99},
}
PIXELES_VIIRS = {"chico": (1, 2), "mediano": (2, 4), "grande": (4, 9)}
DIAS_ACTIVO = {"chico": (1, 1), "mediano": (1, 3), "grande": (2, 5)}


# ---------------------------------------------------------------------------
# Geometría sin dependencias (punto dentro de polígono por ray casting)
# ---------------------------------------------------------------------------

def cargar_limite(ruta: Path = LIMITE) -> np.ndarray:
    geo = json.loads(ruta.read_text(encoding="utf-8"))["features"][0]["geometry"]
    anillo = geo["coordinates"][0] if geo["type"] == "Polygon" else geo["coordinates"][0][0]
    return np.asarray(anillo, dtype=float)  # (n, 2) lon, lat


def dentro(lon: np.ndarray, lat: np.ndarray, anillo: np.ndarray) -> np.ndarray:
    lon = np.atleast_1d(lon)
    lat = np.atleast_1d(lat)
    x1, y1 = anillo[:-1, 0], anillo[:-1, 1]
    x2, y2 = anillo[1:, 0], anillo[1:, 1]
    resultado = np.zeros(lon.shape, dtype=bool)
    for k in range(len(lon)):
        cruza = ((y1 > lat[k]) != (y2 > lat[k])) & (
            lon[k] < (x2 - x1) * (lat[k] - y1) / (y2 - y1 + 1e-15) + x1)
        resultado[k] = cruza.sum() % 2 == 1
    return resultado


def puntos_aleatorios(n: int, anillo: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    xmin, ymin = anillo.min(axis=0)
    xmax, ymax = anillo.max(axis=0)
    puntos = []
    while len(puntos) < n:
        lon = rng.uniform(xmin, xmax, n * 3)
        lat = rng.uniform(ymin, ymax, n * 3)
        ok = dentro(lon, lat, anillo)
        puntos.extend(zip(lon[ok], lat[ok]))
    return np.asarray(puntos[:n])


def desplazar(lon, lat, km, rng, n=1):
    """Desplaza un punto una distancia aleatoria (gaussiana, sigma=km)."""
    dlat = rng.normal(0, km, n) / KM_POR_GRADO
    dlon = rng.normal(0, km, n) / (KM_POR_GRADO * np.cos(np.radians(lat)))
    return lon + dlon, lat + dlat


# ---------------------------------------------------------------------------
# Simulación
# ---------------------------------------------------------------------------

def _fecha_temporada(anio: int, rng: np.random.Generator) -> pd.Timestamp:
    # 85 % en temporada seca (jul-oct), el resto en cualquier mes
    if rng.random() < 0.85:
        inicio = pd.Timestamp(f"{anio}-07-01")
        dias = rng.normal(75, 25)  # pico a mediados de septiembre
        dias = float(np.clip(dias, 0, 122))
    else:
        inicio = pd.Timestamp(f"{anio}-01-01")
        dias = rng.uniform(0, 364)
    return inicio + pd.Timedelta(days=int(dias))


def _fila_modis(lat, lon, t, sat, rng, tamano, evento, de_dia):
    frp = {"chico": 8, "mediano": 25, "grande": 80}[tamano] * rng.lognormal(0, 0.5)
    conf = int(np.clip(rng.normal({"chico": 45, "mediano": 70, "grande": 90}[tamano], 15), 0, 100))
    scan = round(float(rng.uniform(1.0, 2.5)), 1)
    return {
        "latitude": round(float(lat), 4), "longitude": round(float(lon), 4),
        "brightness": round(float(rng.uniform(310, 360)), 1),
        "scan": scan, "track": round(scan * rng.uniform(0.7, 1.0), 1),
        "acq_date": t.strftime("%Y-%m-%d"), "acq_time": int(t.strftime("%H%M")),
        "satellite": sat, "instrument": "MODIS", "confidence": conf,
        "version": "6.1", "bright_t31": round(float(rng.uniform(285, 305)), 1),
        "frp": round(float(frp), 1), "daynight": "D" if de_dia else "N",
        "bright_ti4": None, "bright_ti5": None,
        "sensor_origen": "modis", "_evento": evento,
    }


def _fila_viirs(lat, lon, t, sat, origen, rng, tamano, evento, de_dia):
    frp = {"chico": 2, "mediano": 6, "grande": 15}[tamano] * rng.lognormal(0, 0.6)
    conf = rng.choice(["l", "n", "h"], p={"chico": [0.3, 0.6, 0.1],
                                          "mediano": [0.1, 0.6, 0.3],
                                          "grande": [0.05, 0.45, 0.5]}[tamano])
    scan = round(float(rng.uniform(0.37, 0.6)), 2)
    return {
        "latitude": round(float(lat), 5), "longitude": round(float(lon), 5),
        "brightness": None, "scan": scan, "track": round(scan * rng.uniform(0.8, 1.0), 2),
        "acq_date": t.strftime("%Y-%m-%d"), "acq_time": int(t.strftime("%H%M")),
        "satellite": sat, "instrument": "VIIRS", "confidence": conf,
        "version": "2.0NRT", "bright_t31": None,
        "frp": round(float(frp), 2), "daynight": "D" if de_dia else "N",
        "bright_ti4": round(float(rng.uniform(320, 367)), 2),
        "bright_ti5": round(float(rng.uniform(285, 305)), 2),
        "sensor_origen": origen, "_evento": evento,
    }


def simular(anios=(2021, 2025), incendios_por_anio=45, semilla=42) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    anillo = cargar_limite()

    # Sectores calientes: la mitad de los incendios ocurre cerca de ellos
    calientes = puntos_aleatorios(6, anillo, rng)

    filas = []
    evento = 0
    for anio in range(anios[0], anios[1] + 1):
        n = int(rng.poisson(incendios_por_anio))
        for _ in range(n):
            evento += 1
            if rng.random() < 0.5:
                c = calientes[rng.integers(len(calientes))]
                for _intento in range(20):
                    lon, lat = desplazar(c[0], c[1], 2.0, rng)
                    if dentro(lon, lat, anillo)[0]:
                        break
                lon, lat = float(lon[0]), float(lat[0])
            else:
                lon, lat = puntos_aleatorios(1, anillo, rng)[0]

            tamano = rng.choice(["chico", "mediano", "grande"], p=[0.5, 0.35, 0.15])
            inicio = _fecha_temporada(anio, rng)
            dias = int(rng.integers(DIAS_ACTIVO[tamano][0], DIAS_ACTIVO[tamano][1] + 1))

            for d in range(dias):
                dia = inicio + pd.Timedelta(days=d)
                # el frente avanza un poco cada día
                lon_d, lat_d = desplazar(lon, lat, 0.3 * d, rng)
                lon_d, lat_d = float(lon_d[0]), float(lat_d[0])
                for origen, sat, instr, hora in PASOS:
                    if sat in INICIO_SATELITE and dia < INICIO_SATELITE[sat]:
                        continue
                    if rng.random() > P_OBSERVA:
                        continue
                    if rng.random() > P_DETECTA[tamano][instr]:
                        continue
                    t = dia + pd.Timedelta(hours=hora + rng.normal(0, 0.15))
                    de_dia = 12 <= hora <= 22
                    if instr == "MODIS":
                        mlon, mlat = desplazar(lon_d, lat_d, 0.4, rng)
                        filas.append(_fila_modis(mlat[0], mlon[0], t, sat, rng, tamano, evento, de_dia))
                    else:
                        npx = int(rng.integers(PIXELES_VIIRS[tamano][0], PIXELES_VIIRS[tamano][1] + 1))
                        vlon, vlat = desplazar(lon_d, lat_d, 0.25, rng, npx)
                        for a, b in zip(vlat, vlon):
                            filas.append(_fila_viirs(a, b, t, sat, origen, rng, tamano, evento, de_dia))

    # Falsas alarmas aisladas (un solo sensor, un solo paso): evento = 0
    for lon, lat in puntos_aleatorios(25, anillo, rng):
        origen, sat, instr, hora = PASOS[rng.integers(len(PASOS))]
        anio = int(rng.integers(anios[0], anios[1] + 1))
        t = pd.Timestamp(f"{anio}-01-01") + pd.Timedelta(days=int(rng.uniform(0, 364)), hours=hora)
        de_dia = 12 <= hora <= 22
        if instr == "MODIS":
            filas.append(_fila_modis(lat, lon, t, sat, rng, "chico", 0, de_dia))
        else:
            filas.append(_fila_viirs(lat, lon, t, sat, origen, rng, "chico", 0, de_dia))

    df = pd.DataFrame(filas)
    # MODIS da números y VIIRS letras: en una sola columna quedan como texto
    df["confidence"] = df["confidence"].astype(str)
    # Temperatura de brillo coherente con la potencia: más FRP, píxel más caliente.
    # VIIRS (canal I4) se satura cerca de 367 K.
    r = np.random.default_rng(semilla + 1)
    tb = np.clip(305 + 14 * np.log1p(df["frp"].astype(float)) + r.normal(0, 5, len(df)), 300, 395).round(1)
    es_modis = (df["instrument"] == "MODIS").to_numpy()
    df["brightness"] = np.where(es_modis, tb, np.nan)
    df["bright_ti4"] = np.where(es_modis, np.nan, np.minimum(tb, 367.0))
    df = df.sort_values(["acq_date", "acq_time"]).reset_index(drop=True)
    pref = np.where(df["instrument"] == "MODIS", "M", "V")
    df.insert(0, "id", [f"{p}{i:06d}" for i, p in enumerate(pref, start=1)])
    return df


def validar(limpio: pd.DataFrame, unificada: pd.DataFrame) -> str:
    """Compara el emparejamiento con la verdad conocida del mock."""
    evento_de = limpio.set_index("id")["_evento"]
    hora_de = pd.to_datetime(limpio["acq_date"] + " "
                             + limpio["acq_time"].astype(str).str.zfill(4),
                             format="%Y-%m-%d %H%M")
    hora_de.index = limpio["id"]
    viirs = limpio[limpio["instrument"] == "VIIRS"]

    # 1. Precisión: de los pares formados, cuántos son del mismo incendio real
    ambos = unificada[unificada["sensor_visto"] == "ambos"]
    ev_v = ambos["id_origen"].map(evento_de)
    ev_m = ambos["id_modis"].map(evento_de)
    correctos = int(((ev_v == ev_m) & (ev_v > 0)).sum())

    # 2. Cobertura: MODIS que tenían un VIIRS del mismo incendio a <=60 min
    #    (o sea, que se podían unir) y quedaron solos
    solos = unificada[unificada["sensor_visto"] == "MODIS"]
    unibles = 0
    for id_m in solos["id_origen"]:
        ev = evento_de[id_m]
        if ev == 0:
            continue
        mismos = viirs[viirs["_evento"] == ev]["id"]
        desfase = (hora_de[mismos] - hora_de[id_m]).abs().dt.total_seconds() / 60
        unibles += int((desfase <= 60).any())

    n_modis = int((limpio["instrument"] == "MODIS").sum())
    absorbidos = n_modis - len(solos)
    return "\n".join([
        "Validación contra la verdad del mock:",
        f"  filas VIIRS marcadas 'ambos': {len(ambos)}, con la pareja MODIS del mismo "
        f"incendio: {correctos} ({correctos / max(len(ambos), 1):.0%})",
        f"  MODIS absorbidos: {absorbidos} de {n_modis}",
        f"  MODIS que quedaron solos pero tenían VIIRS del mismo incendio a <=60 min: {unibles}",
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera datos de ejemplo de focos para el Tunari.")
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--anios", type=int, nargs=2, default=[2021, 2025])
    parser.add_argument("--incendios-por-anio", type=int, default=45)
    args = parser.parse_args()

    limpio = simular(tuple(args.anios), args.incendios_por_anio, args.semilla)
    SALIDA.mkdir(parents=True, exist_ok=True)
    limpio.to_parquet(SALIDA / "limpio.parquet", index=False)

    unificada = armonizar(limpio)
    unificada.to_parquet(SALIDA / "unificada.parquet", index=False)

    print(f"Detecciones simuladas: {len(limpio)} "
          f"(MODIS {int((limpio['instrument'] == 'MODIS').sum())}, "
          f"VIIRS {int((limpio['instrument'] == 'VIIRS').sum())}), "
          f"incendios: {limpio['_evento'].max()}")
    print(resumen(unificada, int((limpio["instrument"] == "MODIS").sum())))
    print(validar(limpio, unificada))
    print(f"Guardado en {SALIDA}")


if __name__ == "__main__":
    main()
