# P3 · Análisis de cobertura y prioridad de vigilancia

P3 asigna las detecciones unificadas de P2 a la cuadrícula de P1 y entrega
`prioridad.parquet`, con las seis columnas acordadas. Añade el detalle por
franja horaria, las métricas de recurrencia, un informe gráfico autónomo y
un [guion de demostración](docs/GUION_DEMO_P3.md). No modifica los módulos de P1, P2 o P4.

## Qué podemos medir con los archivos actuales

`unificada.parquet` contiene focos detectados, no todos los pasos u observaciones
del satélite. **Contar focos no mide cobertura.** Las nubes, humo, horario y
resolución pueden impedir una detección. Véanse las
[notas oficiales de NASA FIRMS](https://firms2.modaps.eosdis.nasa.gov/alerts/notes.php)
y la [respuesta del equipo Earthdata sobre observaciones faltantes](https://forum.earthdata.nasa.gov/viewtopic.php?t=5177).

Por eso P3 funciona en dos modos:

- **Datos reales sin máscara de observación:** calcula focos por celda y por
  franja; cobertura, recurrencia corregida y prioridad quedan nulas. El gris
  significa información insuficiente. No significa riesgo bajo.
- **Con registros independientes de observación:** calcula cobertura y prioridad
  cuando el período está completamente evaluado. La demo incluye registros
  inventados, separados en `data/mock/` y marcados como simulación.

La ingesta actual del Tunari tiene cero detecciones. El programa produce un
resultado válido para las 2.977 celdas, sin inventar focos ni cobertura.
Para un análisis histórico real falta el historial señalado por P2 y una
fuente de cobertura independiente (huellas/máscaras y calidad de observación).
La descarga y conversión de esos productos no están incluidas en P1/P2 actuales.

## Ejecución

Desde la raíz del repositorio, con Python y `requirements.txt` instalados:

```powershell
# Windows: usar el entorno local creado para el proyecto
.\.venv\Scripts\python.exe -X utf8 src/armonizacion.py --entrada firms/limpio.parquet
.\.venv\Scripts\python.exe -X utf8 src/analisis.py

# Demo de P3 con las detecciones mock existentes de P2
.\.venv\Scripts\python.exe -X utf8 src/generar_demo_analisis.py

# Pruebas de ambos módulos
.\.venv\Scripts\python.exe -X utf8 -m pytest tests -q
```

El primer comando solo ejecuta el módulo existente de P2 para materializar
`data/processed/unificada.parquet`; no cambia su código. El segundo escribe
el análisis real en `data/processed/`. Sin período declarado, los conteos
abarcan toda la entrada, pero no se calculan tasas temporales.

La demo usa septiembre de 2025 del mock existente y semilla 42. No regenera
`limpio.parquet` ni `unificada.parquet`. Puede cambiarse con `--inicio`, `--fin`
y `--semilla`. Si falta el mock de P2, se genera primero con
`python src/generar_mock.py`.

Cuando se disponga de observaciones reales:

```powershell
.\.venv\Scripts\python.exe -X utf8 src/analisis.py --observaciones data/processed/observaciones.parquet --inicio 2025-09-01 --fin 2025-09-30
```

Opciones: `--entrada`, `--celdas`, `--limite`, `--observaciones`, `--inicio`,
`--fin`, `--salida`, `--graficos`, `--sin-graficos`, `--peso-recurrencia` y
`--datos-simulados`. Las rutas por defecto se resuelven desde el repositorio,
aunque se ejecute desde otra carpeta. Las fechas son días locales inclusivos.
Con observaciones es obligatorio indicar ambas fechas; nunca se deduce el
denominador a partir de las fechas de los incendios.

## Contrato de observaciones

El archivo opcional `observaciones.parquet` debe contener:

| Columna | Tipo | Significado |
|---|---|---|
| `celda_id` | texto | ID de `celdas_analisis.geojson` |
| `fecha_hora` | timestamp UTC | Instante que identifica un intervalo local de seis horas |
| `observada` | booleano sin nulos | Hubo una observación térmica utilizable de la celda en ese intervalo |
| `datos_simulados` | booleano opcional | Propaga la etiqueta de simulación a las salidas |

Se consideran cuatro franjas locales: 00–06, 06–12, 12–18 y 18–24,
en `America/La_Paz` (UTC−4). Una fecha sin zona en la entrada se interpreta
como UTC, igual que en el contrato de P2.

La fuente debe definir una regla consistente para declarar una celda
observable, incluyendo huella espacial y calidad/nubes. Un registro positivo
es evidencia de observación útil, no simplemente un horario nominal de paso.
Un negativo certifica que se evaluó **todo el intervalo y la unión de sensores**
sin encontrar observación útil. Que un sensor esté tapado no prueba que todos
lo estuvieran. Un registro positivo prevalece sobre negativos del mismo
intervalo y los duplicados no suman cobertura.

**Un intervalo ausente es desconocido, nunca un negativo.** La cobertura
puntual solo se publica si hay evaluación para todos los intervalos del
período. Para cobertura parcial se publican límites mínimo y máximo, pero
no se asigna prioridad. Todos los intervalos con focos deben tener una
observación válida; se rechazan máscaras que contradigan esa evidencia.

Esta métrica mide intervalos con al menos una observación útil: no representa
vigilancia continua durante seis horas ni garantiza detectar todos los fuegos.

## Cálculos reproducibles

Cada detección se asigna a una celda. En una arista compartida se usa el menor
`celda_id`, de modo que cuenta una sola vez. Las celdas se recortan al límite
del parque antes del cruce: un punto fuera del parque no entra por estar en
una celda de borde. Los puntos excluidos se informan en el resumen.

Los IDs existentes se conservan. Si P1 no entrega IDs, se generan con un hash
de la geometría original normalizada, independiente del orden de las filas.
P4 debe usar el GeoJSON de salida, sin deducir IDs a partir del índice de P1.
Ubicaciones representativas y áreas se calculan en UTM 19S (EPSG:32719) y se
publican latitud/longitud en EPSG:4326. Los puntos representativos quedan
dentro de las geometrías recortadas.

Para cada celda y para cada franja:

- `N`: intervalos esperados. Para una franja son los días inclusivos del período;
  para una celda completa, cuatro veces ese número.
- `E`: intervalos con estado evaluado, positivo o negativo.
- `O`: intervalos con alguna observación válida.
- `F`: intervalos distintos con al menos un foco unificado.
- `focos`: número de filas de P2 asignadas. Varios píxeles del mismo incendio
  pueden ser varias filas; no es un número de incendios únicos.

```text
fraccion_evaluada       = E / N
cobertura_minima        = O / N
cobertura_maxima        = (O + N - E) / N
cobertura               = O / N                  solo si E = N
recurrencia_observada   = F / N
recurrencia_corregida   = F / O                  solo si E = N y O > 0
prioridad              = 0.6 * recurrencia_corregida + 0.4 * (1 - cobertura)
```

Contar intervalos activos evita que varios píxeles o sensores en la misma
celda/franja inflen la recurrencia. La corrección es una tasa condicionada a
la observación, no una estimación validada del número real de incendios.
Los pesos son una decisión heurística del prototipo y pueden cambiarse con
`--peso-recurrencia` (0 a 1). No se ajustaron ni validaron con incendios reales.

Ejemplo: una celda tiene cuatro intervalos, dos observados y uno con focos.
Su cobertura es 0,5, recurrencia observada 0,25, recurrencia corregida 0,5
y prioridad 0,5. Aunque haya diez píxeles en ese mismo intervalo, `F` sigue
siendo uno. Con cero intervalos observados la cobertura puede ser cero, pero
la recurrencia corregida y la prioridad siguen siendo nulas.

Estados de salida: `sin_periodo`, `sin_observaciones`, `cobertura_incompleta`,
`sin_cobertura` y `completa`. El puntaje está en [0, 1] cuando es calculable;
los valores nulos no se deben rellenar con cero.

## Entregables para P4

Cada ejecución genera los siguientes archivos junto a `prioridad.parquet`:

| Archivo | Uso |
|---|---|
| `prioridad.parquet` | Una fila por celda; contrato `celda_id, latitud, longitud, focos, cobertura, prioridad` más métricas, estado y procedencia |
| `cobertura.parquet` | Cuatro filas por celda, con `franja`, `franja_local`, conteos y tasas |
| `detecciones_por_celda.parquet` | Filas de P2 dentro del período/parque con celda, día y franja asignados |
| `celdas_analisis.geojson` | Geometrías recortadas con IDs, coordenadas representativas y área |
| `resumen_analisis.json` | Período, entradas, exclusiones, pesos, procedencia y advertencias |
| `graficos/informe.html` | Mapa, cobertura por franja, ranking y serie temporal; funciona sin internet |

El mapa del informe usa marcadores en la ubicación representativa de cada
celda, con ejes de longitud y latitud; no necesita teselas ni topología de un
servidor. Las geometrías completas se entregan por separado para el mapa de P4.

Las tablas de métricas incluyen `datos_simulados`, `inicio_local` y `fin_local`.
Se unen a las geometrías mediante `celda_id`, nunca por orden de filas.
P4 debe mostrar nulos en gris, conservar la etiqueta de simulación, limitar el
ranking a puntajes no nulos y leer `estado` para explicar los datos faltantes.
La cobertura media del gráfico usa solo celdas con evaluación completa y
muestra el número de celdas evaluables en el detalle al pasar el cursor.

Las salidas reales van en `data/processed/` y las simuladas en `data/mock/`.
La CLI rechaza guardar entradas marcadas como simulación fuera de un
directorio `mock`. No se sustituye automáticamente una salida real desconocida
por una simulación: la elección debe ser visible para quien usa la interfaz.

## Párrafo para README y presentación

P3 convierte los focos armonizados en conteos por celda y franja horaria del
Tunari. Con registros independientes de observación calcula qué proporción
de intervalos tiene cobertura, corrige la recurrencia por esos intervalos y
combina la actividad observada con la falta de cobertura en un puntaje de
prioridad de vigilancia. Si falta información, lo muestra como desconocido.
La demostración usa observaciones simuladas identificadas; el resultado
orienta dónde vigilar y no predice dónde ocurrirá un incendio.
