# Tunari Blindspot: plan de desarrollo

Proyecto para el NASA International Space Apps Challenge 2026, sede Cochabamba.
Desafío elegido: **Harmonization of MODIS and VIIRS Hot Spots** (enfoque local).

Este documento explica **qué vamos a construir, cómo, quién hace cada parte y por qué usamos Python**. Está escrito para que cualquier persona del equipo, del jurado o de la organización lo entienda sin ser experta en datos satelitales.

---

## 1. El problema, en palabras simples

Los satélites detectan zonas muy calientes en la superficie de la Tierra (posibles incendios). Dos de los satélites más usados son:

- **MODIS**, que ve el terreno con celdas de aproximadamente 1 km.
- **VIIRS**, que lo ve con más detalle, con celdas de aproximadamente 375 m.

Cada uno entrega su propia lista de detecciones, con formatos, resoluciones y horarios distintos. Para quien debe vigilar un bosque, esto genera dos problemas:

1. **Las listas se repiten y se contradicen.** Un mismo incendio puede aparecer dos veces, o solo en una de las dos listas.
2. **Que no aparezca un foco no significa que no hubo fuego.** Puede que ningún satélite haya pasado por ahí en ese momento. Una zona "tranquila" en el mapa puede ser en realidad una zona **que nadie estaba mirando**.

Nuestra zona de estudio es el **Parque Nacional Tunari**, el cerro que rodea Cochabamba.

---

## 2. Qué vamos a construir

Una aplicación web que hace tres cosas:

1. **Armoniza.** Une las detecciones de MODIS y VIIRS en una sola tabla, sin duplicados, y marca cada detección como "vista por ambos satélites" o "vista por uno solo".
2. **Mide la cobertura.** Calcula en qué zonas y en qué horas del día el Tunari se observa poco, o sea, dónde están los **puntos ciegos**.
3. **Prioriza.** Combina el historial de focos con esa cobertura para señalar los sectores que merecen **mayor vigilancia en terreno**.

Importante: el resultado es un **mapa de prioridad de vigilancia**, no una predicción exacta de dónde habrá un incendio.

---

## 3. Por qué usamos Python

Todo el proyecto está escrito en **Python**, de principio a fin. Estas son las razones.

### 3.1. Es el lenguaje de los datos
Python es el lenguaje más usado para ciencia de datos y análisis geoespacial. Las herramientas que necesitamos ya existen, están probadas y están bien documentadas:

| Necesidad | Herramienta de Python |
|---|---|
| Leer, limpiar y unir tablas | pandas |
| Trabajar con coordenadas y mapas | GeoPandas |
| Guardar tablas grandes de forma compacta | PyArrow (formato parquet) |
| Mapas interactivos | Folium |
| Gráficos | Plotly |
| La aplicación web | Streamlit |

### 3.2. Un solo lenguaje para todo el equipo
Las cuatro personas trabajan en Python. Eso significa que los resultados de una persona se conectan con el trabajo de la siguiente **sin traducir nada**: lo que produce la ingesta lo lee directamente la armonización, y así hasta la interfaz.

### 3.3. La interfaz también se escribe en Python
Con **Streamlit**, la página web se construye con el mismo código Python, sin necesidad de escribir HTML, CSS ni JavaScript. Esto reduce muchísimo el tiempo de desarrollo, que en un hackathon de 24 horas es el recurso más escaso.

### 3.4. No necesitamos un servidor aparte
Streamlit hace de interfaz y de servidor al mismo tiempo. Los cálculos pesados se hacen antes, en el computador de cada integrante, y dejan sus resultados en archivos. La aplicación solo los lee y los muestra. Por eso la demo es rápida y no depende de internet ni de servicios externos.

### 3.5. Qué sacrificamos y por qué lo aceptamos
Un framework web como Next.js con TypeScript ofrece más libertad de diseño, pero exigiría montar una API aparte para conectar con los datos y desplegar dos servicios en lugar de uno. En 24 horas, ese riesgo no compensa. Si el proyecto continúa después del hackathon, esa migración es posible.

---

## 4. Cómo se organiza el equipo

Cuatro personas, cuatro roles. Cada archivo tiene **un solo dueño**: nadie edita el archivo de otro, solo lo lee.

| Rol | Hace | Entrega |
|---|---|---|
| **P1 · Ingesta** | Descarga los datos de NASA FIRMS (MODIS y VIIRS) del Tunari, los limpia, los filtra con el límite del parque y crea la cuadrícula de celdas. Al final, realiza una prueba de validación | `limpio.parquet`, `limite.geojson`, `celdas.geojson` |
| **P2 · Armonización** | Une los dos sensores, elimina duplicados por cercanía en tiempo y espacio y etiqueta cada detección. Construye las páginas del comparador y de detecciones unificadas | `unificada.parquet` |
| **P3 · Análisis** | Calcula la cobertura por celda y franja horaria, la recurrencia corregida y el puntaje de prioridad. Prepara los gráficos finales y el guion de la demostración | `prioridad.parquet` |
| **P4 · Interfaz** | Construye la aplicación en Streamlit, el tema visual, la navegación y las páginas de mapa, cobertura y zonas prioritarias. Despliega y sube la entrega | Aplicación publicada |

Además, **cada persona redacta un párrafo corto de su módulo** para el README y la presentación, de modo que nadie cargue con todo el texto al final.

---

## 5. Cómo viajan los datos

```
NASA FIRMS (MODIS + VIIRS)
        |
        v
P1 Ingesta  ------------->  limpio.parquet
        |
        v
P2 Armonización  -------->  unificada.parquet
        |
        v
P3 Análisis  ------------>  prioridad.parquet
        |
        v
P4 Interfaz (Streamlit)  ->  aplicación publicada  ->  entrega final
```

La interfaz lee tanto `unificada.parquet` (para el mapa histórico y el comparador) como `prioridad.parquet` (para las zonas prioritarias y la cobertura).

---

## 6. Estructura del repositorio

```
Hackaton-Nasa-2026/
├── .streamlit/
│   └── config.toml          tema visual de la app
├── app/
│   ├── main.py              portada de la aplicación
│   ├── estilo.py            colores y funciones visuales compartidas
│   ├── datos.py             lectura y validación de archivos
│   └── pages/
│       ├── 1_Mapa_historico.py
│       ├── 2_Comparador.py
│       ├── 3_Cobertura.py
│       └── 4_Zonas_prioritarias.py
├── src/
│   ├── ingesta.py           P1
│   ├── armonizacion.py      P2
│   ├── analisis.py          P3
│   └── generar_mock.py      datos de ejemplo para probar la app
├── data/
│   ├── raw/                 descargas originales (no se suben a GitHub)
│   ├── processed/           resultados reales
│   └── mock/                datos falsos para desarrollar la interfaz
├── docs/
├── requirements.txt
└── README.md
```

---

## 7. Los archivos compartidos

Estos tres archivos son el **acuerdo entre las personas del equipo**. Si alguien necesita cambiar una columna, avisa antes a todos.

| Archivo | Columnas |
|---|---|
| `limpio.parquet` | `id`, `latitud`, `longitud`, `fecha_hora` (UTC), `sensor`, `confianza`, `frp` |
| `unificada.parquet` | `id_unificado`, `latitud`, `longitud`, `fecha_hora`, `sensor_visto` (MODIS, VIIRS o ambos), `confianza`, `frp` |
| `prioridad.parquet` | `celda_id`, `latitud`, `longitud`, `focos`, `cobertura`, `prioridad` (de 0 a 1) |

Pendiente de decidir entre P1 y P2: la columna `confianza`, porque MODIS la entrega como un porcentaje y VIIRS como una categoría (baja, nominal o alta).

Mientras los datos reales no estén listos, la interfaz usa **datos de ejemplo** de `data/mock/` con las mismas columnas. Cuando llegan los reales a `data/processed/`, los reemplazan automáticamente.

---

## 8. Cómo trabajamos en equipo con Git

- La rama **`main`** es la versión compartida del proyecto. Nadie sube directamente a ella.
- Cada persona trabaja en **su propia rama**: `p1-ingesta`, `p2-armonizacion`, `p3-analisis` y `p4-interfaz`.
- Para unir su trabajo, cada persona abre un **Pull Request** en GitHub y lo fusiona con `main`.
- Cada una o dos horas, todos traen lo nuevo de los demás con `git fetch origin` y `git merge origin/main`.
- Los cambios pequeños y frecuentes evitan conflictos.
- Nunca se suben claves ni la carpeta `data/raw/`.

---

## 9. Fases del desarrollo

1. **Preparación.** Repositorio, ramas, roles y acuerdo sobre las columnas de los archivos. Se generan datos de ejemplo para que la interfaz avance desde el inicio.
2. **Datos.** P1 entrega primero una muestra pequeña (un año de datos) para que los demás no esperen, y después el conjunto completo.
3. **Armonización.** P2 construye el algoritmo con la muestra y lo completa con los datos reales.
4. **Análisis.** P3 calcula cobertura, recurrencia y prioridad.
5. **Interfaz.** P4 construye la aplicación sobre datos de ejemplo y luego conecta los reales.
6. **Integración.** Se unen todas las ramas, se prueba la aplicación completa y se publica.
7. **Entrega.** Se pule, se graba un video de respaldo, se ensaya la demostración y se sube el proyecto a la plataforma de Space Apps con margen suficiente.

El alcance se **congela** a la mitad del tiempo: después de ese punto solo se corrigen errores y se pule.

---

## 10. Qué incluye y qué no

**Incluye:**
- Armonización de MODIS y VIIRS para el Parque Nacional Tunari.
- Mapa histórico de focos de calor.
- Análisis de cobertura satelital por zona y hora.
- Mapa de zonas prioritarias de vigilancia.
- Validación con una prueba retrospectiva, si el tiempo alcanza.

**No incluye (trabajo futuro):**
- Predicción de incendios.
- Integración de vegetación, pendiente y elevación.
- Reportes de campo desde el celular.
- Datos en tiempo real.

---

## 11. Riesgos y plan B

| Riesgo | Qué haremos |
|---|---|
| La descarga de datos se demora o falla | Trabajar con la muestra pequeña y usar datos de ejemplo mientras tanto |
| La armonización completa no alcanza | Entregar una versión simple (deduplicación por distancia y hora) y mejorarla si queda tiempo |
| La instalación de GeoPandas falla en algún computador | Cada persona instala solo lo que necesita su parte |
| Falla internet durante la demostración | Los datos están precalculados y hay un video de respaldo |
| Conflictos al unir ramas | Un solo dueño por archivo y uniones frecuentes |

---

## 12. Glosario

- **Foco de calor:** punto del terreno que un satélite detecta como anormalmente caliente. Puede ser un incendio, pero no siempre.
- **FIRMS:** sistema de la NASA que publica los focos de calor detectados por los satélites.
- **MODIS y VIIRS:** dos instrumentos satelitales que detectan focos de calor, con distinta resolución y horarios de paso.
- **Armonizar:** unir datos de fuentes distintas en una sola tabla coherente, sin duplicados.
- **Cobertura satelital:** cuánto y cuándo se observa una zona desde el espacio.
- **Punto ciego:** zona u hora en que hay poca observación, donde la ausencia de focos no es una buena señal.
- **Parquet:** formato de archivo compacto y rápido para guardar tablas.
- **Pull Request:** solicitud en GitHub para fusionar el trabajo de una rama con la rama principal.
