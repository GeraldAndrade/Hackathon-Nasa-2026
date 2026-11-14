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

### Guía rápida para probar la rama `appPRUEBA`

La rama `appPRUEBA` reúne el trabajo de todo el equipo encima de `main`:

- La armonización de P2, con la columna `temp_brillo` y los datos de ejemplo.
- La ingesta de P1 y el análisis de P3.
- La app de P4.
- La app en tiempo real: mapa satelital, de relieve, oscuro y 3D; pronóstico;
  alertas con la regla 30-30-30 y envío por Telegram; tipos de incendio por
  temperatura; y consulta automática de NASA FIRMS y Open-Meteo.
- La plantilla `.streamlit/secrets.toml.example`.

1. Traer la rama y cambiarse a ella:

   ```bash
   git fetch origin
   git checkout appPRUEBA
   ```

2. Instalar las dependencias:

   ```bash
   pip install -r requirements.txt
   ```

3. Configurar las claves (opcional, pero necesario para ver focos en vivo).
   El archivo `.streamlit/secrets.toml` **no está en GitHub** porque guarda claves
   y git lo ignora. Cada persona crea el suyo a partir de la plantilla:

   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```

   En Windows (PowerShell): `Copy-Item .streamlit/secrets.toml.example .streamlit/secrets.toml`.
   Después completa `FIRMS_MAP_KEY` con una clave gratuita de
   [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/api/map_key/). Sin clave la app
   funciona igual, pero muestra focos de ejemplo en lugar de los reales.

4. Abrir la app:

   ```bash
   streamlit run app/app.py
   ```

   Se abre en el navegador en `http://localhost:8501`.

### Qué tiene la app

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

Para enviar alertas por Telegram, completa también en `.streamlit/secrets.toml`
`TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` (crea un bot con @BotFather y agrégalo
al grupo del equipo).
