"""P2 · Armonización de focos de calor MODIS y VIIRS.

Entrada:  limpio.parquet   (salida de P1, columnas crudas de FIRMS o ya normalizadas)
Salida:   unificada.parquet

Columnas de salida (contrato del equipo):
    id_unificado, latitud, longitud, fecha_hora (UTC), sensor_visto, confianza, frp
Columnas extra (opcionales, la interfaz puede ignorarlas):
    satelite, temp_brillo (K), id_origen (id de la fila de limpio), frp_modis, id_modis,
    distancia_km, desfase_min

Idea del algoritmo
------------------
VIIRS ve con píxeles de 375 m y MODIS con píxeles de ~1 km, así que VIIRS da la
ubicación más precisa. Por eso:

1. Se normalizan ambos sensores al mismo formato (coordenadas, hora UTC,
   confianza en tres niveles).
2. Cada detección MODIS se compara con las detecciones VIIRS cercanas en
   espacio (radio en km) y en tiempo (ventana en minutos).
3. Si hay coincidencia, la detección MODIS es un duplicado: se elimina y las
   detecciones VIIRS que la confirman quedan marcadas como "ambos".
4. Las detecciones VIIRS sin pareja quedan como "VIIRS" y las MODIS sin pareja
   como "MODIS".

Así no se encadenan incendios distintos y no se pierde la resolución de VIIRS.

Confianza armonizada
--------------------
MODIS entrega un porcentaje (0-100) y VIIRS una categoría (l, n, h). Se usa la
equivalencia oficial de FIRMS para MODIS:
    0-29 -> baja,  30-79 -> nominal,  80-100 -> alta
y para VIIRS:  l -> baja,  n -> nominal,  h -> alta.

Uso
---
    python src/armonizacion.py
    python src/armonizacion.py --entrada data/processed/limpio.parquet --radio-km 1.5 --ventana-min 60
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
ENTRADA_POR_DEFECTO = RAIZ / "data" / "processed" / "limpio.parquet"
SALIDA_POR_DEFECTO = RAIZ / "data" / "processed" / "unificada.parquet"

RADIO_KM = 1.5       # MODIS ~1 km en nadir, más grande hacia los bordes del barrido
VENTANA_MIN = 60     # Aqua y S-NPP/NOAA-20 pasan con minutos de diferencia

COLUMNAS_CONTRATO = [
    "id_unificado", "latitud", "longitud", "fecha_hora",
    "sensor_visto", "confianza", "frp",
]
NIVELES_CONFIANZA = ["baja", "nominal", "alta"]

_SATELITES = {
    "T": "Terra", "A": "Aqua", "Terra": "Terra", "Aqua": "Aqua",
    "N": "S-NPP", "1": "NOAA-20", "N20": "NOAA-20", "2": "NOAA-21", "N21": "NOAA-21",
}


# ---------------------------------------------------------------------------
# 1. Normalización
# ---------------------------------------------------------------------------

def _sensor_de_fila(df: pd.DataFrame) -> pd.Series:
    """Devuelve 'MODIS' o 'VIIRS' para cada fila, venga de donde venga."""
    for col in ("sensor", "sensor_origen", "instrument"):
        if col in df.columns:
            texto = df[col].astype(str).str.upper()
            return np.where(texto.str.contains("MODIS"), "MODIS",
                            np.where(texto.str.contains("VIIRS"), "VIIRS", None))
    raise ValueError("No se encontró columna de sensor (sensor, sensor_origen o instrument).")


def confianza_armonizada(valor) -> str | None:
    """Convierte la confianza de MODIS (0-100) o VIIRS (l/n/h) a baja/nominal/alta."""
    if pd.isna(valor):
        return None
    texto = str(valor).strip().lower()
    if texto in NIVELES_CONFIANZA:
        return texto
    if texto in ("l", "low"):
        return "baja"
    if texto in ("n", "nominal"):
        return "nominal"
    if texto in ("h", "high"):
        return "alta"
    try:
        numero = float(texto)
    except ValueError:
        return None
    if numero < 30:
        return "baja"
    if numero < 80:
        return "nominal"
    return "alta"


def _fecha_hora_utc(df: pd.DataFrame) -> pd.Series:
    if "fecha_hora" in df.columns:
        return pd.to_datetime(df["fecha_hora"], utc=True)
    # FIRMS: acq_date = 'YYYY-MM-DD', acq_time = HHMM en UTC (a veces sin ceros a la izquierda)
    hhmm = df["acq_time"].astype(int).astype(str).str.zfill(4)
    return pd.to_datetime(
        df["acq_date"].astype(str) + " " + hhmm.str[:2] + ":" + hhmm.str[2:],
        format="%Y-%m-%d %H:%M", utc=True,
    )


def _temp_brillo(df: pd.DataFrame, sensor) -> pd.Series:
    """Temperatura de brillo del píxel en kelvin.

    MODIS la entrega en `brightness` (canal 21/22) y VIIRS en `bright_ti4`
    (canal I4, se satura cerca de 367 K). Si no hay dato queda vacía.
    """
    if "temp_brillo" in df.columns:
        return pd.to_numeric(df["temp_brillo"], errors="coerce")
    vacia = pd.Series(np.nan, index=df.index)
    modis = pd.to_numeric(df["brightness"], errors="coerce") if "brightness" in df.columns else vacia
    viirs = pd.to_numeric(df["bright_ti4"], errors="coerce") if "bright_ti4" in df.columns else vacia
    return pd.Series(np.where(np.asarray(sensor) == "MODIS", modis, viirs), index=df.index, dtype=float)


def normalizar(df: pd.DataFrame) -> pd.DataFrame:
    """Lleva la tabla de P1 (cruda de FIRMS o ya con el contrato) a un formato común."""
    salida = pd.DataFrame(index=df.index)
    lat = df["latitud"] if "latitud" in df.columns else df["latitude"]
    lon = df["longitud"] if "longitud" in df.columns else df["longitude"]
    salida["latitud"] = pd.to_numeric(lat, errors="coerce")
    salida["longitud"] = pd.to_numeric(lon, errors="coerce")
    salida["fecha_hora"] = _fecha_hora_utc(df)
    salida["sensor"] = _sensor_de_fila(df)

    conf_col = "confianza" if "confianza" in df.columns else "confidence"
    salida["confianza"] = df[conf_col].map(confianza_armonizada)
    salida["frp"] = pd.to_numeric(df["frp"], errors="coerce")
    salida["temp_brillo"] = _temp_brillo(df, salida["sensor"])

    if "satellite" in df.columns:
        salida["satelite"] = df["satellite"].astype(str).map(lambda s: _SATELITES.get(s, s))
    elif "satelite" in df.columns:
        salida["satelite"] = df["satelite"]
    else:
        salida["satelite"] = None

    if "id" in df.columns:
        salida["id"] = df["id"].astype(str)
    else:
        salida["id"] = [f"{s[0]}{i:06d}" for i, s in enumerate(salida["sensor"].fillna("X"))]

    salida = salida.dropna(subset=["latitud", "longitud", "fecha_hora", "sensor"])
    # Duplicados exactos (misma fila descargada dos veces)
    salida = salida.drop_duplicates(subset=["sensor", "satelite", "latitud", "longitud", "fecha_hora"])
    return salida.reset_index(drop=True)


# ---------------------------------------------------------------------------
# 2. Emparejamiento MODIS <-> VIIRS
# ---------------------------------------------------------------------------

def _haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def emparejar(modis: pd.DataFrame, viirs: pd.DataFrame,
              radio_km: float = RADIO_KM, ventana_min: float = VENTANA_MIN) -> pd.DataFrame:
    """Devuelve todos los pares (MODIS, VIIRS) dentro del radio y la ventana de tiempo.

    Columnas: idx_modis, idx_viirs, distancia_km, desfase_min
    """
    vacio = pd.DataFrame(columns=["idx_modis", "idx_viirs", "distancia_km", "desfase_min"])
    if modis.empty or viirs.empty:
        return vacio

    viirs = viirs.sort_values("fecha_hora")
    t_viirs = viirs["fecha_hora"].dt.tz_convert(None).to_numpy().astype("datetime64[s]").astype(np.int64)
    lat_v = viirs["latitud"].to_numpy()
    lon_v = viirs["longitud"].to_numpy()
    idx_v = viirs.index.to_numpy()
    ventana_s = ventana_min * 60

    pares = []
    for idx_m, fila in modis.iterrows():
        t_m = np.datetime64(fila["fecha_hora"].tz_convert(None), "s").astype(np.int64)
        ini = np.searchsorted(t_viirs, t_m - ventana_s, side="left")
        fin = np.searchsorted(t_viirs, t_m + ventana_s, side="right")
        if ini == fin:
            continue
        dist = _haversine_km(fila["latitud"], fila["longitud"], lat_v[ini:fin], lon_v[ini:fin])
        cerca = dist <= radio_km
        for j in np.flatnonzero(cerca):
            pares.append((idx_m, idx_v[ini + j], float(dist[j]),
                          abs(t_viirs[ini + j] - t_m) / 60.0))

    if not pares:
        return vacio
    return pd.DataFrame(pares, columns=vacio.columns)


# ---------------------------------------------------------------------------
# 3. Tabla unificada
# ---------------------------------------------------------------------------

def armonizar(limpio: pd.DataFrame, radio_km: float = RADIO_KM,
              ventana_min: float = VENTANA_MIN) -> pd.DataFrame:
    datos = normalizar(limpio)
    modis = datos[datos["sensor"] == "MODIS"]
    viirs = datos[datos["sensor"] == "VIIRS"]

    pares = emparejar(modis, viirs, radio_km, ventana_min)

    # Para cada VIIRS confirmado nos quedamos con el MODIS más cercano
    mejor_por_viirs = (pares.sort_values(["idx_viirs", "distancia_km"])
                       .drop_duplicates("idx_viirs")
                       .set_index("idx_viirs"))

    v = viirs.copy()
    v["sensor_visto"] = np.where(v.index.isin(mejor_por_viirs.index), "ambos", "VIIRS")
    v["id_modis"] = mejor_por_viirs["idx_modis"].reindex(v.index).map(
        lambda i: modis.at[i, "id"] if pd.notna(i) else None)
    v["frp_modis"] = mejor_por_viirs["idx_modis"].reindex(v.index).map(
        lambda i: modis.at[i, "frp"] if pd.notna(i) else np.nan)
    v["distancia_km"] = mejor_por_viirs["distancia_km"].reindex(v.index)
    v["desfase_min"] = mejor_por_viirs["desfase_min"].reindex(v.index)

    # MODIS sin pareja VIIRS: se conservan como detección propia
    m = modis[~modis.index.isin(pares["idx_modis"])].copy()
    m["sensor_visto"] = "MODIS"
    m["id_modis"] = m["id"]
    m["frp_modis"] = m["frp"]
    m["distancia_km"] = np.nan
    m["desfase_min"] = np.nan

    unificada = pd.concat([v, m], ignore_index=True).sort_values("fecha_hora")
    unificada["id_unificado"] = [f"U{i:06d}" for i in range(1, len(unificada) + 1)]
    unificada["confianza"] = pd.Categorical(unificada["confianza"],
                                            categories=NIVELES_CONFIANZA, ordered=True)

    unificada["id_origen"] = unificada["id"]
    extras = ["satelite", "temp_brillo", "id_origen", "frp_modis", "id_modis", "distancia_km", "desfase_min"]
    return unificada[COLUMNAS_CONTRATO + extras].reset_index(drop=True)


def resumen(unificada: pd.DataFrame, n_modis_original: int) -> str:
    conteo = unificada["sensor_visto"].value_counts()
    n_ambos_modis = n_modis_original - conteo.get("MODIS", 0)
    lineas = [
        f"Detecciones unificadas: {len(unificada)}",
        f"  vistas por ambos sensores (filas VIIRS): {conteo.get('ambos', 0)}",
        f"  solo VIIRS: {conteo.get('VIIRS', 0)}",
        f"  solo MODIS: {conteo.get('MODIS', 0)}",
        f"Detecciones MODIS absorbidas como duplicado: {n_ambos_modis} de {n_modis_original}",
    ]
    return "\n".join(lineas)


def main() -> None:
    parser = argparse.ArgumentParser(description="Armoniza focos MODIS y VIIRS.")
    parser.add_argument("--entrada", type=Path, default=ENTRADA_POR_DEFECTO)
    parser.add_argument("--salida", type=Path, default=SALIDA_POR_DEFECTO)
    parser.add_argument("--radio-km", type=float, default=RADIO_KM)
    parser.add_argument("--ventana-min", type=float, default=VENTANA_MIN)
    args = parser.parse_args()

    limpio = pd.read_parquet(args.entrada)
    if "geometry" in limpio.columns:
        limpio = limpio.drop(columns="geometry")

    unificada = armonizar(limpio, args.radio_km, args.ventana_min)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    unificada.to_parquet(args.salida, index=False)

    n_modis = int((normalizar(limpio)["sensor"] == "MODIS").sum())
    print(resumen(unificada, n_modis))
    print(f"Guardado en {args.salida}")


if __name__ == "__main__":
    main()
