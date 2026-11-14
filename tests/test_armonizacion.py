"""Pruebas rápidas de la armonización con datos inventados (formato crudo de FIRMS).

Ejecutar desde la raíz del repo:  python -m pytest tests -q
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from armonizacion import armonizar, confianza_armonizada  # noqa: E402


def _fila(sensor, sat, lat, lon, fecha, hhmm, conf, frp):
    return {
        "latitude": lat, "longitude": lon, "acq_date": fecha, "acq_time": hhmm,
        "satellite": sat, "confidence": conf, "frp": frp, "sensor_origen": sensor,
    }


def _datos():
    # dtype=object imita el limpio.parquet real de P1, donde todo llega como texto/objeto
    return pd.DataFrame(dtype=object, data=[
        # Incendio A: Aqua (MODIS) y S-NPP (VIIRS) lo ven a 500 m y 10 min de diferencia
        _fila("modis", "A", -17.300, -66.200, "2026-09-01", 1805, 85, 30.0),
        _fila("viirs_snpp", "N", -17.3035, -66.2010, "2026-09-01", 1815, "h", 12.0),
        _fila("viirs_snpp", "N", -17.2990, -66.1985, "2026-09-01", 1815, "n", 8.0),
        # Incendio B: solo VIIRS (muy pequeño para MODIS)
        _fila("viirs_noaa20", "1", -17.250, -66.100, "2026-09-02", 610, "l", 2.0),
        # Incendio C: solo MODIS (Terra, VIIRS no pasó a esa hora)
        _fila("modis", "T", -17.200, -66.300, "2026-09-03", 1430, 40, 15.0),
        # Mismo lugar que A pero al día siguiente: NO debe emparejarse
        _fila("modis", "A", -17.300, -66.200, "2026-09-02", 1805, 70, 20.0),
    ])


def test_confianza():
    assert confianza_armonizada(10) == "baja"
    assert confianza_armonizada(50) == "nominal"
    assert confianza_armonizada(95) == "alta"
    assert confianza_armonizada("n") == "nominal"
    assert confianza_armonizada("h") == "alta"


def test_armonizar():
    u = armonizar(_datos())
    conteo = u["sensor_visto"].value_counts().to_dict()
    assert conteo == {"ambos": 2, "VIIRS": 1, "MODIS": 2}
    assert u["id_unificado"].is_unique
    assert str(u["fecha_hora"].dt.tz) == "UTC"
    ambos = u[u["sensor_visto"] == "ambos"]
    assert (ambos["distancia_km"] <= 1.5).all()
    assert (ambos["desfase_min"] == 10).all()
