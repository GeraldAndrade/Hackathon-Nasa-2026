import requests

MAP_KEY = "80404282529192ff8f12c273bab5097a"

# Bounding Box aproximado de Cochabamba / Parque Tunari
BBOX = "-66.5,-17.5,-65.8,-17.0"

# Rango de dias a descargar - la api solo deja hasta 5 dias btw
DIAS = "5" 

#MODIS y VIIRS
sensores = {
    "modis": "MODIS_NRT",
    "viirs_snpp": "VIIRS_SNPP_NRT",
    "viirs_noaa20": "VIIRS_NOAA20_NRT",
    "viirs_noaa21": "VIIRS_NOAA21_NRT"
}

def descargar_datos():
    print("Iniciando descarga desde NASA FIRMS...")
    
    for nombre, codigo in sensores.items():
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{codigo}/{BBOX}/{DIAS}"
        
        print(f"Descargando {nombre.upper()}...")
        respuesta = requests.get(url)
        
        if respuesta.status_code == 200:
            nombre_archivo = f"{nombre}_raw.csv"
            with open(nombre_archivo, "wb") as archivo:
                archivo.write(respuesta.content)
            print(f"Archivo guardado: {nombre_archivo}")
        else:
            print(f"Error descargando {nombre}. Código: {respuesta.status_code}")
            print(respuesta.text)

if __name__ == "__main__":
    descargar_datos()