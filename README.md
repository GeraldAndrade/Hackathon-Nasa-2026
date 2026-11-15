# Hackathon-Nasa-2026
Desafío NASA: Harmonization of MODIS and VIIRS Hot Spots  Enfoque local: Armonización Satelital para Monitoreo de Incendios en el Parque Nacional Tunari

## Módulos
- P1 · Ingesta de NASA FIRMS: `src/ingesta.py`
- [P2 · Armonización de MODIS y VIIRS](README_ARMONIZACION.md)
- [P3 · Cobertura, recurrencia y prioridad de vigilancia](README_ANALISIS.md)

Todo el proyecto usa **datos reales**: focos de NASA FIRMS (MODIS y VIIRS) y clima de
Open-Meteo. No hay datos de ejemplo.

## Cómo ponerlo en marcha

1. Instalar las dependencias:

   ```bash
   python -m pip install -r requirements.txt
   ```

2. Guardar la clave de NASA FIRMS. El archivo `.streamlit/secrets.toml` **no se sube a
   GitHub** (git lo ignora). Cada persona crea el suyo a partir de la plantilla y completa
   `FIRMS_MAP_KEY` con la clave del equipo o una propia de
   [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/api/map_key/):

   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```

   En Windows (PowerShell): `Copy-Item .streamlit/secrets.toml.example .streamlit/secrets.toml`.
   También sirve la variable de entorno `FIRMS_MAP_KEY`.

3. Descargar y procesar el historial de focos del parque (P1 → P2 → P3):

   ```bash
   python src/ingesta.py
   ```

   Descarga desde 2021-01-01 hasta hoy (cámbialo con `--desde` y `--hasta`), recorta los
   focos con el límite del parque, los armoniza y calcula el análisis por celda. Todo queda en
   `data/processed/`. FIRMS permite 5000 transacciones cada 10 minutos (cada día de cada
   producto cuenta como una), así que la primera descarga tarda unos 20 minutos; las
   siguientes solo piden lo nuevo porque las descargas quedan guardadas en `data/raw/`.

4. Abrir la app:

   ```bash
   python -m streamlit run app/app.py
   ```

   Se abre en el navegador en `http://localhost:8501`.

### Qué tiene la app

| Página | Qué muestra |
|---|---|
| Mapa en vivo | Focos de NASA FIRMS en vivo (últimas 24 h a 5 días) o del historial por mes, coloreados por tipo de incendio, vista conjunta o por sensor (MODIS / VIIRS), mapa satelital, de relieve, oscuro o **3D con la topografía real del Tunari**, temperatura del aire y viento sobre el parque, y qué satélite pasa a continuación |
| Pronóstico | 7 días y 48 horas por sector (temperatura con colores, viento, humedad, lluvia), rosa de vientos y peor momento de la semana |
| Alertas | Regla de clima ajustable (30-30-30 recomendada) calibrada con el clima real de 2025, focos nuevos, puntos ciegos y envío por Telegram |
| Armonización y tipos | Resultado de P2 sobre el historial real, tipos de incendio por temperatura, cobertura por hora y celdas donde más se repite el fuego (P3) |
| Portada del equipo | Portada de P4 |

Los datos se consultan solos cada 5 a 30 minutos (se elige en el menú lateral). Fuentes:
focos de [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/api/), clima, relieve y
clima histórico de [Open-Meteo](https://open-meteo.com/) (sin clave), imágenes
satelitales de Esri y relieve 3D de AWS Terrain Tiles.

Para enviar alertas por Telegram, completa también en `.streamlit/secrets.toml`
`TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` (crea un bot con @BotFather y agrégalo
al grupo del equipo).
