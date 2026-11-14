import requests
import json
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

def obtener_limite_tunari():
    print("1. Descargando el límite del Parque Nacional Tunari desde OpenStreetMap...")
    url = "https://nominatim.openstreetmap.org/search"
    # formato GeoJSON
    params = {
        "q": "Parque Nacional Tunari, Bolivia",
        "format": "json",
        "polygon_geojson": 1,
        "limit": 1
    }
    headers = {"User-Agent": "TunariFireTracker_Ingesta_P1"}
    
    respuesta = requests.get(url, params=params, headers=headers)
    datos = respuesta.json()
    
    if len(datos) > 0:
        geometria = datos[0]['geojson']
        # Armamos un archivo GeoJSON estándar
        feature_collection = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {"nombre": "Parque Nacional Tunari"}, "geometry": geometria}]
        }
        with open("limite.geojson", "w", encoding="utf-8") as f:
            json.dump(feature_collection, f)
        print("Entregable 'limite.geojson' creado.")
        return True
    else:
        print("No se encontró el parque.")
        return False

def limpiar_y_recortar():
    print("\n2. Procesando los archivos CSV de la NASA...")
    archivos_csv = ['modis_raw.csv', 'viirs_snpp_raw.csv', 'viirs_noaa20_raw.csv', 'viirs_noaa21_raw.csv']
    lista_df = []
    
    for archivo in archivos_csv:
        try:
            df = pd.read_csv(archivo)
            # Sensor que detecto cada fuego
            df['sensor_origen'] = archivo.split('_raw')[0]
            lista_df.append(df)
        except FileNotFoundError:
            print(f"No se encontró {archivo}, saltando...")
            
    df_completo = pd.concat(lista_df, ignore_index=True)
    
    # Convertimos las coordenadas en Puntos geométricos
    geometria = [Point(xy) for xy in zip(df_completo.longitude, df_completo.latitude)]
    # CRS EPSG:4326 es el estándar GPS (latitud/longitud)
    gdf_incendios = gpd.GeoDataFrame(df_completo, geometry=geometria, crs="EPSG:4326")
    
    print("\n3. Haciendo el cruce espacial (Intersección)...")
    limite_tunari = gpd.read_file("limite.geojson")
    
    incendios_tunari = gpd.clip(gdf_incendios, limite_tunari)
    
    print(f"🔥 Se filtraron {len(incendios_tunari)} focos de calor estrictamente dentro del Parque Tunari.")
    
    # Guardamos el resultado en el formato optimizado que pide tu rol
    incendios_tunari.to_parquet("limpio.parquet")
    print("Entregable 'limpio.parquet' creado con éxito.")

if __name__ == "__main__":
    if obtener_limite_tunari():
        limpiar_y_recortar()