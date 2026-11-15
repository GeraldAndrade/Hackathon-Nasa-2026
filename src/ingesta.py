"""P1 · Ingesta de focos de calor reales de NASA FIRMS para el Parque Nacional Tunari.

Descarga las detecciones de MODIS y VIIRS (S-NPP, NOAA-20 y NOAA-21) con la API
de área de FIRMS, las recorta con el límite del parque y deja listos todos los
archivos que lee la aplicación:

    data/processed/limite.geojson      límite del parque (OpenStreetMap)
    data/processed/celdas.geojson      cuadrícula de ~1 km
    data/processed/limpio.parquet      focos dentro del parque (columnas de FIRMS)
    data/processed/unificada.parquet   armonización MODIS + VIIRS (P2)
    data/processed/prioridad.parquet   y demás salidas del análisis (P3)

Para cada fecha se usa el producto de calidad científica (SP) cuando existe y,
para los meses más recientes, el de tiempo casi real (NRT). Las descargas se
guardan en data/raw/firms/ (no se sube a GitHub), así una nueva ejecución solo
pide los tramos que faltan y los de los últimos días.

La clave se lee de la variable de entorno FIRMS_MAP_KEY o de
.streamlit/secrets.toml (FIRMS_MAP_KEY = "...").

Uso (desde cualquier carpeta):
    python src/ingesta.py                          # 2021-01-01 hasta hoy
    python src/ingesta.py --desde 2024-01-01 --hasta 2024-12-31
    python src/ingesta.py --solo-descarga          # sin armonizar ni analizar
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import threading
import time
import tomllib
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.geometry import box

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

PROCESADOS = RAIZ / "data" / "processed"
CRUDOS = RAIZ / "data" / "raw" / "firms"
LIMITE = PROCESADOS / "limite.geojson"
CELDAS = PROCESADOS / "celdas.geojson"
LIMPIO = PROCESADOS / "limpio.parquet"
UNIFICADA = PROCESADOS / "unificada.parquet"
PRIORIDAD = PROCESADOS / "prioridad.parquet"

API = "https://firms.modaps.eosdis.nasa.gov/api"
# Rectángulo que cubre todo el parque (oeste, sur, este, norte)
BBOX = (-66.75, -17.56, -65.90, -16.90)
MAX_DIAS = 5            # la API de área acepta de 1 a 5 días por consulta
TAMANO_CELDA = 0.01     # grados, ~1,1 km
DESDE_POR_DEFECTO = "2021-01-01"

# Cada satélite tiene un producto científico (SP) y otro de tiempo casi real (NRT)
FAMILIAS = {
    "modis": ("MODIS_SP", "MODIS_NRT"),
    "viirs_snpp": ("VIIRS_SNPP_SP", "VIIRS_SNPP_NRT"),
    "viirs_noaa20": ("VIIRS_NOAA20_SP", "VIIRS_NOAA20_NRT"),
    "viirs_noaa21": ("VIIRS_NOAA21_SP", "VIIRS_NOAA21_NRT"),
}

_SESION = requests.Session()
_SESION.headers["User-Agent"] = "TunariBlindspot/1.0 (NASA Space Apps)"


# ---------------------------------------------------------------------------
# Clave
# ---------------------------------------------------------------------------

def clave_firms() -> str:
    clave = os.environ.get("FIRMS_MAP_KEY")
    secretos = RAIZ / ".streamlit" / "secrets.toml"
    if not clave and secretos.exists():
        clave = tomllib.loads(secretos.read_text(encoding="utf-8")).get("FIRMS_MAP_KEY")
    if not clave:
        raise SystemExit("Falta FIRMS_MAP_KEY: guárdala en .streamlit/secrets.toml o como variable de entorno.")
    return clave


# ---------------------------------------------------------------------------
# Límite y cuadrícula
# ---------------------------------------------------------------------------

def obtener_limite() -> gpd.GeoDataFrame:
    """Límite del parque; si no existe se descarga de OpenStreetMap (Nominatim)."""
    if not LIMITE.exists():
        print("Descargando el límite del Parque Nacional Tunari desde OpenStreetMap...")
        r = _SESION.get("https://nominatim.openstreetmap.org/search", timeout=30,
                        params={"q": "Parque Nacional Tunari, Bolivia", "format": "json",
                                "polygon_geojson": 1, "limit": 1})
        r.raise_for_status()
        datos = r.json()
        if not datos:
            raise SystemExit("OpenStreetMap no devolvió el límite del parque.")
        LIMITE.parent.mkdir(parents=True, exist_ok=True)
        LIMITE.write_text(json.dumps({"type": "FeatureCollection", "features": [{
            "type": "Feature", "properties": {"nombre": "Parque Nacional Tunari"},
            "geometry": datos[0]["geojson"]}]}), encoding="utf-8")
    return gpd.read_file(LIMITE)


def obtener_celdas(limite: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Cuadrícula de celdas de ~1 km que tocan el parque; se crea si no existe."""
    if not CELDAS.exists():
        print("Creando la cuadrícula de celdas...")
        xmin, ymin, xmax, ymax = limite.total_bounds
        celdas = [box(x, y, x + TAMANO_CELDA, y + TAMANO_CELDA)
                  for x in np.arange(xmin, xmax, TAMANO_CELDA)
                  for y in np.arange(ymin, ymax, TAMANO_CELDA)]
        cuadricula = gpd.GeoDataFrame(geometry=celdas, crs="EPSG:4326")
        cuadricula = cuadricula[cuadricula.intersects(limite.geometry.union_all())]
        cuadricula.to_file(CELDAS, driver="GeoJSON")
    return gpd.read_file(CELDAS)


# ---------------------------------------------------------------------------
# Descarga
# ---------------------------------------------------------------------------

def disponibilidad(clave: str) -> dict[str, tuple[date, date]]:
    """Primera y última fecha disponible de cada producto en FIRMS."""
    while True:
        r = _SESION.get(f"{API}/data_availability/csv/{clave}/all", timeout=30)
        if r.ok and r.text.startswith("data_id"):
            break
        usadas, limite = cuota(clave)
        if usadas < limite:
            raise SystemExit(f"FIRMS rechazó la clave: {r.text[:120]}")
        print("La cuota de FIRMS de estos 10 minutos está agotada; esperando...")
        time.sleep(60)
    tabla = pd.read_csv(io.StringIO(r.text))
    return {fila.data_id: (date.fromisoformat(fila.min_date), date.fromisoformat(fila.max_date))
            for fila in tabla.itertuples()}


def planificar(desde: date, hasta: date, disp: dict) -> list[tuple[str, str, date, int]]:
    """Lista de consultas (familia, producto, fecha inicial, días) sin huecos ni solapes.

    Se usa SP hasta su última fecha y NRT desde el día siguiente.
    """
    consultas = []
    for familia, (sp, nrt) in FAMILIAS.items():
        tramos, siguiente = [], desde
        if sp in disp:
            ini, fin = max(desde, disp[sp][0]), min(hasta, disp[sp][1])
            if ini <= fin:
                tramos.append((sp, ini, fin))
            siguiente = max(desde, disp[sp][1] + timedelta(days=1))
        if nrt in disp:
            ini, fin = max(siguiente, disp[nrt][0]), min(hasta, disp[nrt][1])
            if ini <= fin:
                tramos.append((nrt, ini, fin))
        for producto, ini, fin in tramos:
            dia = ini
            while dia <= fin:
                dias = min(MAX_DIAS, (fin - dia).days + 1)
                consultas.append((familia, producto, dia, dias))
                dia += timedelta(days=dias)
    return consultas


def _archivo(producto: str, dia: date, dias: int) -> Path:
    return CRUDOS / producto / f"{dia:%Y-%m-%d}_{dias}d.csv"


class Limitador:
    """Reparte las consultas para no superar la cuota de FIRMS.

    FIRMS permite 5000 transacciones cada 10 minutos por clave y cada día pedido
    cuenta como una transacción. Se usa como mucho `maximo` para dejar margen a
    la app en vivo, que comparte la misma clave.
    """

    def __init__(self, maximo: int = 4000, ventana_s: int = 600):
        self.maximo, self.ventana_s = maximo, ventana_s
        self.gastos: deque[tuple[float, int]] = deque()
        self.candado = threading.Lock()

    def esperar(self, costo: int) -> None:
        while True:
            with self.candado:
                ahora = time.monotonic()
                while self.gastos and ahora - self.gastos[0][0] > self.ventana_s:
                    self.gastos.popleft()
                if sum(c for _, c in self.gastos) + costo <= self.maximo:
                    self.gastos.append((ahora, costo))
                    return
            time.sleep(5)


def cuota(clave: str) -> tuple[int, int]:
    """Transacciones usadas y límite de la clave en la ventana actual de 10 minutos."""
    r = _SESION.get("https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/",
                    params={"MAP_KEY": clave}, timeout=30)
    r.raise_for_status()
    j = r.json()
    return int(j.get("current_transactions") or 0), int(j.get("transaction_limit") or 5000)


def _descargar(clave: str, producto: str, dia: date, dias: int, refrescar_desde: date,
               limitador: Limitador) -> str:
    destino = _archivo(producto, dia, dias)
    ultimo = dia + timedelta(days=dias - 1)
    if destino.exists() and ultimo < refrescar_desde:
        return "cache"
    area = ",".join(str(v) for v in BBOX)
    url = f"{API}/area/csv/{clave}/{producto}/{area}/{dias}/{dia:%Y-%m-%d}"
    motivo, fallos = "", 0
    while fallos < 5:
        limitador.esperar(dias)
        try:
            r = _SESION.get(url, timeout=60)
            texto = r.text.strip()
            if r.ok and texto.startswith("latitude"):
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_text(texto + "\n", encoding="utf-8")
                return "descargado"
            motivo = texto[:120]
        except requests.RequestException as e:
            motivo = type(e).__name__
        # Al agotar la cuota FIRMS responde "Invalid MAP_KEY": se espera a que se libere.
        try:
            usadas, limite = cuota(clave)
        except (requests.RequestException, ValueError):
            usadas, limite = 0, 1
        if usadas >= limite - dias or "limit" in motivo.lower():
            time.sleep(60)
            continue
        fallos += 1
        time.sleep(5 * fallos)
    raise RuntimeError(f"{producto} {dia}: {motivo}")


def descargar(clave: str, desde: date, hasta: date, hilos: int = 3) -> tuple[list, list[str]]:
    consultas = planificar(desde, hasta, disponibilidad(clave))
    refrescar_desde = date.today() - timedelta(days=2)  # NRT recibe datos nuevos los últimos días
    pendientes = sum(d for _, p, i, d in consultas
                     if not (_archivo(p, i, d).exists() and i + timedelta(days=d - 1) < refrescar_desde))
    usadas, limite = cuota(clave)
    limitador = Limitador(maximo=min(4000, limite - 500))
    if usadas:  # lo ya gastado en esta ventana cuenta para la cuota
        limitador.gastos.append((time.monotonic(), usadas))
    print(f"Consultando NASA FIRMS: {len(consultas)} tramos de hasta {MAX_DIAS} días "
          f"({desde} a {hasta}); faltan {pendientes} días-producto.")
    if pendientes > limitador.maximo:
        print(f"  La cuota es de {limite} cada 10 minutos: la descarga tomará unos "
              f"{10 * pendientes // limitador.maximo} minutos.")
    def tarea(c):
        _, producto, dia, dias = c
        try:
            return _descargar(clave, producto, dia, dias, refrescar_desde, limitador)
        except RuntimeError as e:
            return f"error: {e}"

    with ThreadPoolExecutor(max_workers=hilos) as pool:
        resultados = list(pool.map(tarea, consultas))
    errores = [r[len("error: "):] for r in resultados if r.startswith("error: ")]
    print(f"  {resultados.count('descargado')} descargados, {resultados.count('cache')} ya estaban guardados.")
    return consultas, errores


# ---------------------------------------------------------------------------
# Recorte al parque
# ---------------------------------------------------------------------------

def unir_y_recortar(consultas, limite: gpd.GeoDataFrame) -> pd.DataFrame:
    partes = []
    for familia, producto, dia, dias in consultas:
        ruta = _archivo(producto, dia, dias)
        if ruta.exists():
            df = pd.read_csv(ruta, dtype=str)
            if len(df):
                partes.append(df.assign(sensor_origen=familia, fuente=producto))
    if not partes:
        return pd.DataFrame(columns=["id", "latitude", "longitude", "acq_date", "acq_time", "satellite",
                                     "instrument", "confidence", "frp", "sensor_origen", "fuente"])
    crudo = pd.concat(partes, ignore_index=True)
    for col in ("latitude", "longitude", "brightness", "bright_ti4", "bright_ti5", "bright_t31",
                "scan", "track", "frp"):
        if col in crudo:
            crudo[col] = pd.to_numeric(crudo[col], errors="coerce")
    crudo["acq_time"] = pd.to_numeric(crudo["acq_time"], errors="coerce").astype("Int64")
    crudo = crudo.dropna(subset=["latitude", "longitude", "acq_date", "acq_time"])

    puntos = gpd.GeoDataFrame(crudo, geometry=gpd.points_from_xy(crudo.longitude, crudo.latitude),
                              crs="EPSG:4326")
    dentro = puntos[puntos.within(limite.to_crs(4326).geometry.union_all())]
    limpio = pd.DataFrame(dentro.drop(columns="geometry"))
    limpio = (limpio.drop_duplicates(subset=["sensor_origen", "satellite", "latitude", "longitude",
                                             "acq_date", "acq_time"])
              .sort_values(["acq_date", "acq_time", "sensor_origen", "latitude", "longitude"])
              .reset_index(drop=True))
    limpio.insert(0, "id", [f"F{i:07d}" for i in range(1, len(limpio) + 1)])
    return limpio


# ---------------------------------------------------------------------------
# Programa
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga y procesa los focos reales de NASA FIRMS.")
    parser.add_argument("--desde", default=DESDE_POR_DEFECTO, help="Fecha inicial YYYY-MM-DD (UTC)")
    parser.add_argument("--hasta", default=None, help="Fecha final YYYY-MM-DD (por defecto, hoy)")
    parser.add_argument("--hilos", type=int, default=3, help="Consultas simultáneas a FIRMS")
    parser.add_argument("--solo-descarga", action="store_true",
                        help="Solo descargar y recortar (sin armonizar ni analizar)")
    args = parser.parse_args()

    desde = date.fromisoformat(args.desde)
    hasta = date.fromisoformat(args.hasta) if args.hasta else date.today()
    if hasta < desde:
        parser.error("--hasta debe ser igual o posterior a --desde")

    clave = clave_firms()
    PROCESADOS.mkdir(parents=True, exist_ok=True)
    limite = obtener_limite()
    celdas = obtener_celdas(limite)

    consultas, errores = descargar(clave, desde, hasta, args.hilos)
    if errores:
        # No se publica un historial con huecos: lo descargado queda guardado y se retoma al reintentar.
        print(f"{len(errores)} tramos no se pudieron descargar:")
        for e in errores[:10]:
            print("  -", e)
        raise SystemExit("Vuelve a ejecutar el mismo comando para completar la descarga. "
                         "Los archivos de data/processed/ no se modificaron.")
    limpio = unir_y_recortar(consultas, limite)
    limpio.to_parquet(LIMPIO, index=False)
    print(f"{len(limpio)} focos dentro del parque -> {LIMPIO.relative_to(RAIZ)}")
    if args.solo_descarga:
        return

    from armonizacion import armonizar, normalizar, resumen
    from analisis import analizar, guardar_resultados, preparar_celdas

    unificada = armonizar(limpio)
    unificada.to_parquet(UNIFICADA, index=False)
    print(resumen(unificada, int((normalizar(limpio)["sensor"] == "MODIS").sum())))
    print(f"-> {UNIFICADA.relative_to(RAIZ)}")

    celdas_p3 = preparar_celdas(celdas, limite)
    resultado = analizar(unificada, celdas_p3, str(desde), str(hasta))
    resultado.resumen["archivos_entrada"] = {"fuente": "NASA FIRMS (API de área)",
                                             "productos": sorted({c[1] for c in consultas})}
    guardar_resultados(resultado, celdas_p3, PRIORIDAD, PROCESADOS / "graficos")
    for aviso in resultado.resumen["advertencias"]:
        print(f"Aviso: {aviso}")
    print(f"Análisis de {len(celdas_p3)} celdas -> {PRIORIDAD.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
