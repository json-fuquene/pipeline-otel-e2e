# ID-002 — Informe de implementación: observabilidad local y despliegue ECS

## Identificación

| Campo | Detalle |
|---|---|
| ID | ID-002 |
| Título | Observabilidad OpenTelemetry local y despliegue de laboratorio en ECS. |
| Sprint / iteración | No documentado. |
| Estado de cierre | Fases implementadas; validación local/cloud pendiente. |
| Sistemas y repositorios afectados | Servicios, Docker Compose, Collector, Jaeger, Prometheus, CloudWatch, Terraform y documentación. |
| Iniciativas relacionadas | ID-001 — servicios funcionales instrumentados por esta iniciativa. |

## Resumen

La fase 1 conserva instrumentación local de trazas y métricas. La fase 2 añade exportación OTLP de logs JSON además de stdout, pipeline Collector para las tres señales, imágenes auxiliares y un root Terraform para ECS Fargate. No se aplicó Terraform ni se publicó en AWS; falta validar configuración, builds y smoke test extremo a extremo. El root Terraform está en `/home/ajfuq/projects/infraestructura/infra/otel-ecs-lab`.

## Problema atendido

Los servicios no ofrecían trazas distribuidas, métricas consultables ni IDs de traza en sus logs estructurados.

## Resultado por fase

| Estado | Fase | Resultado entregado | Desviación respecto al diseño |
|---|---|---|---|
| Implementada sin validar | Fase 1 — Instrumentación OpenTelemetry | SDK e instrumentors configurados, spans de negocio, métricas HTTP, campos de correlación, Collector y documentación local. | La validación operativa queda pendiente por falta de acceso a Docker y PyPI. |
| Implementada sin validar en AWS | Fase 2 — Despliegue ECS | OTLP HTTP/gRPC, processors, exporters Jaeger/Prometheus/CloudWatch, imágenes auxiliares y red/tarea Fargate con secretos y roles mínimos. | No se inicializó Terraform ni se ejecutó en una cuenta AWS; los manifiestos quedaron staged en el repositorio por el permiso de filesystem. |

## Cumplimiento de requisitos

| Estado | Requisito | Evidencia |
|---|---|---|
| Implementado; por validar | RF-001 a RF-008 | Instrumentación en código; falta observar spans y métricas en runtime. |
| Implementado; por validar | RNF-001 a RNF-004 | Cambios aditivos; falta smoke funcional y revisión de telemetría real. |
| Implementado; por validar | RF-009 a RF-017, RNF-005 a RNF-007 | Configuración e IaC presentes; faltan `terraform validate`, ejecución cloud, visualización en backends y destrucción. |

## Cambios entregados

| Ubicación | Cambio aplicado | Efecto observable |
|---|---|---|
| `services/catalog/app` y `services/orders/app` | SDK, instrumentors, spans de negocio y logs con contexto de traza. | Las APIs quedan configuradas para producir telemetría correlacionada. |
| `compose.yaml`, `docker/otel-collector/config.yaml` | Collector local y puertos dedicados de métricas. | Collector recibe OTLP por red interna; métricas usan puertos de host 9464/9465. |
| `README.md`, `specs/ID-002-observabilidad-otel/` | Instrucciones, criterios y estado de validación. | El flujo y sus límites se documentan para ejecución y revisión. |
| `docker/{otel-collector,jaeger,prometheus,postgres}`, `/home/ajfuq/projects/infraestructura/infra/otel-ecs-lab`, `scripts/push-ecs-images.py` | Imágenes, configuración y recursos mínimos ECS/ECR. | Publicación y smoke test en Fargate preparados, pendientes de ejecución. |

## Evidencia de validación

| Tipo | Qué se verificó | Resultado |
|---|---|---|
| Automatizada / estática | `python3 -m compileall -q services`; `docker compose config --quiet`. | Aprobadas. |
| Automatizada / estática fase 2 | `terraform fmt -check -recursive /home/ajfuq/projects/infraestructura/infra/otel-ecs-lab`. | Aprobada; `terraform init -backend=false` no pudo descargar providers por bloqueo DNS/red hacia `registry.terraform.io`, por lo que `terraform validate` queda pendiente. |
| Configs auxiliares | Parseo YAML de Collector ECS, Jaeger y Prometheus. | Pendiente; este runtime no tiene parser YAML instalado. |
| Build de imágenes | `docker compose build catalog orders otel-collector`. | No ejecutado: acceso al archivo Buildx bloqueado por sandbox; reintento sin config Docker falló por permisos del socket Docker. |
| Dependencias | `python3 -m pip install --target /tmp/otel-validation -r services/catalog/requirements.txt -r services/orders/requirements.txt`. | No ejecutado: DNS de `pypi.org` no resuelve; no se instalaron paquetes. |
| Funcional / operativa | Métricas y traza pedidos→catálogo→PostgreSQL. | Pendiente de confirmación. |
| Terraform / infraestructura | Sintaxis, providers y recursos AWS. | Pendiente; no se ejecutó `terraform init/validate/plan/apply`. |
| ECS | Tarea, migraciones, APIs y backends de observabilidad. | Pendiente de cuenta y permisos AWS; no se aplicaron recursos. |
| Reversión y compatibilidad | Respuestas funcionales y apagado limpio. | Pendiente de confirmación. |

## Decisiones técnicas relevantes

| Id | Decisión | Alternativa descartada | Motivo | Consecuencia asumida |
|---|---|---|---|---|
| D-001 | Nueva iniciativa ID-002. | Renumerar o reemplazar fase de ID-001. | Mantener historial y trazabilidad del plan de servicios. | Dos carpetas SDD relacionadas. |
| D-002 | Métricas en endpoints propios de cada API. | Agregar Prometheus local. | El requisito solicita endpoint y no servidor de consulta. | El scrape/consulta queda a cargo de Prometheus externo si se requiere. |
| D-003 | Logs JSON correlacionados en stdout. | Exportar OTel Logs por OTLP. | Se conserva el flujo local existente. | Los logs no aparecen como señal separada en el Collector. |
| D-004 | Métricas HTTP; spans SQLAlchemy. | Instrumentar métricas de DB/negocio. | Alcance inicial verificable sin inventar indicadores de dominio. | Métricas de DB quedan para otra iniciativa. |
| D-005 | Spans explícitos al crear producto y pedido. | Depender solo de spans automáticos. | Delimitar las operaciones críticas de negocio. | Los spans agregan eventos internos, sin cambiar respuestas. |
| D-006 | Versiones fijadas del SDK, instrumentors y Collector. | Usar tags flotantes. | Reproducibilidad. | Los instrumentors Python fijados están en versión beta. |
| D-007 | Convenciones HTTP estables y atributos URL sanitizados. | Convenciones legacy con query completa. | Evitar filtrar parámetros de solicitud en spans y métricas. | Los nombres de métricas siguen las convenciones HTTP estables. |

## Limitaciones conocidas

- El Collector `debug` no conserva trazas y no ofrece búsqueda o visualización histórica.
- Los instrumentors SQLAlchemy generan spans; las métricas iniciales se limitan a HTTP.
- No se ha comprobado la compatibilidad efectiva de las dependencias OTel Logs en una imagen Python 3.12.
- Los recursos Fargate, la validez integral de los configs y permisos efectivos de IAM siguen sin validación runtime.

## Pendientes y bloqueantes

| Id | Pendiente o bloqueante | Impacto | Siguiente acción | Dónde continúa |
|---|---|---|---|---|
| 1 | Obtener acceso al daemon Docker y al registry de imágenes. | Sin build o arranque local no se valida Compose ni el Collector. | Ejecutar `docker compose up -d --build --wait` y revisar salud. | ID-002, fase 1 |
| 2 | Resolver DNS/acceso a PyPI para instalar las dependencias. | Las importaciones OTel no se han ejecutado en este entorno. | Construir imágenes con acceso al índice de paquetes y corregir incompatibilidades encontradas. | ID-002, fase 1 |
| 3 | Ejecutar el flujo extremo a extremo. | RF-001–RF-008 siguen sin evidencia funcional. | Crear producto y pedido; revisar `/metrics`, logs y salida del Collector. | ID-002, fase 1 |
| 4 | Ubicar los manifiestos en el repositorio `/home/ajfuq/projects/infraestructura`. | Resuelto: manifiestos en `infra/otel-ecs-lab`. | Ninguna. | ID-002, fase 2 |
| 5 | Ejecutar validación e infraestructura de prueba en AWS. | RF-009–RF-017 todavía no cuentan con evidencia cloud. | Formatear/validar Terraform, publicar imágenes, aplicar, smoke test y destruir recursos. | ID-002, fase 2 |

## Estado de cierre

La implementación está presente; el estado general permanece `Implementada sin validar`. No se afirma que las nuevas dependencias importen correctamente, que los contenedores auxiliares inicien, que Terraform despliegue o que se hayan observado señales reales en Jaeger, Prometheus o CloudWatch. El gate funcional y cloud queda pendiente.

## Próximos pasos recomendados

1. Construir e iniciar el entorno en una máquina con Docker y acceso a PyPI.
2. Confirmar métricas, correlación de spans y logs, y actualizar los estados de fase y plan con evidencia.

## Verificación de cierre documental

Gate funcional/cloud queda pendiente junto con la validación de YAML, Terraform y runtime; el estado de la fase y del plan refleja esa limitación.
