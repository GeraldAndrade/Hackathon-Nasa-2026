# Demostración de P3 · aproximadamente tres minutos

## Preparación

Ejecutar `python src/generar_demo_analisis.py` desde el entorno del proyecto.
Abrir `data/mock/graficos/informe.html` en un navegador. El archivo incluye
los gráficos y no requiere internet. Tener también a mano el informe de
`data/processed/graficos/informe.html`, que muestra el estado real disponible.
Los resultados y las fórmulas están en `README_ANALISIS.md`.

## 0:00–0:35 · Por qué hace falta P3

“P1 descarga y recorta los focos; P2 elimina las coincidencias entre sensores.
Nosotros preguntamos: ¿qué sectores merecen más vigilancia? No basta contar
puntos. Una zona sin focos puede haber tenido pocas oportunidades de ser
observada. Esta pantalla es una simulación, claramente identificada.”

## 0:35–1:10 · Cobertura por horario

Mostrar el gráfico de cobertura por franja y pasar el cursor sobre una barra.

“Agrupamos en cuatro franjas de seis horas, en horario de Bolivia. Contamos
intervalos con observación válida, aunque no haya fuego. Varias observaciones
en un intervalo cuentan una sola vez. Los registros de esta demo son
inventados; los datos reales de FIRMS que descargamos solo contienen focos y
no permiten medir por sí solos la cobertura.”

## 1:10–1:50 · Mapa y prioridad

Mostrar el mapa y el ranking de celdas.

“La recurrencia cuenta intervalos con focos, para que diez píxeles de un mismo
episodio no multipliquen por diez la actividad temporal. Dividimos por los
intervalos observados y combinamos esa tasa con la falta de cobertura. Usamos
60 % de recurrencia y 40 % de falta de cobertura: son pesos del prototipo,
pendientes de validación. El puntaje ayuda a priorizar vigilancia en terreno;
no es una probabilidad de incendio.”

## 1:50–2:25 · Qué sabemos hoy con los datos reales

Cambiar al informe real, con las celdas grises y sin ranking.

“La ventana reciente descargada no contiene focos dentro del Tunari. No
concluimos que el parque esté libre de incendios. Tampoco inventamos cobertura:
el gris significa información insuficiente. Para un resultado histórico real
necesitamos el archivo de detecciones y las máscaras de observación y calidad.”

## 2:25–3:00 · Integración y alcance

“Entregamos una tabla por celda, el detalle por horario y un GeoJSON con IDs
estables para conectarlos con la interfaz. Los cálculos y gráficos se generan
antes de la demo y funcionan sin internet. Las pruebas verifican la asignación
espacial, los cambios de día en UTC, la corrección de recurrencia y los casos
sin datos. El siguiente paso científico es integrar cobertura real y comparar
el resultado con reportes de campo.”

## Respuestas breves para el jurado

- **¿Esto predice incendios?** No. Es una priorización heurística de vigilancia.
- **¿Más focos significan más incendios?** No necesariamente: puede haber varios
  píxeles o pasadas del mismo episodio; distinguimos filas de intervalos activos.
- **¿Por qué hay celdas sin prioridad?** Falta período, evaluación completa o
  alguna observación válida. No se reemplaza lo desconocido por cero.
- **¿Qué validaron?** La lógica y sus casos límite con datos controlados. La
  cobertura y la utilidad operativa reales todavía requieren datos independientes.
- **¿La simulación demuestra el rendimiento real?** No. Sirve para integrar
  P3 con P4 y explicar el método; sus observaciones fueron inventadas.
