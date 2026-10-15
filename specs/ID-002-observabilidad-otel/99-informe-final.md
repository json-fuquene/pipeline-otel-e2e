# ID-002 — Informe de estado: observabilidad local y despliegue ECS

## Identificación

| Campo | Detalle |
|---|---|
| ID | ID-002 |
| Título | Observabilidad OpenTelemetry local y despliegue de laboratorio en ECS. |
| Sprint / iteración | No documentado. |
| Estado de cierre | Revisión 8 de ECS en rollout; la UI del panel CPU, el pivote log→traza y la limpieza del laboratorio siguen pendientes. Este informe no cierra ID-002. |
| Sistemas y repositorios afectados | Servicios, Docker Compose, Collector, Jaeger, Prometheus, CloudWatch, Terraform y documentación. |
| Iniciativas relacionadas | ID-001 — servicios funcionales instrumentados por esta iniciativa. |

## Resumen

Las pruebas previas confirmaron que Explore consulta datos de CloudWatch, pero el panel CPU no recogía una solicitud al usar Query Inspector. Se actualizó el target para especificar la fuente CloudWatch y sus campos de consulta; se publicó `phase3-test-4` y Terraform generó la revisión 8 de ECS. El rollout sigue en curso: no se afirma estabilidad final ni renderizado exitoso del panel. Queda verificarlo en UI y completar el pivote log→traza y la limpieza del laboratorio.

## Problema atendido

Los servicios no ofrecían trazas distribuidas, métricas consultables ni IDs de traza en sus logs estructurados.

## Resultado por fase

| Estado | Fase | Resultado entregado | Desviación respecto al diseño |
|---|---|---|---|
| Implementada sin validar | Fase 1 — Instrumentación OpenTelemetry | SDK e instrumentors configurados, spans de negocio, métricas HTTP, campos de correlación, Collector y documentación local. | La validación operativa queda pendiente por falta de acceso a Docker y PyPI. |
| Implementada; runtime operativo | Fase 2 — Despliegue ECS | OTLP HTTP/gRPC, processors, exporters Jaeger/Prometheus/CloudWatch y red/tarea Fargate. | Despliegue anterior estable; limpieza queda pendiente. |
| Rollout en curso; UI pendiente | Fase 3 — Visualización y correlación en ECS | Grafana efímero, fuentes Prometheus/Jaeger/CloudWatch y dashboard de seis paneles. | Tag `phase3-test-4` y revisión 8 aplicados; confirmar estabilidad, consulta/render de CPU y log→traza. |
| Implementada; sin mediciones | Fase 4 — Análisis de overhead | Toggle `OTEL_ENABLED`, escenario k6 y runner local para comparar p99, CPU y memoria. | No hay benchmark ejecutado ni resultados medidos; correr el protocolo y guardar las evidencias según `04-analisis-overhead.md`. |

## Cumplimiento de requisitos

| Estado | Requisito | Evidencia |
|---|---|---|
| Implementado; por validar | RF-001 a RF-008 | Instrumentación en código; falta observar spans y métricas en runtime. |
| Implementado; por validar | RNF-001 a RNF-004 | Cambios aditivos; falta smoke funcional y revisión de telemetría real. |
| Implementado; validación integral pendiente | RF-009 a RF-017, RNF-005 a RNF-007 | IaC aplicada y rollout ECS confirmado; faltan consulta funcional de backends y destrucción. |
| Parcial, revalidación pendiente | RF-018, RF-020, RF-022, RNF-008 y RNF-009 | La revisión 8 sigue en rollout; validar dashboard y consulta CPU desde la UI. |
| Pendiente de validación funcional | RF-019 y RF-021 | Correlación distribuida log→traza; requiere solicitud real y consulta en Grafana/Jaeger. |
| Implementado; medición pendiente | RF-023 y RNF-010 | El toggle, el runner y el escenario están listos; no se han generado resultados de benchmark. |

## Cambios entregados

| Ubicación | Cambio aplicado | Efecto observable |
|---|---|---|
| `services/catalog/app` y `services/orders/app` | SDK, instrumentors, spans de negocio y logs con contexto de traza. | Las APIs quedan configuradas para producir telemetría correlacionada. |
| `compose.yaml`, `docker/otel-collector/config.yaml` | Collector local y puertos dedicados de métricas. | Collector recibe OTLP por red interna; métricas usan puertos de host 9464/9465. |
| `README.md`, `specs/ID-002-observabilidad-otel/` | Instrucciones, criterios y estado de validación. | El flujo y sus límites se documentan para ejecución y revisión. |
| `docker/{otel-collector,jaeger,prometheus,postgres,grafana}`, `infra/otel-ecs-lab`, `infra/tf_modules`, `scripts/push-ecs-images.py` | Imágenes, configuración y recursos mínimos ECS/ECR; incluye dashboard Grafana y acceso a CloudWatch/Jaeger/Prometheus. | Tag `phase3-test-4` publicado; revisión 8 en rollout. El target CPU explicita datasource CloudWatch y requiere verificación en UI. |
| `specs/ID-002-observabilidad-otel/04-analisis-overhead.md` | Diseño del experimento de overhead con k6, toggle OTel, carga de solo lectura, cálculos y evidencias. | Especificación únicamente; sin datos medidos ni afirmaciones de rendimiento. |

## Evidencia de validación

| Tipo | Qué se verificó | Resultado |
|---|---|---|
| Automatizada / estática | `python3 -m compileall -q services`; `docker compose config --quiet`. | Aprobadas. |
| Automatizada / estática fase 2 | `terraform fmt -check -recursive infra/otel-ecs-lab` y `terraform fmt -check -recursive infra/tf_modules`. | Aprobada; `terraform init -backend=false` no pudo descargar providers por bloqueo DNS/red hacia `registry.terraform.io`, por lo que `terraform validate` queda pendiente. |
| ECS fase 2 | `aws ecs wait services-stable`; `describe-services` y `describe-tasks`, revisión `pipeline-otel-test:4`, tag `phase2-test-4`. | Rollout `COMPLETED`, desired/running 1/1, pending 0; APIs y PostgreSQL `HEALTHY`, Jaeger/Collector/Prometheus `RUNNING`, migraciones con código 0. |
| Corrección de métricas | Logs CloudWatch de Collector y Prometheus API. | Se desactivó `resource_to_telemetry_conversion`, que provocaba etiquetas duplicadas; la revisión nueva recibe y exporta métricas HTTP sin repetir el error. |
| Configs auxiliares | Parseo YAML de Collector ECS, Jaeger y Prometheus. | Pendiente; este runtime no tiene parser YAML instalado. |
| Build de imágenes anterior | `docker compose build catalog orders otel-collector`. | No ejecutado en la validación anterior: acceso al archivo Buildx/socket bloqueado. |
| Build y provisioning Grafana fase 3 | `docker build -f docker/grafana/Dockerfile`; ejecución temporal local con API health, dashboard UID y fuentes. | Aprobado; contenedor temporal detenido al terminar. |
| Dependencias | `python3 -m pip install --target /tmp/otel-validation -r services/catalog/requirements.txt -r services/orders/requirements.txt`. | No ejecutado: DNS de `pypi.org` no resuelve; no se instalaron paquetes. |
| Funcional / operativa | `POST /products`, `POST /orders` y muestras Prometheus de ambas APIs. | Ambos POST respondieron `201`; consultas Grafana devolvieron éxito HTTP 100%, p95 de catálogo 9.75 ms y pedidos 24.25 ms. |
| Terraform / infraestructura fase 3, despliegue previo | `terraform fmt -check -recursive`, `terraform plan` y `terraform apply`, tag `phase3-test-3`. | La revisión 7 estuvo estable antes del cambio actual; queda supersedida por la revisión 8, cuyo rollout sigue pendiente de confirmar. |
| Imagen / provisioning Grafana | Build `pipeline-otel-grafana:phase3-validation`, API health, `/api/dashboards/uid/otel-lab` y `/api/datasources`. | Build exitoso; API saludable, dashboard con seis paneles y tres fuentes provisionadas. |
| API Grafana, despliegue previo | `/api/dashboards/uid/otel-lab` y `/api/ds/query` en la revisión 7. | Cinco consultas respondieron HTTP 200 y devolvieron muestras. Este resultado no valida la ejecución del panel CPU desde la UI; Query Inspector no recoge una solicitud en la vista reportada. |
| ECS | Tarea, migraciones, APIs y backends de observabilidad. | Revisión 7 estable en la prueba anterior; revisión 8 con `phase3-test-4` actualmente en rollout. |
| Benchmark de overhead fase 4 | k6 con y sin OTel, p99, CPU y memoria por API. | No ejecutado; implementación y corridas quedan pendientes. |
| Reversión y compatibilidad | Respuestas funcionales y apagado limpio. | Pendiente de confirmación. |

## Decisiones técnicas relevantes

| Id | Decisión | Alternativa descartada | Motivo | Consecuencia asumida |
|---|---|---|---|---|
| D-001 | Nueva iniciativa ID-002. | Renumerar o reemplazar fase de ID-001. | Mantener historial y trazabilidad del plan de servicios. | Dos carpetas SDD relacionadas. |
| D-002 | Métricas en endpoints propios de cada API. | Agregar Prometheus local. | El requisito solicita endpoint y no servidor de consulta. | El scrape/consulta queda a cargo de Prometheus externo si se requiere. |
| D-003 | Conservar logs JSON en stdout y exportar OTel Logs por OTLP en ECS. | Solo stdout o reemplazar los logs estructurados por OTLP. | Se conserva el flujo local y CloudWatch recibe la señal correlacionada. | El flujo OTLP funcional aún debe consultarse y verificarse. |
| D-004 | Métricas HTTP; spans SQLAlchemy. | Instrumentar métricas de DB/negocio. | Alcance inicial verificable sin inventar indicadores de dominio. | Métricas de DB quedan para otra iniciativa. |
| D-005 | Spans explícitos al crear producto y pedido. | Depender solo de spans automáticos. | Delimitar las operaciones críticas de negocio. | Los spans agregan eventos internos, sin cambiar respuestas. |
| D-006 | Versiones fijadas del SDK, instrumentors y Collector. | Usar tags flotantes. | Reproducibilidad. | Los instrumentors Python fijados están en versión beta. |
| D-007 | Convenciones HTTP estables y atributos URL sanitizados. | Convenciones legacy con query completa. | Evitar filtrar parámetros de solicitud en spans y métricas. | Los nombres de métricas siguen las convenciones HTTP estables. |

## Limitaciones conocidas

- El Collector `debug` no conserva trazas y no ofrece búsqueda o visualización histórica.
- Los instrumentors SQLAlchemy generan spans; las métricas iniciales se limitan a HTTP.
- No se ha comprobado la compatibilidad efectiva de las dependencias OTel Logs en una imagen Python 3.12.
- La tarea Fargate se desplegó y arrancó; la consulta funcional de señales, la validez integral de los configs y el alcance efectivo de IAM siguen pendientes.

## Pendientes y bloqueantes

| Id | Pendiente o bloqueante | Impacto | Siguiente acción | Dónde continúa |
|---|---|---|---|---|
| 1 | Obtener acceso al daemon Docker y al registry de imágenes. | Sin build o arranque local no se valida Compose ni el Collector. | Ejecutar `docker compose up -d --build --wait` y revisar salud. | ID-002, fase 1 |
| 2 | Resolver DNS/acceso a PyPI para instalar las dependencias. | Las importaciones OTel no se han ejecutado en este entorno. | Construir imágenes con acceso al índice de paquetes y corregir incompatibilidades encontradas. | ID-002, fase 1 |
| 3 | Ejecutar el flujo extremo a extremo. | RF-001–RF-008 siguen sin evidencia funcional. | Crear producto y pedido; revisar `/metrics`, logs y salida del Collector. | ID-002, fase 1 |
| 4 | Ubicar los manifiestos Terraform junto al repositorio de aplicación. | Resuelto: root en `infra/otel-ecs-lab`, módulos en `infra/tf_modules`. | Ninguna. | ID-002, fase 2 |
| 5 | Consultar señales end-to-end y destruir el laboratorio después de capturar evidencias. | Jaeger, Prometheus y CloudWatch todavía no tienen evidencia funcional registrada; el despliegue sigue activo. | Aplicar los pasos documentados y registrar logs, trazas, métricas, dashboard y limpieza. | ID-002, fases 2 y 3 |
| 6 | Publicar y desplegar Grafana efímero en ECS; validar dashboard y correlación. | Tag `phase3-test-4` publicado y revisión 8 en rollout; falta confirmar estabilidad, validar CPU en la UI, guardar evidencias y comprobar correlación `trace_id` en Jaeger. | Seguir `03-visualizacion-grafana.md` y completar limpieza. | ID-002, fase 3 |
| 7 | Ejecutar el análisis de overhead definido para fase 4. | El toggle, runner k6 y recolección local de recursos están implementados; faltan mediciones y evidencia. | Instalar k6 en el host de ejecución, correr al menos tres rondas válidas por variante y completar la tabla solo con datos observados. | ID-002, fase 4 |

## Estado de cierre

El estado general permanece `En implementación`. El arranque de la revisión 4 se confirmó en ECS, pero las señales no se han verificado integralmente en sus backends y el laboratorio sigue sin destruirse. La fase 3 está implementada en código; la publicación de imágenes, aplicación Terraform y validación de dashboard/correlación siguen pendientes.

## Próximos pasos recomendados

1. Construir e iniciar el entorno en una máquina con Docker y acceso a PyPI.
2. Confirmar métricas, correlación de spans y logs, y actualizar los estados de fase y plan con evidencia.

## Verificación de cierre documental

Gate funcional/cloud queda pendiente junto con la validación de YAML, Terraform y runtime; el estado de la fase y del plan refleja esa limitación.
