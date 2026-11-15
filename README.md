# Tunari Blindspot · NASA Hackathon 2026

<<<<<<< HEAD
**Armonización de detecciones satelitales para apoyar la vigilancia de incendios en el Parque Nacional Tunari, Cochabamba, Bolivia.**

Tunari Blindspot es un prototipo desarrollado para el desafío **Harmonization of MODIS and VIIRS Hot Spots**. Integra focos de calor de NASA FIRMS, análisis geoespacial y condiciones meteorológicas en una aplicación web. Su objetivo es facilitar la consulta de detecciones y orientar qué sectores requieren mayor vigilancia, teniendo en cuenta las limitaciones de la observación satelital.

Está pensado como apoyo para guardaparques, equipos de monitoreo y personas interesadas en la prevención de incendios. La prioridad calculada es una heurística del prototipo: **no representa una probabilidad de incendio ni reemplaza la verificación en terreno**.

## El problema que aborda

MODIS y VIIRS observan una misma región con distintas resoluciones y horarios. Una detección MODIS puede coincidir con varias detecciones VIIRS, por lo que sumar ambos conjuntos sin procesarlos puede duplicar registros. Además, una zona sin focos registrados puede haber tenido pocas oportunidades de observación.

El proyecto trabaja sobre dos preguntas: **cómo reunir las detecciones de ambos sensores conservando su procedencia** y **cómo orientar la vigilancia sin confundir falta de información con ausencia de fuego**.

## Alcance actual

| Componente | Qué permite hacer |
|---|---|
| Ingesta y recorte territorial (P1) | Descargar detecciones recientes de MODIS y VIIRS desde FIRMS, recortarlas al límite del Tunari y generar una cuadrícula de análisis. |
| Armonización (P2) | Normalizar coordenadas, fechas UTC, confianza y temperatura de brillo; eliminar duplicados exactos y emparejar detecciones entre sensores por cercanía espacial y temporal. |
| Análisis territorial (P3) | Asignar detecciones a celdas, contar intervalos con focos y, cuando existen registros independientes de observación, calcular cobertura, recurrencia corregida y prioridad de vigilancia. |
| Aplicación web (P4) | Explorar mapas 2D y 3D, comparar sensores, consultar el pronóstico por sector y visualizar los resultados de armonización y análisis. |
| Alertas | Evaluar reglas meteorológicas ajustables, mostrar focos recientes y avisos orientativos de intervalos entre pasos satelitales; enviar mensajes por Telegram si se configura y activa esa opción. |
| Demostración | Generar detecciones y observaciones simuladas, además de informes HTML interactivos que pueden abrirse sin conexión. |
=======
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
>>>>>>> origin/ingesta

La implementación está centrada en el **Parque Nacional Tunari**. Adaptarla a otra región requiere cambiar límites, cuadrícula, sectores meteorológicos y parámetros locales.

### Qué muestra la aplicación

- **Mapa en vivo:** detecciones de los últimos 1, 2 o 5 días, vista conjunta o por sensor, filtros por temperatura de brillo, capas de temperatura del aire, viento y prioridad, y bases satelital, de relieve, oscura y 3D.
- **Histórico:** consulta de julio a octubre de 2025 con los archivos disponibles; puede utilizar datos de ejemplo.
- **Pronóstico:** hasta siete días y detalle de las próximas 48 horas por sector, con temperatura, humedad, viento y precipitación.
- **Alertas:** umbrales configurables de temperatura, humedad y viento, comparación con el clima histórico de la temporada 2025 y configuración de Telegram. La regla inicial es 30 °C, 30 % de humedad y 30 km/h de viento.
- **Armonización y tipos:** comparación de detecciones originales y unificadas, categorías orientativas por temperatura de brillo, horarios aproximados de paso y resultados de P3.
- **Portada del equipo:** panel de resumen de los módulos y mapas de detecciones.

## Cómo funciona

```text
NASA FIRMS: MODIS + VIIRS
        |
        v
P1 · Descarga y recorte al parque --> limpio.parquet
        |
        v
P2 · Normalización y coincidencias --> unificada.parquet
        |
        + límite y cuadrícula del Tunari
        + observaciones independientes, si están disponibles
        v
P3 · Análisis por celda y franja horaria
        |
        +--> Parquet + GeoJSON + resumen JSON + informe HTML
        v
P4 · Aplicación Streamlit <-- Open-Meteo: clima y pronóstico
        |
        +--> Mapas 2D/3D y alertas opcionales por Telegram
```

La aplicación también puede consultar FIRMS directamente y armonizar las detecciones en memoria, sin ejecutar previamente los scripts de ingesta.

### Armonización de MODIS y VIIRS

El algoritmo de [src/armonizacion.py](src/armonizacion.py) utiliza por defecto un **radio de 1,5 km** y una **ventana de 60 minutos** para buscar coincidencias entre sensores. Ambos parámetros son configurables.

Cuando encuentra coincidencias, conserva las filas VIIRS por su mayor resolución espacial y las marca como `ambos`; retira las detecciones MODIS emparejadas y conserva las que no tienen pareja. Una detección MODIS puede confirmar varias filas VIIRS: la salida representa **detecciones armonizadas, no un catálogo de incendios individuales**.

La confianza se expresa como `baja`, `nominal` o `alta`. La tabla mantiene coordenadas, fecha UTC, sensor, potencia radiativa del fuego (`frp`, en MW) y, cuando existen, temperatura de brillo en kelvin, satélite y referencias al emparejamiento.

### Cobertura y prioridad de vigilancia

El análisis de [src/analisis.py](src/analisis.py) usa celdas derivadas de una cuadrícula de **0,01°** y cuatro franjas locales de seis horas: `00–06`, `06–12`, `12–18` y `18–24`, en `America/La_Paz`.

Con un período declarado y registros de observación suficientes, calcula:

```text
cobertura = intervalos observados / intervalos esperados
recurrencia corregida = intervalos con focos / intervalos observados
prioridad = 0,6 × recurrencia corregida + 0,4 × (1 − cobertura)
```

El peso de recurrencia es configurable; el peso de falta de cobertura es su complemento. Los registros de observación deben incluir `celda_id`, `fecha_hora` y `observada` (booleana), y permitir distinguir intervalos observados de intervalos evaluados sin observación válida. Para obtener un puntaje se necesita evaluar todos los intervalos del período y contar con alguna observación válida. Si faltan datos, el sistema conserva estados como `sin_observaciones` o `cobertura_incompleta` y deja las métricas no calculables sin valor.

**Las detecciones FIRMS por sí solas no proporcionan esa máscara de observación.** La demostración incluye una máscara simulada para explicar el método.

## Tecnologías y fuentes de datos

| Tecnología o formato | Uso en el proyecto |
|---|---|
| Python | Procesamiento, consultas a servicios externos y lógica de la aplicación. Se recomienda Python 3.11 o superior; el código utiliza `tomllib`. |
| pandas y NumPy | Normalización de tablas, fechas, operaciones numéricas y emparejamiento de detecciones. |
| GeoPandas y Shapely | Recorte territorial, geometrías, cuadrículas, asignación espacial y cálculo de áreas. |
| PyArrow y Parquet | Lectura y escritura de tablas de detecciones y resultados. |
| Streamlit | Aplicación web multipágina, controles, caché y actualización periódica. |
| Folium y streamlit-folium | Mapas 2D con capas, marcadores y controles interactivos. |
| PyDeck | Visualización 3D del terreno y de las detecciones. |
| Plotly | Gráficos interactivos e informes HTML con recursos embebidos. |
| Requests | Consultas HTTP a FIRMS, Open-Meteo y Telegram. |
| GeoJSON y JSON | Límites, geometrías de celdas y resúmenes del análisis. |
| pytest | Pruebas de armonización y análisis territorial. |

Las dependencias de ejecución se encuentran en [requirements.txt](requirements.txt); las de desarrollo, en [requirements-dev.txt](requirements-dev.txt). NumPy y Shapely se utilizan directamente en el código y se instalan como dependencias de pandas y GeoPandas.

Las integraciones implementadas son:

- **NASA FIRMS:** focos de calor de `MODIS_NRT`, `VIIRS_SNPP_NRT`, `VIIRS_NOAA20_NRT` y `VIIRS_NOAA21_NRT`. La consulta en vivo requiere `FIRMS_MAP_KEY`.
- **Open-Meteo:** condiciones actuales, pronóstico, clima histórico y elevaciones; la configuración actual no requiere clave.
- **OpenStreetMap / Nominatim:** obtención del límite del parque en el script de procesamiento de P1.
- **Esri y AWS Terrain Tiles:** imágenes satelitales y relieve para los mapas.
- **Telegram Bot API:** envío opcional de alertas al chat configurado.

## Ejecutar la aplicación

Ejecuta los comandos desde la raíz del repositorio. Necesitas Python y acceso a internet para instalar dependencias y consultar servicios externos.

### 1. Crear el entorno e instalar dependencias

En Windows con PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

En Linux o macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 2. Configurar las integraciones opcionales

Copia [.streamlit/secrets.toml.example](.streamlit/secrets.toml.example) como `.streamlit/secrets.toml`:

```powershell
Copy-Item .streamlit/secrets.toml.example .streamlit/secrets.toml
```

En Linux o macOS, utiliza `cp .streamlit/secrets.toml.example .streamlit/secrets.toml`.

Completa únicamente las integraciones que vayas a utilizar:

```toml
FIRMS_MAP_KEY = "TU_CLAVE_FIRMS"
TELEGRAM_BOT_TOKEN = "TOKEN_DEL_BOT"
TELEGRAM_CHAT_ID = "ID_DEL_CHAT"
```

El archivo de secretos está excluido de Git. La aplicación también admite estas claves como variables de entorno.

Sin clave FIRMS, el mapa utiliza archivos históricos disponibles o datos de ejemplo. Telegram requiere las dos variables correspondientes y activar el envío desde la página de alertas.

### 3. Iniciar Streamlit

```bash
python -m streamlit run app/app.py
```

Abre `http://localhost:8501`. En el menú lateral se puede elegir una actualización cada 5, 10, 15 o 30 minutos, o forzar una consulta. La actualización depende de la sesión de Streamlit; el repositorio no implementa un servicio independiente de alertas en segundo plano.

## Procesamiento y demostración

### Probar con datos simulados

El repositorio incluye archivos de ejemplo en `data/mock/`. Para regenerarlos:

```bash
python src/generar_mock.py --semilla 42 --anios 2021 2025
python src/generar_demo_analisis.py
```

El primer comando genera detecciones sintéticas y su tabla armonizada. El segundo simula observaciones para septiembre de 2025 y genera los resultados de P3 dentro de `data/mock/`. Estos comandos sobrescriben los archivos de demostración correspondientes.

Puedes abrir [el informe de demostración](data/mock/graficos/informe.html) sin conexión. También hay un [guion de demostración de P3](docs/GUION_DEMO_P3.md).

### Procesar detecciones propias

Con un archivo `limpio.parquet` de P1 o una tabla Parquet con las columnas FIRMS compatibles:

```bash
python src/armonizacion.py --entrada firms/limpio.parquet --salida data/processed/unificada.parquet --radio-km 1.5 --ventana-min 60
python src/analisis.py --entrada data/processed/unificada.parquet
```

Sin observaciones independientes, el segundo comando asigna detecciones a las celdas y genera resultados descriptivos, dejando cobertura y prioridad desconocidas. Para calcularlas, proporciona también `--inicio`, `--fin` (fechas locales inclusivas en formato `YYYY-MM-DD`) y `--observaciones` con la ruta al Parquet de observaciones.

La ingesta inicial está implementada en `firms/descargar-firms.py`, `firms/procesar-firms.py` y `firms/crear-cuadricula.py`; `src/ingesta.py` está vacío. Los scripts de `firms/` usan rutas relativas y deben ejecutarse desde esa carpeta. El descargador tiene su propia configuración de clave, región y días dentro del archivo y no utiliza los secretos de Streamlit. Revisa esos valores antes de ejecutarlo y evita publicar credenciales. El procesamiento genera `firms/limpio.parquet`, mientras que P2 busca por defecto `data/processed/limpio.parquet`; por eso el ejemplo indica la entrada explícitamente.

### Archivos de salida

| Archivo | Contenido |
|---|---|
| `limpio.parquet` | Detecciones de entrada recortadas al parque. |
| `unificada.parquet` | Detecciones armonizadas de MODIS y VIIRS. |
| `prioridad.parquet` | Conteos, métricas, estado y ubicación representativa por celda. |
| `cobertura.parquet` | Detalle de cobertura y recurrencia por celda y franja horaria. |
| `detecciones_por_celda.parquet` | Relación entre cada detección asignada y su celda. |
| `celdas_analisis.geojson` | Geometrías con identificadores `celda_id` para unirlas a los resultados. |
| `resumen_analisis.json` | Período, procedencia, parámetros, conteos y advertencias. |
| `graficos/informe.html` | Informe interactivo autónomo del análisis. |

## Estructura del repositorio

```text
app/                  Aplicación Streamlit, mapas, estilos y acceso a servicios
  app.py              Punto de entrada de la aplicación multipágina
  paginas/            Mapa, pronóstico, alertas y análisis
src/                  Armonización, análisis y generadores de datos simulados
firms/                Scripts de ingesta, límite del parque y cuadrícula
data/processed/       Resultados del procesamiento de entradas reales
data/mock/            Datos y resultados de demostración simulados
docs/                 Guion de demostración
tests/                Pruebas de P2 y P3
.streamlit/           Configuración visual y plantilla de secretos
```

La aplicación busca primero resultados útiles en `data/processed/` y puede recurrir a `data/mock/` cuando no hay archivos o valores utilizables. Por ello, **una misma sesión puede combinar clima consultado en línea con focos o prioridades simuladas**; revisa las etiquetas de procedencia de cada vista.

## Limitaciones y trabajo pendiente

- **Estado de prototipo:** los resultados apoyan la exploración y la demostración. No hay un modelo entrenado para predecir incendios, propagación o superficie quemada.
- **Cobertura real pendiente:** el resumen incluido en `data/processed/resumen_analisis.json` registra cero detecciones de entrada y ausencia de observaciones independientes. Los puntajes de demostración no acreditan cobertura ni utilidad operativa reales.
- **Horarios orientativos:** los próximos pasos y avisos de puntos ciegos usan horarios aproximados fijos; no calculan órbitas del día ni verifican nubosidad u observación efectiva.
- **Clasificación orientativa:** las categorías de incendio se basan en umbrales de temperatura de brillo del píxel. No miden directamente la temperatura de las llamas ni validan el tipo de vegetación o incendio.
- **Dependencia de fuentes externas:** las consultas en vivo, el clima y las bases cartográficas necesitan conexión y disponibilidad de sus proveedores. Actualizar el panel no garantiza una nueva observación satelital.
- **Validación pendiente:** se necesitan máscaras reales de observación y calidad, historial de detecciones y comparación con reportes de campo para evaluar y ajustar la prioridad y las reglas de alerta.

## Pruebas

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
```

Las pruebas cubren normalización de confianza y coincidencias entre sensores, asignación espacial sin doble conteo en bordes, conversión entre UTC y hora boliviana, cálculo de métricas, manejo de datos incompletos y procedencia de simulaciones. Verifican la lógica del software; no sustituyen la validación científica o en terreno.
