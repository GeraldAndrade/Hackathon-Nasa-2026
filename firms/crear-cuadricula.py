import geopandas as gpd
from shapely.geometry import Polygon
import numpy as np

def generar_cuadricula():
    print("1. Cargando el límite del Parque Tunari...")
    try:
        limite = gpd.read_file("limite.geojson")
    except FileNotFoundError:
        print("Error: No se encontró 'limite.geojson'. Corre primero 'procesar_ingesta.py'.")
        return

    xmin, ymin, xmax, ymax = limite.total_bounds

    # 0.01 grados equivale aprox. a 1.1 km x 1.1 km
    tamaño_celda = 0.01
    print(f"2. Dibujando celdas de {tamaño_celda} grados...")

    celdas = []
    for x0 in np.arange(xmin, xmax, tamaño_celda):
        for y0 in np.arange(ymin, ymax, tamaño_celda):
            x1 = x0 + tamaño_celda
            y1 = y0 + tamaño_celda
            celdas.append(Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]))

    cuadricula = gpd.GeoDataFrame(geometry=celdas, crs="EPSG:4326")

    print("3. Filtrando las celdas que caen fuera del parque...")
    cuadricula_tunari = gpd.sjoin(cuadricula, limite, predicate='intersects')
    
    cuadricula_tunari = cuadricula_tunari[['geometry']]
    cuadricula_tunari.to_file("celdas.geojson", driver="GeoJSON")
    print(f"Entregable 'celdas.geojson' creado con éxito. Total: {len(cuadricula_tunari)} celdas.")

if __name__ == "__main__":
    generar_cuadricula()