from pathlib import Path

import numpy as np
import pandas as pd

SALIDA = Path(__file__).resolve().parent.parent / "data" / "mock"
SALIDA.mkdir(parents=True, exist_ok=True)

rng = np.random.default_rng(42)
n = 60

fechas = pd.to_datetime("2024-08-01") + pd.to_timedelta(rng.integers(0, 90 * 24 * 60, n), unit="m")

limpio = pd.DataFrame({
    "id": np.arange(n),
    "latitud": -17.30 + rng.normal(0, 0.06, n),
    "longitud": -66.25 + rng.normal(0, 0.06, n),
    "fecha_hora": fechas,
    "sensor": rng.choice(["MODIS", "VIIRS"], n),
    "confianza": rng.choice(["baja", "nominal", "alta"], n),
    "frp": rng.gamma(2.0, 4.0, n).round(2),
})
limpio.to_parquet(SALIDA / "limpio.parquet", index=False)

unificada = limpio.rename(columns={"id": "id_unificado", "sensor": "sensor_visto"})
unificada["sensor_visto"] = rng.choice(["MODIS", "VIIRS", "ambos"], n)
unificada.to_parquet(SALIDA / "unificada.parquet", index=False)

celdas = 25
prioridad = pd.DataFrame({
    "celda_id": np.arange(celdas),
    "latitud": -17.30 + rng.uniform(-0.1, 0.1, celdas),
    "longitud": -66.25 + rng.uniform(-0.1, 0.1, celdas),
    "focos": rng.integers(0, 15, celdas),
    "cobertura": rng.uniform(0.2, 1.0, celdas).round(2),
})
prioridad["prioridad"] = (prioridad["focos"] / prioridad["focos"].max() / prioridad["cobertura"]).clip(0, 1).round(2)
prioridad.to_parquet(SALIDA / "prioridad.parquet", index=False)