"""Reglas compartidas: tipos de incendio por temperatura, colores y riesgo del clima."""

from __future__ import annotations

import numpy as np
import pandas as pd

# Tipos de incendio según la temperatura de brillo del píxel (kelvin).
# El satélite mide el promedio de todo el píxel (fuego + terreno), por eso los
# valores son mucho más bajos que la llama real (800-1.200 °C).
TIPOS = [
    # clave,      nombre,             desde_K, hasta_K, color,     texto,      suele_ser
    ("debil",   "Anomalía débil",     0,   320, "#FDE68A", "#0A0E13", "Brasas, suelo muy caliente o falsa alarma"),
    ("baja",    "Baja intensidad",  320,   340, "#FDBA4D", "#0A0E13", "Quema agrícola, chaqueo o pastizal"),
    ("activo",  "Incendio activo",  340,   360, "#F97316", "#0A0E13", "Matorral con frente de llamas"),
    ("intenso", "Incendio intenso", 360, 10_000, "#E11D48", "#FFFFFF", "Incendio forestal o de copa"),
]
CLAVES = [t[0] for t in TIPOS]
NOMBRE = {t[0]: t[1] for t in TIPOS}
COLOR = {t[0]: t[4] for t in TIPOS}
COLOR_TEXTO = {t[0]: t[5] for t in TIPOS}
SUELE_SER = {t[0]: t[6] for t in TIPOS}
QUE_HACER = {
    "debil": "Esperar el siguiente paso del satélite",
    "baja": "Confirmar si la quema está autorizada",
    "activo": "Enviar patrulla",
    "intenso": "Alertar a bomberos y comunidades",
}


def k_a_c(k: float) -> float:
    return k - 273.15


def rango_texto(clave: str) -> str:
    _, _, desde, hasta, *_ = next(t for t in TIPOS if t[0] == clave)
    if desde == 0:
        return f"menos de {k_a_c(hasta):.0f} °C"
    if hasta >= 10_000:
        return f"más de {k_a_c(desde):.0f} °C"
    return f"{k_a_c(desde):.0f} – {k_a_c(hasta):.0f} °C"


def clasificar(temp_k: pd.Series) -> pd.Series:
    """Devuelve la clave del tipo de incendio para cada temperatura de brillo."""
    t = pd.to_numeric(temp_k, errors="coerce")
    clase = np.select([t < 320, t < 340, t < 360, t >= 360], CLAVES, default="sin_dato")
    return pd.Series(clase, index=t.index)


# Escala de color de la temperatura del aire (°C), parecida a la de Windy.
ESCALA_AIRE = [(0, (91, 141, 239)), (10, (79, 195, 161)), (18, (198, 224, 90)), (24, (247, 201, 72)),
               (28, (245, 158, 44)), (32, (239, 90, 44)), (36, (194, 37, 92))]


def color_aire(t: float, como_lista: bool = False):
    if t is None or (isinstance(t, float) and np.isnan(t)):
        rgb = (120, 120, 120)
    else:
        rgb = ESCALA_AIRE[-1][1]
        for (t0, c0), (t1, c1) in zip(ESCALA_AIRE, ESCALA_AIRE[1:]):
            if t <= t1:
                f = max(0.0, min(1.0, (t - t0) / (t1 - t0)))
                rgb = tuple(int(a + (b - a) * f) for a, b in zip(c0, c1))
                break
    return list(rgb) if como_lista else "#%02X%02X%02X" % rgb


DEGRADADO_AIRE = ("linear-gradient(90deg, #5B8DEF 0%, #4FC3A1 28%, #C6E05A 50%, "
                  "#F7C948 67%, #F59E2C 78%, #EF5A2C 89%, #C2255C 100%)")


# Regla 30-30-30: más de 30 °C, menos de 30 % de humedad, viento de más de 30 km/h.
REGLA_RECOMENDADA = {"temp": 30, "humedad": 30, "viento": 30}
NIVELES_RIESGO = {
    3: ("muy alto", "#E11D48", "#FFFFFF"),
    2: ("alto", "#F97316", "#0A0E13"),
    1: ("moderado", "#FDBA4D", "#0A0E13"),
    0: ("bajo", "#2E7D5B", "#FFFFFF"),
}


def puntos_riesgo(temp, humedad, viento, regla=REGLA_RECOMENDADA) -> int:
    return int(temp >= regla["temp"]) + int(humedad <= regla["humedad"]) + int(viento >= regla["viento"])


def nivel_riesgo(temp, humedad, viento, regla=REGLA_RECOMENDADA):
    return NIVELES_RIESGO[puntos_riesgo(temp, humedad, viento, regla)]


def punto_cardinal(grados: float) -> str:
    nombres = ["norte", "noreste", "este", "sureste", "sur", "suroeste", "oeste", "noroeste"]
    return nombres[int(((grados % 360) + 22.5) // 45) % 8]
