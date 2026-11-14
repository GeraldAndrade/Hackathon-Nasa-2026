# Hackathon-Nasa-2026
Desafío NASA: Harmonization of MODIS and VIIRS Hot Spots  Enfoque local: Armonización Satelital para Monitoreo de Incendios en el Parque Nacional Tunari

## Módulos
- [P2 · Armonización de MODIS y VIIRS](README_ARMONIZACION.md)
- [P3 · Cobertura, recurrencia y prioridad de vigilancia](README_ANALISIS.md)

P3 asigna los focos armonizados a las celdas del Tunari y, cuando hay registros
independientes de observación, calcula cobertura por horario, recurrencia
corregida y prioridad de vigilancia. Los datos desconocidos quedan identificados
y la demostración usa observaciones simuladas separadas de los resultados reales.
Incluye gráficos sin conexión y un [guion de demostración](docs/GUION_DEMO_P3.md).

## Aplicación en tiempo real

```bash
pip install -r requirements.txt
streamlit run app/app.py
```

| Página | Qué muestra |
|---|---|
| Mapa en vivo | Focos de NASA FIRMS coloreados por tipo de incendio, vista conjunta o por sensor (MODIS / VIIRS), mapa satelital, de relieve, oscuro o **3D con la topografía real del Tunari**, temperatura del aire y viento sobre el parque, y qué satélite pasa a continuación |
| Pronóstico | 7 días y 48 horas por sector (temperatura con colores, viento, humedad, lluvia), rosa de vientos y peor momento de la semana |
| Alertas | Regla de clima ajustable (30-30-30 recomendada) calibrada con el clima real de 2025, focos nuevos, puntos ciegos y envío por Telegram |
| Armonización y tipos | Resultado de P2, tipos de incendio por temperatura, cobertura por hora y zonas prioritarias de P3 |
| Portada del equipo | Portada de P4 |

Los datos se consultan solos cada 5 a 30 minutos (se elige en el menú lateral). Fuentes:
focos de [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/api/), clima, relieve y
clima histórico de [Open-Meteo](https://open-meteo.com/) (sin clave), imágenes
satelitales de Esri y relieve 3D de AWS Terrain Tiles.

Para ver focos en vivo y enviar alertas, copia `.streamlit/secrets.toml.example`
como `.streamlit/secrets.toml` y completa `FIRMS_MAP_KEY` (gratis) y, si quieres,
los datos del bot de Telegram. Sin clave, el mapa muestra los datos de ejemplo.
