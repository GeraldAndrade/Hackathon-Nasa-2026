"""P3: cobertura, recurrencia y prioridad de vigilancia del Parque Tunari.

Las detecciones FIRMS no son un inventario de observaciones sin fuego.
Sin registros independientes de observación, cobertura y prioridad son nulas.
Ver README_ANALISIS.md para el contrato, las fórmulas y sus limitaciones.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
ZONA_HORARIA = "America/La_Paz"
FRANJAS = ["00–06", "06–12", "12–18", "18–24"]
FUENTE_NASA = "https://firms2.modaps.eosdis.nasa.gov/alerts/notes.php"


@dataclass
class ResultadoAnalisis:
    prioridad: pd.DataFrame
    cobertura: pd.DataFrame
    asignaciones: pd.DataFrame
    resumen: dict


def _exigir_columnas(df, columnas, nombre):
    faltan = sorted(set(columnas) - set(df.columns))
    if faltan:
        raise ValueError(f"{nombre}: faltan columnas {faltan}.")


def preparar_celdas(celdas: gpd.GeoDataFrame,
                     limite: gpd.GeoDataFrame | None = None) -> gpd.GeoDataFrame:
    """Da IDs estables a P1 sin editarlo; recorta los bordes al parque.

    El hash depende de la geometría original, no del orden de las filas.
    Los puntos de representación y las áreas se calculan en UTM 19S.
    """
    if celdas.empty or celdas.crs is None:
        raise ValueError("La cuadrícula debe tener celdas y un CRS declarado.")
    c = celdas.to_crs(4326).copy()
    if c.geometry.isna().any() or c.geometry.is_empty.any() or not c.is_valid.all():
        raise ValueError("La cuadrícula contiene geometrías vacías o inválidas.")
    if not c.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError("La cuadrícula debe contener polígonos.")
    if "celda_id" not in c:
        c["celda_id"] = c.geometry.map(
            lambda g: "C" + hashlib.sha256(g.normalize().wkb).hexdigest()[:16])
    if c["celda_id"].isna().any():
        raise ValueError("Hay identificadores de celda vacíos.")
    c["celda_id"] = c["celda_id"].astype(str)
    if c["celda_id"].duplicated().any() or c["celda_id"].eq("").any():
        raise ValueError("Los identificadores de celda deben ser únicos y no vacíos.")
    if limite is not None:
        if limite.empty or limite.crs is None or not limite.is_valid.all():
            raise ValueError("El límite debe tener geometrías válidas y un CRS.")
        c.geometry = c.geometry.intersection(limite.to_crs(4326).geometry.union_all())
        c = c[~c.geometry.is_empty & c.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    if c.empty:
        raise ValueError("No quedaron celdas dentro del límite.")
    c = c[["celda_id", "geometry"]].sort_values("celda_id").reset_index(drop=True)
    metrica = c.to_crs(32719)
    puntos = metrica.representative_point().to_crs(4326)
    c["latitud"] = puntos.y
    c["longitud"] = puntos.x
    c["area_km2"] = metrica.area / 1e6
    return c


def _periodo(inicio, fin):
    if (inicio is None) != (fin is None):
        raise ValueError("Indica --inicio y --fin juntos (fechas locales inclusivas).")
    if inicio is None:
        return None, None, None
    ini, termino = pd.Timestamp(inicio), pd.Timestamp(fin)
    if any(t.tzinfo is not None or t != t.normalize() for t in (ini, termino)):
        raise ValueError("El período debe usar fechas locales sin hora: YYYY-MM-DD.")
    if pd.isna(ini) or pd.isna(termino) or termino < ini:
        raise ValueError("El período es inválido: fin debe ser igual o posterior a inicio.")
    return ini, termino, (termino - ini).days + 1


def _agregar_tiempo(df):
    salida = df.copy()
    salida["fecha_hora"] = pd.to_datetime(salida["fecha_hora"], utc=True, format="mixed")
    if salida["fecha_hora"].isna().any():
        raise ValueError("Hay fechas de observación o detección vacías.")
    local = salida["fecha_hora"].dt.tz_convert(ZONA_HORARIA)
    salida["dia"] = local.dt.tz_localize(None).dt.normalize()
    salida["franja"] = (local.dt.hour // 6).astype(int)
    return salida


def asignar_detecciones(unificada, celdas, inicio=None, fin=None):
    """Asigna cada punto una vez; desempata aristas por celda_id estable."""
    _exigir_columnas(unificada, ["id_unificado", "latitud", "longitud", "fecha_hora"],
                     "unificada.parquet")
    if unificada["id_unificado"].isna().any() or unificada["id_unificado"].duplicated().any():
        raise ValueError("id_unificado debe ser único y no nulo (entrada de P2).")
    d = _agregar_tiempo(unificada)
    for col, maximo in (("latitud", 90), ("longitud", 180)):
        d[col] = pd.to_numeric(d[col], errors="raise")
        if not (np.isfinite(d[col]) & d[col].between(-maximo, maximo)).all():
            raise ValueError(f"Coordenadas inválidas en {col}.")
    fuera_periodo = 0
    if inicio is not None:
        dentro = d["dia"].between(inicio, fin)
        fuera_periodo = int((~dentro).sum())
        d = d[dentro].copy()
    puntos = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d.longitud, d.latitud), crs=4326)
    puntos = puntos.reset_index(drop=True)
    puntos["_fila_p3"] = np.arange(len(puntos))
    unidos = gpd.sjoin(puntos, celdas[["celda_id", "geometry"]], how="left", predicate="intersects")
    unidos = unidos.sort_values(["_fila_p3", "celda_id"]).drop_duplicates("_fila_p3")
    fuera_parque = int(unidos["celda_id"].isna().sum())
    columnas = [col for col in d.columns if col not in ("geometry", "celda_id")]
    asignados = pd.DataFrame(unidos.loc[unidos.celda_id.notna(), columnas + ["celda_id"]])
    return asignados.reset_index(drop=True), fuera_periodo, fuera_parque


def analizar(unificada: pd.DataFrame, celdas: gpd.GeoDataFrame,
             inicio=None, fin=None, observaciones: pd.DataFrame | None = None,
             peso_recurrencia: float = 0.6, datos_simulados: bool = False) -> ResultadoAnalisis:
    """Calcula métricas por celda y por cuatro franjas de seis horas locales.

    Observaciones: celda_id, fecha_hora (UTC), observada (bool). Un True
    certifica observación utilizable de la celda en ese intervalo. Un False
    certifica que el intervalo fue evaluado sin observación utilizable.
    Registros ausentes son desconocidos, nunca ceros. Se unen sensores por OR.
    """
    if not np.isfinite(peso_recurrencia) or not 0 <= peso_recurrencia <= 1:
        raise ValueError("peso_recurrencia debe estar entre 0 y 1.")
    ini, termino, dias = _periodo(inicio, fin)
    if observaciones is not None and dias is None:
        raise ValueError("Los registros de observación requieren --inicio y --fin explícitos.")
    _exigir_columnas(celdas, ["celda_id", "latitud", "longitud", "area_km2"], "celdas preparadas")
    asignadas, fuera_periodo, fuera_parque = asignar_detecciones(unificada, celdas, ini, termino)
    claves = ["celda_id", "dia", "franja"]
    activos = asignadas[claves].drop_duplicates()
    focos = asignadas.groupby(["celda_id", "franja"]).size().rename("focos")
    intervalos_activos = activos.groupby(["celda_id", "franja"]).size().rename("intervalos_con_focos")
    indice = pd.MultiIndex.from_product([celdas.celda_id, range(4)], names=["celda_id", "franja"])
    franjas = indice.to_frame(index=False).set_index(["celda_id", "franja"])
    franjas = franjas.join(focos).join(intervalos_activos).fillna(0).astype(int)
    franjas["intervalos_evaluados"] = 0
    franjas["intervalos_observados"] = 0
    observaciones_fuera_periodo = 0
    if observaciones is not None:
        _exigir_columnas(observaciones, ["celda_id", "fecha_hora", "observada"], "observaciones")
        obs = _agregar_tiempo(observaciones)
        if obs["observada"].isna().any() or not pd.api.types.is_bool_dtype(obs.observada):
            raise ValueError("observada debe ser booleana, sin nulos (True/False).")
        obs["celda_id"] = obs["celda_id"].astype(str)
        if not obs["celda_id"].isin(celdas.celda_id).all():
            raise ValueError("Hay observaciones con celda_id ajeno a la cuadrícula.")
        dentro = obs.dia.between(ini, termino)
        observaciones_fuera_periodo = int((~dentro).sum())
        # Una observación válida prevalece sobre otra inválida en el mismo intervalo.
        intervalos = obs[dentro].groupby(claves)["observada"].max().reset_index()
        comprobacion = activos.merge(intervalos, on=claves, how="left")
        if not comprobacion["observada"].fillna(False).all():
            raise ValueError("Hay intervalos con focos sin observación válida. Revisa la máscara de cobertura.")
        resumen_obs = intervalos.groupby(["celda_id", "franja"])["observada"].agg(
            intervalos_evaluados="size", intervalos_observados="sum")
        franjas.update(resumen_obs)
    for col in ("intervalos_evaluados", "intervalos_observados"):
        franjas[col] = franjas[col].astype(int)
    franjas = franjas.reset_index()
    franjas["intervalos_esperados"] = dias if dias is not None else np.nan
    franjas = _metricas(franjas, peso_recurrencia)
    franjas["franja_local"] = franjas["franja"].map(dict(enumerate(FRANJAS)))
    suma = ["focos", "intervalos_con_focos", "intervalos_evaluados", "intervalos_observados"]
    prioridad = franjas.groupby("celda_id")[suma].sum().reset_index()
    prioridad["intervalos_esperados"] = dias * 4 if dias is not None else np.nan
    prioridad = _metricas(prioridad, peso_recurrencia)
    prioridad = celdas.drop(columns="geometry").merge(prioridad, on="celda_id", validate="one_to_one")
    contrato = ["celda_id", "latitud", "longitud", "focos", "cobertura", "prioridad"]
    prioridad = prioridad[contrato + [c for c in prioridad if c not in contrato]]
    # La procedencia viaja también dentro de los Parquet que leerá P4.
    for entrada in (unificada, observaciones):
        if entrada is not None and "datos_simulados" in entrada:
            if not pd.api.types.is_bool_dtype(entrada.datos_simulados):
                raise ValueError("datos_simulados debe ser una columna booleana.")
            datos_simulados = datos_simulados or bool(entrada.datos_simulados.any())
    for tabla in (prioridad, franjas):
        tabla["datos_simulados"] = datos_simulados
        tabla["inicio_local"] = str(ini.date()) if ini is not None else None
        tabla["fin_local"] = str(termino.date()) if termino is not None else None
    advertencias = []
    if observaciones is None:
        advertencias.append("Faltan registros independientes de observación: cobertura y prioridad desconocidas.")
    if dias is None:
        advertencias.append("Sin período declarado: no se calculan tasas temporales.")
    if unificada.empty:
        advertencias.append("La entrada no contiene detecciones; esto no demuestra ausencia de fuego.")
    if fuera_parque:
        advertencias.append(f"{fuera_parque} detecciones fuera del parque/cuadrícula fueron excluidas.")
    resumen = {
        "modulo": "P3", "version_metodo": "1.0", "datos_simulados": datos_simulados,
        "zona_horaria": ZONA_HORARIA, "inicio_local": str(ini.date()) if ini is not None else None,
        "fin_local": str(termino.date()) if termino is not None else None,
        "dias": dias, "celdas": len(prioridad), "detecciones_entrada": len(unificada),
        "detecciones_asignadas": len(asignadas), "detecciones_fuera_periodo": fuera_periodo,
        "detecciones_fuera_parque": fuera_parque,
        "observaciones_fuera_periodo": observaciones_fuera_periodo,
        "celdas_con_prioridad": int(prioridad.prioridad.notna().sum()),
        "celdas_cobertura_completa": int(prioridad.estado.eq("completa").sum()),
        "peso_recurrencia": peso_recurrencia, "peso_punto_ciego": 1 - peso_recurrencia,
        "formula": "peso_recurrencia * recurrencia_corregida + (1-peso_recurrencia) * (1-cobertura)",
        "unidad_recurrencia": "intervalos locales de 6 h con focos / intervalos observados",
        "fuente_limitaciones": FUENTE_NASA, "advertencias": advertencias,
    }
    return ResultadoAnalisis(prioridad, franjas, asignadas, resumen)


def _metricas(df, peso):
    df = df.copy()
    esperado = df.intervalos_esperados
    evaluado = df.intervalos_evaluados
    observado = df.intervalos_observados
    completo = esperado.notna() & evaluado.eq(esperado)
    df["fraccion_evaluada"] = evaluado / esperado
    df["cobertura_minima"] = observado / esperado
    df["cobertura_maxima"] = (observado + esperado - evaluado) / esperado
    df["cobertura"] = df.cobertura_minima.where(completo)
    df["recurrencia_observada"] = df.intervalos_con_focos / esperado
    df["recurrencia_corregida"] = (df.intervalos_con_focos / observado.replace(0, np.nan)).where(completo)
    df["prioridad"] = (peso * df.recurrencia_corregida + (1 - peso) * (1 - df.cobertura)).clip(0, 1)
    df["estado"] = np.select(
        [esperado.isna(), evaluado.eq(0), ~completo, observado.eq(0)],
        ["sin_periodo", "sin_observaciones", "cobertura_incompleta", "sin_cobertura"],
        default="completa")
    return df


def guardar_resultados(resultado, celdas, salida, directorio_graficos, graficos=True):
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    resultado.prioridad.to_parquet(salida, index=False)
    resultado.cobertura.to_parquet(salida.with_name("cobertura.parquet"), index=False)
    resultado.asignaciones.to_parquet(salida.with_name("detecciones_por_celda.parquet"), index=False)
    # P4 puede unir este GeoJSON a prioridad.parquet mediante celda_id.
    celdas.to_file(salida.with_name("celdas_analisis.geojson"), driver="GeoJSON")
    if graficos:
        generar_graficos(resultado, celdas, directorio_graficos)
    salida.with_name("resumen_analisis.json").write_text(
        json.dumps(resultado.resumen, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def generar_graficos(resultado, celdas, directorio):
    """Informe interactivo autónomo: Plotly embebido, sin mapas ni CDN externos."""
    import plotly.graph_objects as go
    from plotly.io import to_html

    directorio = Path(directorio)
    directorio.mkdir(parents=True, exist_ok=True)
    p, f, r = resultado.prioridad, resultado.cobertura, resultado.resumen
    etiqueta = "SIMULACIÓN · NO OPERATIVO" if r["datos_simulados"] else "DATOS REALES · ANÁLISIS DESCRIPTIVO"
    graficos = []
    # Coordenadas cartesianas: los trazados geo de Plotly pueden solicitar
    # topología mundial a un CDN, incluso con el JavaScript embebido.
    # Aquí cada marcador representa una celda y no hay recursos cartográficos remotos.
    mapa = go.Figure()
    mapa.add_trace(go.Scatter(
        x=p.longitud, y=p.latitud, mode="markers", showlegend=False,
        marker=dict(size=7, symbol="square", color="#d5d9dc"),
        text=p.celda_id, customdata=p.estado,
        hovertemplate="%{text}<br>%{customdata}<extra></extra>"))
    validas = p[p.prioridad.notna()]
    if not validas.empty:
        mapa.add_trace(go.Scatter(
            x=validas.longitud, y=validas.latitud, mode="markers", showlegend=False,
            marker=dict(size=7, symbol="square", color=validas.prioridad, cmin=0, cmax=1,
                        colorscale="YlOrRd", showscale=True, colorbar=dict(title="Prioridad")),
            text=validas.celda_id, customdata=validas.prioridad,
            hovertemplate="%{text}<br>Prioridad %{customdata:.3f}<extra></extra>"))
    mapa.update_layout(title="Prioridad por celda · gris = sin puntaje calculable", height=570,
                       xaxis_title="Longitud · ubicación representativa de cada celda",
                       yaxis_title="Latitud", yaxis=dict(scaleanchor="x", scaleratio=
                       1 / np.cos(np.radians(float(p.latitud.mean())))))
    graficos.append(mapa)
    medias = f.groupby("franja")["cobertura"].mean().reindex(range(4))
    n = f.groupby("franja")["cobertura"].count().reindex(range(4))
    barra = go.Figure(go.Bar(x=FRANJAS, y=medias, customdata=n,
                            hovertemplate="%{x}<br>Cobertura %{y:.1%}<br>Celdas evaluables %{customdata}<extra></extra>"))
    barra.update_layout(title="Cobertura media por franja local · solo celdas con evaluación completa",
                        xaxis_title="Hora de Bolivia (UTC−4)", yaxis_title="Fracción de intervalos observados",
                        yaxis_range=[0, 1], yaxis_tickformat=".0%")
    if medias.isna().all():
        barra.add_annotation(text="Cobertura desconocida: faltan registros de observación", showarrow=False,
                             x=0.5, y=0.5, xref="paper", yref="paper")
    graficos.append(barra)
    top = validas.nlargest(15, "prioridad").sort_values("prioridad")
    ranking = go.Figure(go.Bar(x=top.prioridad, y=top.celda_id, orientation="h"))
    ranking.update_layout(title="Hasta 15 celdas con mayor prioridad calculable", xaxis_range=[0, 1],
                          xaxis_title="Puntaje heurístico · no es probabilidad de incendio", height=550)
    if top.empty:
        ranking.add_annotation(text="No hay información suficiente para ordenar las celdas", showarrow=False,
                               x=0.5, y=0.5, xref="paper", yref="paper")
    graficos.append(ranking)
    if not resultado.asignaciones.empty:
        serie = resultado.asignaciones.groupby("dia").size()
        historico = go.Figure(go.Scatter(x=serie.index, y=serie.values, mode="lines+markers"))
        historico.update_layout(title="Detecciones unificadas por día local · no son incendios únicos",
                               xaxis_title="Fecha local", yaxis_title="Detecciones")
        graficos.append(historico)
    piezas = []
    for i, figura in enumerate(graficos):
        figura.update_layout(template="plotly_white", font=dict(family="Arial", size=14),
                             margin=dict(l=60, r=40, t=80, b=60))
        piezas.append(to_html(figura, full_html=False, include_plotlyjs=(i == 0),
                              config={"responsive": True}, div_id=f"p3-grafico-{i}"))
    from html import escape
    avisos = " ".join(r["advertencias"])
    html = f"""<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>P3 · Tunari Blindspot</title><body style="max-width:1100px;margin:30px auto;padding:0 20px;font-family:Arial">
<h1>Tunari Blindspot · Análisis P3</h1><p><strong>{etiqueta}</strong></p>
<p>Período local: {r['inicio_local'] or 'sin declarar'} a {r['fin_local'] or 'sin declarar'}.
{r['detecciones_asignadas']} detecciones; {r['celdas']} celdas;
{r['celdas_con_prioridad']} celdas con prioridad calculable.</p>
<p>{escape(avisos)}</p><p>Ausencia de focos no demuestra ausencia de fuego.
El puntaje orienta vigilancia y requiere validación en terreno.</p>
{''.join(piezas)}<p>Pesos: recurrencia {r['peso_recurrencia']:.0%}, falta de cobertura {r['peso_punto_ciego']:.0%}.
Las celdas grises no tienen puntaje; no representan riesgo bajo.</p></body></html>"""
    (directorio / "informe.html").write_text(html, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", type=Path, default=RAIZ / "data/processed/unificada.parquet")
    parser.add_argument("--celdas", type=Path, default=RAIZ / "data/processed/celdas.geojson")
    parser.add_argument("--limite", type=Path, default=RAIZ / "data/processed/limite.geojson")
    parser.add_argument("--observaciones", type=Path, help="Parquet de observaciones independientes")
    parser.add_argument("--inicio", help="Primera fecha local inclusiva YYYY-MM-DD")
    parser.add_argument("--fin", help="Última fecha local inclusiva YYYY-MM-DD")
    parser.add_argument("--salida", type=Path, default=RAIZ / "data/processed/prioridad.parquet")
    parser.add_argument("--graficos", type=Path)
    parser.add_argument("--sin-graficos", action="store_true")
    parser.add_argument("--peso-recurrencia", type=float, default=0.6)
    parser.add_argument("--datos-simulados", action="store_true")
    args = parser.parse_args()
    try:
        celdas = preparar_celdas(gpd.read_file(args.celdas), gpd.read_file(args.limite))
        resultado = analizar(pd.read_parquet(args.entrada), celdas, args.inicio, args.fin,
                             pd.read_parquet(args.observaciones) if args.observaciones else None,
                             args.peso_recurrencia, args.datos_simulados)
        resultado.resumen["archivos_entrada"] = {
            "unificada": str(args.entrada.resolve()), "celdas": str(args.celdas.resolve()),
            "limite": str(args.limite.resolve()),
            "observaciones": str(args.observaciones.resolve()) if args.observaciones else None}
        graficos = args.graficos or args.salida.parent / "graficos"
        guardar_resultados(resultado, celdas, args.salida, graficos, not args.sin_graficos)
    except (ValueError, FileNotFoundError) as exc:
        parser.exit(1, f"Error de análisis: {exc}\n")
    for aviso in resultado.resumen["advertencias"]:
        print(f"Aviso: {aviso}")
    print(f"{len(resultado.prioridad)} celdas; {resultado.resumen['detecciones_asignadas']} detecciones asignadas; "
          f"{resultado.resumen['celdas_con_prioridad']} puntajes calculables.")
    print(f"Guardado en {args.salida}")


if __name__ == "__main__":
    main()
