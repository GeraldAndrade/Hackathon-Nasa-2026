# P2 · Armonización de MODIS y VIIRS

Módulo del proyecto **Tunari Blindspot** (NASA Space Apps Challenge 2026, Cochabamba).

Toma los focos de calor de los dos sensores, que P1 deja en `limpio.parquet`, y los une en **una sola tabla sin duplicados**: `unificada.parquet`. Cada detección queda marcada según quién la vio: **ambos**, **solo VIIRS** o **solo MODIS**.

---

## Qué hace, en palabras simples

MODIS ve el terreno con píxeles de unos 1 km y VIIRS con píxeles de 375 m. Cuando los dos ven el mismo incendio, aparece dos veces en las listas de FIRMS. La armonización:

1. **Normaliza** los dos sensores al mismo formato: coordenadas, fecha y hora en UTC, sensor y satélite.
2. **Armoniza la confianza.** MODIS entrega un porcentaje y VIIRS una letra. Usamos la equivalencia oficial de FIRMS:

   | MODIS (%) | VIIRS | Resultado |
   |---|---|---|
   | 0 a 29 | `l` | `baja` |
   | 30 a 79 | `n` | `nominal` |
   | 80 a 100 | `h` | `alta` |

3. **Empareja** cada detección MODIS con las detecciones VIIRS que estén a **1,5 km o menos** y a **60 minutos o menos** de diferencia.
4. **Elimina duplicados.**
   - Si una detección MODIS tiene pareja, se descarta y las detecciones VIIRS que la confirman quedan como `ambos`. Así se conserva la ubicación más precisa, la de VIIRS.
   - Las detecciones sin pareja quedan como `VIIRS` o `MODIS`.

Solo se emparejan sensores distintos. Los píxeles VIIRS vecinos no se fusionan entre sí, para que incendios distintos no terminen encadenados en uno solo y P3 pueda contar focos por celda.

---

## Archivos

| Archivo | Qué es |
|---|---|
| `src/armonizacion.py` | El algoritmo y el programa que se ejecuta desde la terminal |
| `src/generar_mock.py` | Genera datos de ejemplo del Tunari para probar sin esperar a los reales |
| `tests/test_armonizacion.py` | Pruebas con casos inventados |
| `data/mock/limpio.parquet` | Datos de ejemplo con el mismo formato que la salida de P1 |
| `data/mock/unificada.parquet` | Resultado de la armonización sobre los datos de ejemplo |

---

## Cómo usarlo

Instalar las dependencias (solo hacen falta estas tres para este módulo):

```bash
pip install pandas pyarrow pytest
```

Armonizar los datos reales de P1:

```bash
python src/armonizacion.py --entrada firms/limpio.parquet
```

Por defecto lee `data/processed/limpio.parquet` y escribe `data/processed/unificada.parquet`. Las opciones son:

| Opción | Por defecto | Para qué |
|---|---|---|
| `--entrada` | `data/processed/limpio.parquet` | Archivo de P1 |
| `--salida` | `data/processed/unificada.parquet` | Dónde guardar el resultado |
| `--radio-km` | `1.5` | Distancia máxima para considerar dos detecciones como el mismo foco |
| `--ventana-min` | `60` | Diferencia máxima de tiempo, en minutos |

Regenerar los datos de ejemplo:

```bash
python src/generar_mock.py
```

Correr las pruebas:

```bash
python -m pytest tests -q
```

---

## Formato de entrada

Acepta los dos formatos posibles de `limpio.parquet`:

- **Columnas originales de FIRMS**, que es lo que entrega P1 hoy: `latitude`, `longitude`, `acq_date`, `acq_time`, `satellite`, `instrument`, `confidence`, `frp` y `sensor_origen`.
- **Columnas del contrato del equipo:** `id`, `latitud`, `longitud`, `fecha_hora`, `sensor`, `confianza` y `frp`.

---

## Formato de salida: `unificada.parquet`

Columnas del contrato, que la interfaz usa:

| Columna | Descripción |
|---|---|
| `id_unificado` | Identificador único (`U000001`, …) |
| `latitud`, `longitud` | Ubicación (de VIIRS cuando la ven ambos) |
| `fecha_hora` | Fecha y hora en UTC (Bolivia es UTC-4) |
| `sensor_visto` | `ambos`, `VIIRS` o `MODIS` |
| `confianza` | `baja`, `nominal` o `alta` |
| `frp` | Potencia radiativa del fuego, en MW, del sensor de la fila |

Columnas extra para revisar los resultados (la interfaz puede ignorarlas):

| Columna | Descripción |
|---|---|
| `satelite` | Terra, Aqua, S-NPP, NOAA-20 o NOAA-21 |
| `id_origen` | Fila de `limpio.parquet` de la que viene |
| `id_modis`, `frp_modis` | Detección MODIS que la confirma, si la hay |
| `distancia_km`, `desfase_min` | Qué tan lejos y cuántos minutos después o antes estaba esa detección MODIS |

---

## Resultados con los datos de ejemplo

Los datos de ejemplo simulan 5 años (2021 a 2025) con 223 incendios dentro del límite real del parque. Incluyen las horas de paso de cada satélite, nubes, incendios chicos que MODIS no ve y falsas alarmas. Como cada detección guarda el incendio que la causó, se puede comprobar si el algoritmo acierta.

| | Cantidad |
|---|---|
| Detecciones simuladas | 5.224 (679 MODIS y 4.545 VIIRS) |
| Detecciones unificadas | 4.910 |
| Vistas por ambos sensores | 2.264 |
| Solo VIIRS | 2.281 |
| Solo MODIS (casi todas de Terra a las 10:30, cuando no pasa ningún VIIRS) | 365 |
| Pares MODIS-VIIRS formados que son del mismo incendio | 100 % |
| MODIS que quedaron solos teniendo un VIIRS del mismo incendio a 60 minutos o menos | 0 |

En los datos de ejemplo nosotros controlamos cuánto se desvían las posiciones. Por eso estos resultados prueban que la lógica funciona, pero **el radio de 1,5 km y la ventana de 60 minutos hay que confirmarlos con los datos reales**.

---

## Pendientes

- **Datos reales.** Hoy `firms/limpio.parquet` tiene 0 focos, porque la API de tiempo casi real solo entrega los últimos 5 días. Hace falta el historial de los productos de archivo (`MODIS_SP`, `VIIRS_SNPP_SP`, `VIIRS_NOAA20_SP`) o la descarga *Archive Download* de FIRMS.
- **Zona de descarga.** El BBOX que usa la ingesta (`-66.5,-17.5,-65.8,-17.0`) no cubre todo el parque. El Tunari llega a la longitud -66.74 y a la latitud -16.90. Se propone `-66.75,-17.56,-65.90,-16.90`.
- **Ajuste.** Cuando lleguen los datos reales, revisar cómo se reparten `distancia_km` y `desfase_min` para afinar el radio y la ventana.
