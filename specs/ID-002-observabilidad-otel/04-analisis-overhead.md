# Fase 4 — Análisis de overhead de OpenTelemetry

## Objetivo

Cuantificar el efecto de la instrumentación OTel sobre la latencia y el consumo de recursos de `catalog` y `orders`, comparando dos ejecuciones equivalentes: OTel habilitado y deshabilitado. Esta especificación define el experimento; no contiene mediciones. Los resultados y cualquier conclusión se completan solo después de ejecutar y conservar la evidencia.

## Alcance y controles

- Ejecutar en Docker Compose local; el benchmark no apunta a ECS ni a servicios externos.
- Mantener igual código funcional, imagen base, dependencias, versión de Python, configuración de PostgreSQL, recursos de contenedor, dataset, máquina anfitriona y carga entre variantes.
- Introducir una opción `OTEL_ENABLED` en ambas APIs, con valor por defecto `true`. `false` deshabilita providers/exporters, instrumentación automática (FastAPI, HTTPX y SQLAlchemy) y generación de spans de negocio. La ruta funcional, las consultas a DB, respuestas, logging de aplicación y configuración de procesos deben permanecer equivalentes. El modo sin OTel no inicia el endpoint Prometheus.
- Mantener Collector, PostgreSQL y generador k6 en las mismas condiciones para las dos variantes. El Collector no debe formar parte de las muestras de CPU/memoria de las APIs; con OTel apagado no debe recibir exportaciones de las APIs.
- Usar datos sembrados una sola vez antes de cada par comparativo. La carga medida usa solo lecturas para que el tamaño/estado de la base no cambie durante la muestra.
- No cambiar el número de workers, límites de CPU/memoria, niveles de logging ni volumen de datos entre variantes. Registrar las diferencias inevitables del host o del runtime.

## Carga de trabajo

El script `scripts/benchmark/overhead.js` de k6 debe ejercer ambos servicios con distribución fija y etiquetas por API/ruta:

| API | Operación | Endpoint | Requisito |
|---|---|---|---|
| Catalog | Lectura de producto | `GET /products/{product_id}` | Usar un producto semilla existente; esperar `200`. |
| Orders | Lectura de pedido | `GET /orders/{order_id}` | Usar un pedido semilla existente; esperar `200`. |

La configuración toma hosts e IDs desde variables de entorno, no contiene credenciales ni IDs efímeros versionados. Se usa un escenario de tasa de llegada constante; la tasa objetivo se elige en un piloto común a ambas variantes, por debajo de la capacidad estable observada y sin iteraciones descartadas. Fijar la misma tasa, duración, VUs preasignados/máximos, timeout y proporción de rutas en cada corrida. No introducir umbrales absolutos de latencia sin un SLO aprobado.

## Protocolo de ejecución

1. Registrar commit, estado de trabajo, versiones de Docker Compose/k6/Python, CPU y memoria del host, límites efectivos de contenedor, número de workers y variables no sensibles que afectan el runtime. No guardar secretos.
2. Levantar Compose y crear el dataset semilla; comprobar que las dos lecturas devuelven `200`. Hacer un piloto corto para escoger una tasa común sostenible; excluir el piloto de resultados.
3. Para cada variante, recrear solo las APIs con el mismo código/configuración salvo `OTEL_ENABLED`; esperar readiness y ejecutar el mismo calentamiento sin incluirlo en el intervalo medido.
4. Ejecutar al menos tres rondas medidas por variante, alternando el orden (por ejemplo, OTel → sin OTel → sin OTel → OTel). Cada ronda usa la misma carga y duración. Guardar un JSON de resultados k6 por ronda y una serie temporal de `docker stats` para los contenedores `catalog` y `orders` durante todo el intervalo.
5. Descartar y repetir una ronda solo ante una causa operativa documentada (reinicio, readiness fallida, datos semilla faltantes o carga del generador insuficiente); conservar el artefacto descartado y su motivo. No descartar una ronda por tener resultados desfavorables.
6. Consolidar la mediana entre rondas para cada variante y métrica, manteniendo también los resultados individuales y la dispersión. No mezclar muestras de calentamiento, hosts ni revisiones de código distintas.

La implementación disponible incluye `scripts/benchmark/overhead.js`, `scripts/benchmark/run_overhead.py` y el comando de entrada `scripts/benchmark/run-overhead.sh`. El runner construye las APIs, crea un proyecto Compose aislado por ejecución, alterna tres corridas por variante, siembra un producto y pedido antes de cada ventana, valida readiness, aplica la misma carga de lectura y mide CPU/memoria de los contenedores API. Al finalizar cada ronda elimina el proyecto y sus volúmenes; conserva las imágenes locales. Cada ejecución crea un directorio nuevo bajo `artifacts/overhead/<timestamp>-<commit>-<id>/` con metadatos, logs, JSON resumen de k6, muestras CSV de Docker stats, resultados por ronda y tabla comparativa. La implementación estática está lista, pero no se ha ejecutado el benchmark y no hay resultados medidos.

Para ejecutar la configuración predeterminada se necesita Docker Compose, k6 instalado en el host, `.env` inicializado con `python3 scripts/init-local-env.py` y los puertos 8001/8002 libres. `scripts/benchmark/run-overhead.sh` realiza seis corridas de 180 segundos más 30 segundos de calentamiento cada una (aprox. 21 minutos), además de construir imágenes. Los valores pueden ajustarse con `--rounds`, `--rate`, `--warmup-seconds` y `--duration-seconds`; se exigen al menos tres rondas por variante.

## Métricas y cálculo

Recolectar k6 `http_req_duration` con etiquetas separadas para cada API y ruta, códigos de respuesta/checks, tasa de solicitudes, `dropped_iterations` y duración total. Conservar los percentiles por ronda y usar p99 de respuesta HTTP como latencia principal. De `docker stats` conservar las muestras de CPU y memoria de cada API, marcando la semántica/plataforma del host; en Linux Docker resta cache de la lectura de memoria reportada por la CLI. No sumar porcentajes de CPU de contenedores si el resultado no especifica que es una métrica agregada.

Para cada API, calcular primero la mediana entre rondas de cada variante:

| Salida | Fórmula |
|---|---|
| Diferencia p99 (ms) | `p99_otel - p99_base` |
| Diferencia p99 (%) | `100 × (p99_otel - p99_base) / p99_base` |
| Diferencia CPU (puntos porcentuales) | `cpu_otel - cpu_base` |
| CPU relativa (%) | `100 × (cpu_otel - cpu_base) / cpu_base` |
| Memoria adicional (MiB) | `mem_otel - mem_base` |
| Memoria relativa (%) | `100 × (mem_otel - mem_base) / mem_base` |

En la tabla final presentar base, OTel, diferencia absoluta y relativa para ambas APIs. Expresar denominadores cero o métricas no disponibles como `N/D`, nunca como cero. Conservar unidad y agregación temporal para CPU/memoria. Diferencias negativas se reportan como medidas; no se interpretan automáticamente como mejoras causadas por OTel.

## Criterios de aceptación

- El switch funciona en ambas APIs y por defecto mantiene OTel activado; pruebas funcionales confirman que el modo `false` conserva rutas, códigos, esquemas de respuesta y persistencia.
- Las dos variantes procesan la misma muestra, con las mismas lecturas semilla, tasa y recursos configurados. Cada ronda reporta cero respuestas inesperadas y cero `dropped_iterations`; si no se cumple, el resultado se marca inválido o se repite según el protocolo.
- Hay al menos tres rondas válidas por variante y por API, con p99 de k6 y muestras de CPU/memoria de todo el intervalo medido.
- Los JSON/CSV originales, configuraciones efectivas, versiones, commit, metadatos del host, tabla calculada y notas de desviaciones se guardan juntos y permiten recalcular el resultado.
- Se informa solo lo medido: no se presenta umbral de overhead aceptable ni recomendación de producción sin un criterio acordado.

## Evidencias requeridas

- `00-entorno.json`: commit, timestamp, host/runtime, versiones, límites de contenedor, carga y duración.
- Un resultado k6 JSON por corrida, junto con stdout/resumen y CSV de muestras de `docker stats` para `catalog` y `orders`.
- `01-rondas.csv`: variante, orden, número de ronda, p99 por API/ruta, CPU y memoria resumidas, solicitudes/checks, iteraciones descartadas, estado válido/descartado y motivo.
- `02-comparacion.md`: tabla final con base, OTel, diferencia absoluta/relativa y metodología exacta. Si no hay ejecución, marcar `Pendiente de medir`; no añadir cifras de ejemplo como si fueran resultados.
- Captura opcional de readiness de las dos variantes, con URLs, IDs semilla y datos sensibles ocultos.

## Riesgos y límites

- Un benchmark local caracteriza únicamente el host, límites, versiones y carga documentados; no predice directamente el overhead de ECS/Fargate.
- La CPU disponible y actividad de otros procesos pueden introducir variación. Alternar el orden, repetir rondas y conservar series reduce sesgo, pero no lo elimina.
- La memoria reportada por `docker stats` depende de plataforma/cgroups y difiere de otras definiciones de working set; documentar el runtime y evitar comparar hosts distintos.
- El toggle cambia instrumentación/providers, no las dependencias instaladas ni el coste de importarlas. El experimento mide el efecto operativo de deshabilitar la instrumentación en este proceso, no el efecto de eliminar paquetes del artefacto.
- Los servicios tienen un flujo `POST /orders` que crea filas y llama a Catalog. No se incluye en la comparación principal porque altera el dataset. Una prueba de escritura/cadena distribuida requiere un protocolo separado que resetee la base de forma idéntica entre rondas.

## Referencias

- [Grafana k6: métricas de resultados y resumen final](https://grafana.com/docs/k6/latest/get-started/results-output/) — incluye latencia, errores, p99 y exportación de datos de corrida.
- [Grafana k6: thresholds](https://grafana.com/docs/k6/latest/using-k6/thresholds/) — define thresholds y checks; los checks por sí solos no cambian el código de salida del test.
- [Grafana k6: escenario constant-arrival-rate](https://grafana.com/docs/k6/latest/using-k6/scenarios/executors/constant-arrival-rate/) — ejecución con tasa de llegada objetivo.
- [Docker CLI: `docker container stats`](https://docs.docker.com/reference/cli/docker/container/stats/) — significado de CPU/memoria y nota de uso de cache en Linux.
