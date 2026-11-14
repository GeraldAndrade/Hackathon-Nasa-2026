"""Verifica las decisiones de P3 con casos pequeños calculables a mano."""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from analisis import analizar, preparar_celdas, guardar_resultados, generar_graficos
from generar_demo_analisis import simular_observaciones


def celdas():
    return preparar_celdas(gpd.GeoDataFrame(
        {"celda_id": ["A", "B"]}, geometry=[box(-66.2, -17.3, -66.1, -17.2),
                                                 box(-66.1, -17.3, -66.0, -17.2)], crs=4326))


def detecciones(filas=()):
    return pd.DataFrame(filas, columns=["id_unificado", "latitud", "longitud", "fecha_hora"])


def observaciones(cobertura_a=(True, True, False, False), cobertura_b=(True,) * 4):
    return pd.DataFrame([
        (celda, f"2025-09-01T{hora:02d}:00:00Z", observada)
        for celda, estados in (("A", cobertura_a), ("B", cobertura_b))
        for hora, observada in zip((4, 10, 16, 22), estados)
    ], columns=["celda_id", "fecha_hora", "observada"])


def test_prioridad_correccion_y_union_sensores():
    d = detecciones([("U1", -17.25, -66.15, "2025-09-01T05:00Z"),
                     ("U2", -17.25, -66.15, "2025-09-01T05:30Z")])
    o = observaciones()
    # Registros repetidos y un sensor tapado no cuentan como nuevos intervalos.
    o = pd.concat([o, o.iloc[:1], o.iloc[:1].assign(observada=False)])
    r = analizar(d, celdas(), "2025-09-01", "2025-09-01", o)
    a = r.prioridad.set_index("celda_id").loc["A"]
    assert a.focos == 2
    assert a.intervalos_con_focos == 1
    assert a.intervalos_evaluados == 4
    assert a.cobertura == 0.5
    assert a.recurrencia_observada == 0.25
    assert a.recurrencia_corregida == 0.5
    assert a.prioridad == pytest.approx(0.6 * 0.5 + 0.4 * 0.5)
    assert r.prioridad.set_index("celda_id").loc["B", "prioridad"] == 0


def test_ausencia_de_focos_no_es_cobertura_cero():
    r = analizar(detecciones(), celdas(), "2025-09-01", "2025-09-02")
    assert r.prioridad.focos.eq(0).all()
    assert r.prioridad.cobertura.isna().all()
    assert r.prioridad.prioridad.isna().all()
    assert r.prioridad.estado.eq("sin_observaciones").all()
    assert r.prioridad.intervalos_esperados.eq(8).all()


def test_sin_periodo_y_sin_datos_se_puede_exportar(tmp_path):
    r = analizar(detecciones(), celdas())
    assert r.prioridad.estado.eq("sin_periodo").all()
    guardar_resultados(r, celdas(), tmp_path / "prioridad.parquet", tmp_path / "graficos", graficos=False)
    assert pd.read_parquet(tmp_path / "prioridad.parquet").shape[0] == 2
    assert (tmp_path / "resumen_analisis.json").exists()


def test_intervalos_faltantes_son_desconocidos_y_cero_observado_no_divide():
    o = observaciones(cobertura_b=(False,) * 4).iloc[1:]
    r = analizar(detecciones(), celdas(), "2025-09-01", "2025-09-01", o)
    tabla = r.prioridad.set_index("celda_id")
    a, b = tabla.loc["A"], tabla.loc["B"]
    assert a.estado == "cobertura_incompleta"
    assert np.isnan(a.cobertura)
    assert a.cobertura_minima == 0.25
    assert a.cobertura_maxima == 0.5
    assert b.estado == "sin_cobertura"
    assert b.cobertura == 0
    assert np.isnan(b.recurrencia_corregida) and np.isnan(b.prioridad)


def test_aristas_cuentan_una_vez_y_puntos_fuera_se_excluyen():
    d = detecciones([("borde", -17.25, -66.1, "2025-09-01T05:00Z"),
                     ("fuera", -18, -66, "2025-09-01T05:00Z")])
    r = analizar(d, celdas())
    assert r.prioridad.focos.sum() == 1
    assert r.asignaciones.iloc[0].celda_id == "A"
    assert r.resumen["detecciones_fuera_parque"] == 1


def test_utc_dia_anterior_y_franjas_en_hora_boliviana():
    d = detecciones([("anterior", -17.25, -66.15, "2025-09-02T03:59Z"),
                     ("siguiente", -17.25, -66.15, "2025-09-02T04:00Z")])
    r = analizar(d, celdas(), "2025-09-01", "2025-09-01")
    assert len(r.asignaciones) == 1
    assert r.asignaciones.iloc[0].franja == 3
    assert r.resumen["detecciones_fuera_periodo"] == 1


def test_limite_recorta_celdas_e_identificadores_no_dependen_del_orden():
    original = gpd.GeoDataFrame(geometry=[box(-66.2, -17.3, -66.1, -17.2),
                                              box(-66.1, -17.3, -66, -17.2)], crs=4326)
    limite = gpd.GeoDataFrame(geometry=[box(-66.18, -17.28, -66.02, -17.22)], crs=4326)
    a = preparar_celdas(original, limite)
    b = preparar_celdas(original.iloc[::-1], limite)
    assert a.celda_id.tolist() == b.celda_id.tolist()
    assert a.geometry.equals(b.geometry)
    assert a.geometry.covered_by(limite.geometry.iloc[0]).all()


@pytest.mark.parametrize("inicio,fin", [("2025-09-02", "2025-09-01"), ("2025-09-01", None)])
def test_rechaza_periodo_invalido(inicio, fin):
    with pytest.raises(ValueError):
        analizar(detecciones(), celdas(), inicio, fin)


def test_rechaza_observaciones_inconsistentes_y_ids_invalidos():
    d = detecciones([("U1", -17.25, -66.15, "2025-09-01T05:00Z")])
    with pytest.raises(ValueError, match="sin observación válida"):
        analizar(d, celdas(), "2025-09-01", "2025-09-01", observaciones().iloc[1:])
    with pytest.raises(ValueError, match="booleana"):
        analizar(detecciones(), celdas(), "2025-09-01", "2025-09-01",
                 observaciones().assign(observada="False"))
    with pytest.raises(ValueError, match="ajeno"):
        analizar(detecciones(), celdas(), "2025-09-01", "2025-09-01",
                 observaciones().assign(celda_id="X"))
    with pytest.raises(ValueError, match="único"):
        analizar(pd.concat([d, d]), celdas())


def test_demo_reproducible_y_rango_de_prioridad():
    d = detecciones([("U1", -17.25, -66.15, "2025-09-01T05:00Z")])
    o = simular_observaciones(celdas(), d, "2025-09-01", "2025-09-02", 42)
    pd.testing.assert_frame_equal(o, simular_observaciones(celdas(), d, "2025-09-01", "2025-09-02", 42))
    r = analizar(d, celdas(), "2025-09-01", "2025-09-02", o, datos_simulados=True)
    assert r.prioridad.prioridad.dropna().between(0, 1).all()
    assert r.resumen["datos_simulados"] is True
    assert r.prioridad.datos_simulados.all()
    assert r.prioridad.intervalos_evaluados.eq(8).all()


def test_informe_incluye_simulacion_y_no_usa_recursos_remotos(tmp_path, monkeypatch):
    import plotly.io
    from html.parser import HTMLParser

    figuras = []
    exportar = plotly.io.to_html

    def capturar(figura, **kwargs):
        figuras.append(figura)
        return exportar(figura, **kwargs)

    monkeypatch.setattr(plotly.io, "to_html", capturar)
    r = analizar(detecciones(), celdas(), "2025-09-01", "2025-09-01",
                 observaciones(), datos_simulados=True)
    generar_graficos(r, celdas(), tmp_path)
    html = (tmp_path / "informe.html").read_text(encoding="utf-8")
    assert "SIMULACIÓN · NO OPERATIVO" in html
    assert len(figuras) == 3
    assert all(traza.type in ("scatter", "bar") for fig in figuras for traza in fig.data)

    class Recursos(HTMLParser):
        externos = []

        def handle_starttag(self, tag, attrs):
            for atributo, valor in attrs:
                if atributo == "src" or (tag == "link" and atributo == "href"):
                    self.externos.append(valor)

    recursos = Recursos()
    recursos.feed(html)
    assert recursos.externos == []


def test_observaciones_simuladas_propagan_procedencia():
    r = analizar(detecciones(), celdas(), "2025-09-01", "2025-09-01",
                 observaciones().assign(datos_simulados=True))
    assert r.resumen["datos_simulados"]
    assert r.prioridad.datos_simulados.all()
