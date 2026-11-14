"""Demostración reproducible de P3; no modifica los datos de P1/P2.

Usa las detecciones mock existentes de P2 y simula una máscara INDEPENDIENTE
de evaluación de cobertura. Esta máscara no proviene de NASA ni valida el
modelo científico. Se garantiza la observación de los intervalos con focos.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from analisis import (RAIZ, ZONA_HORARIA, analizar, asignar_detecciones,
                      guardar_resultados, preparar_celdas, _periodo)


def simular_observaciones(celdas, unificada, inicio, fin, semilla=42):
    ini, termino, _ = _periodo(inicio, fin)
    dias = pd.date_range(ini, termino, freq="D")
    # ~357.000 filas para 30 días y 2.977 celdas; no se simulan cinco años
    # de observaciones para mantener la demostración liviana.
    indice = pd.MultiIndex.from_product([celdas.celda_id, dias, range(4)],
                                         names=["celda_id", "dia", "franja"])
    obs = indice.to_frame(index=False)
    rng = np.random.default_rng(semilla)
    # Gradiente espacial y horarios deliberadamente inventados.
    longitud = celdas.set_index("celda_id").longitud
    ancho = longitud.max() - longitud.min()
    espacial = ((longitud - longitud.min()) / ancho if ancho > 0 else longitud * 0 + 0.5)
    prob = (obs.celda_id.map(espacial).to_numpy() * 0.30
            + np.take([0.30, 0.08, 0.48, 0.12], obs.franja))
    obs["observada"] = rng.random(len(obs)) < prob
    asignadas, _, _ = asignar_detecciones(unificada, celdas, ini, termino)
    activos = pd.MultiIndex.from_frame(asignadas[["celda_id", "dia", "franja"]].drop_duplicates())
    obs["observada"] |= indice.isin(activos)
    # Una fila resume el estado de la unión de sensores del intervalo, no un
    # sobrevuelo concreto. En datos reales se necesita una máscara equivalente.
    hora_local = obs.dia + pd.to_timedelta(obs.franja * 6, unit="h")
    obs["fecha_hora"] = hora_local.dt.tz_localize(ZONA_HORARIA).dt.tz_convert("UTC")
    obs["datos_simulados"] = True
    return obs[["celda_id", "fecha_hora", "observada", "datos_simulados"]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", type=Path, default=RAIZ / "data/mock/unificada.parquet")
    parser.add_argument("--inicio", default="2025-09-01")
    parser.add_argument("--fin", default="2025-09-30")
    parser.add_argument("--semilla", type=int, default=42)
    args = parser.parse_args()
    salida = RAIZ / "data/mock"
    celdas = preparar_celdas(gpd.read_file(RAIZ / "firms/celdas.geojson"),
                             gpd.read_file(RAIZ / "firms/limite.geojson"))
    unificada = pd.read_parquet(args.entrada)
    observaciones = simular_observaciones(celdas, unificada, args.inicio, args.fin, args.semilla)
    salida.mkdir(parents=True, exist_ok=True)
    observaciones.to_parquet(salida / "observaciones.parquet", index=False)
    resultado = analizar(unificada, celdas, args.inicio, args.fin, observaciones,
                         datos_simulados=True)
    resultado.resumen["semilla_simulacion"] = args.semilla
    resultado.resumen["archivos_entrada"] = {
        "unificada": str(args.entrada.resolve()), "observaciones": "simuladas por generar_demo_analisis.py"}
    resultado.resumen["advertencias"].append(
        "Máscara de cobertura simulada y condicionada a las detecciones; no valida cobertura real.")
    guardar_resultados(resultado, celdas, salida / "prioridad.parquet", salida / "graficos")
    print("SIMULACIÓN: observaciones de cobertura inventadas; no usar en operaciones.")
    print(f"{len(observaciones)} intervalos; {resultado.resumen['detecciones_asignadas']} detecciones "
          f"en el período; {resultado.resumen['celdas_con_prioridad']} puntajes.")
    print(f"Informe: {salida / 'graficos/informe.html'}")


if __name__ == "__main__":
    main()
