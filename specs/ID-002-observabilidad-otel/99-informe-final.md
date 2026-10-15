# ID-002 — Informe de estado: observabilidad local y despliegue ECS

## Identificación

| Campo | Detalle |
|---|---|
| ID | ID-002 |
| Título | Observabilidad OpenTelemetry local y despliegue de laboratorio en ECS. |
| Sprint / iteración | No documentado. |
| Estado de cierre | Plan en curso; fase 3 especificada y pendiente de implementación. Este informe resume las fases 1 y 2 y no cierra ID-002. |
| Sistemas y repositorios afectados | Servicios, Docker Compose, Collector, Jaeger, Prometheus, CloudWatch, Terraform y documentación. |
| Iniciativas relacionadas | ID-001 — servicios funcionales instrumentados por esta iniciativa. |

## Resumen

La fase 1 contiene instrumentación local de trazas y métricas. La fase 2 contiene exportación OTLP de logs JSON, pipeline Collector para las tres señales, imágenes auxiliares e IaC ECS Fargate. La revisión 4 del task definition se desplegó con el tag `phase2-test-4`; ECS completó el rollout con una tarea activa, APIs y PostgreSQL saludables, backends en ejecución y migraciones exitosas. Falta la validación funcional integral de las señales. La fase 3 queda definida para agregar Grafana efímero, un dashboard de seis paneles y correlación de logs con trazas. El root Terraform está en `infra/otel-ecs-lab` y los módulos en `infra/tf_modules`.

## Problema atendido

Los servicios no ofrecían trazas distribuidas, métricas consultables ni IDs de traza en sus logs estructurados.

## Resultado por fase

| Estado | Fase | Resultado entregado | Desviación respecto al diseño |
|---|---|---|---|
| Implementada sin validar | Fase 1 — Instrumentación OpenTelemetry | SDK e instrumentors configurados, spans de negocio, métricas HTTP, campos de correlación, Collector y documentación local. | La validación operativa queda pendiente por falta de acceso a Docker y PyPI. |
| Implementada sin validar | Fase 2 — Despliegue ECS | OTLP HTTP/gRPC, processors, exporters Jaeger/Prometheus/CloudWatch, seis imágenes ECR y red/tarea Fargate. | Rollout de revisión 4 completado; visualización funcional, flujo de señales y destrucción quedan pendientes. |
| Pendiente | Fase 3 — Visualización y correlación en ECS | Plan para Grafana efímero, fuentes Prometheus/Jaeger/CloudWatch y seis paneles. | Especificación y validación preparadas; sin cambios de runtime ejecutados. |

## Cumplimiento de requisitos

| Estado | Requisito | Evidencia |
|---|---|---|
| Implementado; por validar | RF-001 a RF-008 | Instrumentación en código; falta observar spans y métricas en runtime. |
| Implementado; por validar | RNF-001 a RNF-004 | Cambios aditivos; falta smoke funcional y revisión de telemetría real. |
| Implementado; validación integral pendiente | RF-009 a RF-017, RNF-005 a RNF-007 | IaC aplicada y rollout ECS confirmado; faltan consulta funcional de backends y destrucción. |

## Cambios entregados

| Ubicación | Cambio aplicado | Efecto observable |
|---|---|---|
| `services/catalog/app` y `services/orders/app` | SDK, instrumentors, spans de negocio y logs con contexto de traza. | Las APIs quedan configuradas para producir telemetría correlacionada. |
| `compose.yaml`, `docker/otel-collector/config.yaml` | Collector local y puertos dedicados de métricas. | Collector recibe OTLP por red interna; métricas usan puertos de host 9464/9465. |
| `README.md`, `specs/ID-002-observabilidad-otel/` | Instrucciones, criterios y estado de validación. | El flujo y sus límites se documentan para ejecución y revisión. |
| `docker/{otel-collector,jaeger,prometheus,postgres}`, `infra/otel-ecs-lab`, `infra/tf_modules`, `scripts/push-ecs-images.py` | Imágenes, configuración y recursos mínimos ECS/ECR. | Las seis imágenes `phase2-test-4` están en ECR y ECS ejecuta la revisión 4; falta el smoke test integral de señales. |

## Evidencia de validación

| Tipo | Qué se verificó | Resultado |
|---|---|---|
| Automatizada / estática | `python3 -m compileall -q services`; `docker compose config --quiet`. | Aprobadas. |
| Automatizada / estática fase 2 | `terraform fmt -check -recursive infra/otel-ecs-lab` y `terraform fmt -check -recursive infra/tf_modules`. | Aprobada; `terraform init -backend=false` no pudo descargar providers por bloqueo DNS/red hacia `registry.terraform.io`, por lo que `terraform validate` queda pendiente. |
| ECS fase 2 | `aws ecs wait services-stable`; `describe-services` y `describe-tasks`, revisión `pipeline-otel-test:4`, tag `phase2-test-4`. | Rollout `COMPLETED`, desired/running 1/1, pending 0; APIs y PostgreSQL `HEALTHY`, Jaeger/Collector/Prometheus `RUNNING`, migraciones con código 0. |
| Logs Collector fase 2 | CloudWatch stream del contenedor `otel-collector`. | El Collector permanece `RUNNING`, pero registra un error de conversión de `pipeline_up` por labels duplicadas; investigar y mostrar en el panel de errores de fase 3. |
| Configs auxiliares | Parseo YAML de Collector ECS, Jaeger y Prometheus. | Pendiente; este runtime no tiene parser YAML instalado. |
| Build de imágenes | `docker compose build catalog orders otel-collector`. | No ejecutado: acceso al archivo Buildx bloqueado por sandbox; reintento sin config Docker falló por permisos del socket Docker. |
| Dependencias | `python3 -m pip install --target /tmp/otel-validation -r services/catalog/requirements.txt -r services/orders/requirements.txt`. | No ejecutado: DNS de `pypi.org` no resuelve; no se instalaron paquetes. |
| Funcional / operativa | Métricas y traza pedidos→catálogo→PostgreSQL. | Pendiente de confirmación. |
| Terraform / infraestructura | Sintaxis, providers y recursos AWS. | Pendiente; no se ejecutó `terraform init/validate/plan/apply`. |
| ECS | Tarea, migraciones, APIs y backends de observabilidad. | Rollout de revisión 4 completado; la visualización de señales todavía no fue validada. |
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
| 6 | Implementar Grafana efímero en ECS. | La nueva fase está especificada, sin dashboard ni contenedor desplegado. | Seguir `03-visualizacion-grafana.md`, validar seis paneles y correlación `trace_id`. | ID-002, fase 3 |

## Estado de cierre

El estado general permanece `En implementación`. El arranque de la revisión 4 se confirmó en ECS, pero las señales no se han verificado integralmente en sus backends, el panel de errores debe mostrar el problema de etiquetas observado y el laboratorio sigue sin destruirse. La fase 3 no está implementada.

## Próximos pasos recomendados

1. Construir e iniciar el entorno en una máquina con Docker y acceso a PyPI.
2. Confirmar métricas, correlación de spans y logs, y actualizar los estados de fase y plan con evidencia.

## Verificación de cierre documental

Gate funcional/cloud queda pendiente junto con la validación de YAML, Terraform y runtime; el estado de la fase y del plan refleja esa limitación.
