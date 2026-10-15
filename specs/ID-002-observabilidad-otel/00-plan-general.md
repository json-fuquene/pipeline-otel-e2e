# ID-002 — Plan general: observabilidad local y despliegue ECS

## Identificación

| Campo | Detalle |
|---|---|
| ID | ID-002 |
| Título | Observabilidad OpenTelemetry local y despliegue de laboratorio en ECS. |
| Sprint / iteración | No documentado. |
| Prioridad | Alta |
| Estado global | Fase 1 implementada sin validar; fase 2 implementada sin validar en AWS |
| Sistemas y repositorios afectados | APIs, Docker Compose, Collector, Jaeger, Prometheus, CloudWatch e IaC ECS. |
| Iniciativas relacionadas | ID-001 — instrumenta los servicios definidos por ese plan. |

## Resumen de estado

La fase 1 conserva su implementación local. La fase 2 agrega exportación de logs OTLP, backends de consulta y manifiestos ECS Fargate. La especificación y el código están preparados; Terraform no se aplicó ni se validó el pipeline en AWS.

## Enfoque técnico

Cada servicio configura su `TracerProvider` con `service.name` propio y exportador OTLP/gRPC. FastAPI, HTTPX en pedidos y SQLAlchemy se instrumentan con instrumentors OTel; las rutas de salud se excluyen. Los endpoints Prometheus usan `PrometheusMetricReader` en el puerto interno 9464. Los logs JSON incorporan el contexto span activo y conservan `request_id`.

En ECS la tarea Fargate agrupa APIs y backends con red `awsvpc`: PostgreSQL, migraciones, Collector, Jaeger y Prometheus. El Collector procesa señales con `memory_limiter`, `resource` y `batch`, y exporta trazas a Jaeger, métricas a Prometheus y logs a CloudWatch.

```mermaid
flowchart LR
  C[Cliente local] -->|HTTP| O[Pedidos]
  O -->|HTTP con traceparent| K[Catálogo]
  O --> DB[(PostgreSQL)]
  K --> DB
  O -->|OTLP gRPC| OT[OTel Collector]
  K -->|OTLP gRPC| OT
  OT -->|trazas| J[Jaeger]
  OT -->|logs| CW[CloudWatch Logs]
  OT -->|métricas| P[Prometheus]
  C -->|Prometheus :9465| OM[Métricas pedidos]
  C -->|Prometheus :9464| CM[Métricas catálogo]
```

## Contratos e interfaces afectados

| Elemento | Ubicación | Cambio | Compatibilidad hacia atrás |
|---|---|---|---|
| Endpoint Prometheus | `127.0.0.1:9464/metrics`, `127.0.0.1:9465/metrics` | Métricas HTTP de catálogo y pedidos. | Aditivo; API funcional no cambia. |
| Exportación OTLP | Red Compose, `otel-collector:4317` | Las APIs exportan trazas gRPC. | Interno al Compose. |
| ECS | `/home/ajfuq/projects/infraestructura/infra/otel-ecs-lab` | Crea red, ECR, secretos, permisos y tarea Fargate. | Requiere cuenta AWS. |
| Logs OTLP | Red interna ECS | Envía logs JSON de solicitud a CloudWatch Logs. | Aditivo; stdout se conserva. |
| Logs JSON | Middleware de cada servicio | Se agregan `trace_id` y `span_id`. | Aditivo; se conserva `request_id`. |
| Dependencias Python | `services/*/requirements.txt` | SDK, exportadores e instrumentors fijados. | Solo afecta imágenes de servicios. |

## Fases de ejecución

| Estado | # | Documento | Requisitos que cubre | Sistemas | Resultado esperado |
|---|---|---|---|---|---|
| Implementada sin validar | 1 | [Instrumentación OTel](01-instrumentacion-otel.md) | RF-001–RF-008, RNF-001–RNF-004 | APIs, Compose, Collector y README. | Trazas, métricas y logs correlacionados en entorno local. |
| Implementada sin validar en AWS | 2 | [Despliegue ECS](02-despliegue-ecs.md) | RF-009–RF-017, RNF-005–RNF-007 | Collector, APIs, imágenes, Jaeger, Prometheus, CloudWatch y Terraform. | Laboratorio Fargate listo para smoke test. |

## Cobertura de requisitos

| Estado de cobertura | Requisito | Fase que lo cubre |
|---|---|---|
| Implementado sin validar | RF-001 | Fase 1 |
| Implementado sin validar | RF-002 | Fase 1 |
| Implementado sin validar | RF-003 | Fase 1 |
| Implementado sin validar | RF-004 | Fase 1 |
| Implementado sin validar | RF-005 | Fase 1 |
| Implementado sin validar | RF-006 | Fase 1 |
| Implementado sin validar | RF-007 | Fase 1 |
| Implementado sin validar | RF-008 | Fase 1 |
| Implementado sin validar | RNF-001 | Fase 1 |
| Implementado sin validar | RNF-002 | Fase 1 |
| Implementado sin validar | RNF-003 | Fase 1 |
| Implementado sin validar | RNF-004 | Fase 1 |
| Implementado sin validar | RF-009–RF-017 | Fase 2 |
| Implementado sin validar | RNF-005–RNF-007 | Fase 2 |

## Dependencias y orden de ejecución

La fase 1 depende del código base de ID-001. La fase 2 depende de la fase 1, las imágenes publicadas en ECR, permisos de creación AWS y un CIDR autorizado. Las migraciones inician tras PostgreSQL saludable y las APIs esperan sus migraciones.

## Prerequisitos operativos

| Estado | Prerequisito | Tipo | Impacto si falta |
|---|---|---|---|
| Confirmado | Docker Compose v2 está instalado. | Infraestructura | Bloquea validación funcional. |
| Pendiente | Acceso al registro de imágenes para descargar Collector y dependencias Python. | Acceso | Bloquea build e integración. |
| Pendiente | Puertos locales 9464 y 9465 disponibles. | Configuración | Bloquea exposición de métricas. |
| No requerido | Cuenta cloud o backend externo de trazas. | Acceso | Ninguno; el Collector usa `debug`. |
| Pendiente | Cuenta AWS con permisos para ECS, ECR, VPC, IAM, Secrets Manager y CloudWatch. | Acceso | Bloquea smoke test cloud. |
| Pendiente | Escritura habilitada en `/home/ajfuq/projects/infraestructura`. | Filesystem | El Terraform está provisionalmente dentro del repositorio de aplicación. |

## Riesgos y limitaciones

| Riesgo o limitación | Detalle | Impacto | Mitigación o decisión | Bloqueante |
|---|---|---|---|---|
| Prelanzamiento de instrumentors | Paquetes Python de instrumentación usan versiones beta. | Medio | Versiones fijadas y build/validación de imagen pendientes. | Para validar |
| Sin backend persistente de trazas | `debug` escribe trazas recibidas en logs del Collector. | Bajo | Adecuado para demostración local; no ofrece búsqueda histórica. | No |
| Métricas de DB fuera del alcance | SQLAlchemy se instrumenta para spans; las métricas cubren HTTP. | Bajo | Extender requisitos en otra iniciativa si se necesitan métricas DB. | No |
| Datos efímeros ECS | PostgreSQL y Jaeger pierden datos al parar la tarea. | Medio | Usar datos sintéticos y destruir el entorno al terminar. | No |
| Directorio IaC externo no escribible | La ruta solicitada queda fuera de las rutas autorizadas de esta sesión. | Medio | Copiar los manifiestos cuando se habilite la escritura allí. | Para entregar ruta final |

## Estrategia de validación

| Estado | Nivel | Qué cubre | Ejecución |
|---|---|---|---|
| Aprobada | Automatizada / estática | Sintaxis Python y resolución de Compose sin imprimir valores interpolados. | `python3 -m compileall -q services`; `docker compose config --quiet` |
| Pendiente de confirmación | Funcional / operativa | Métricas, exportación y correlación pedidos→catálogo→DB. | `docker compose up -d --build --wait`; ver instrucciones de fase 1. |
| Pendiente | Reversión y compatibilidad | APIs conservan contratos y cambios se revierten quitando Collector, providers y puertos. | Revisar smoke de API y eliminar bloque OTel de Compose/dependencias. |

## Criterios de cierre del plan

- [ ] RF-001 a RF-008 y RNF-001 a RNF-004 validados.
- [ ] RF-009 a RF-017 y RNF-005 a RNF-007 validados en ECS.
- [ ] Compose levanta APIs, PostgreSQL y Collector.
- [ ] Métricas consultables y spans correlacionados visibles en logs del Collector.
- [ ] No se exportan valores sensibles ni se cambian contratos funcionales.
- [ ] Gate 3 y Gate 4 completados con evidencia en fase e informe final.

## Referencias

- [`00-especificacion.md`](00-especificacion.md) — requisitos, casos y decisiones.
- [`01-instrumentacion-otel.md`](01-instrumentacion-otel.md) — instrucciones de implementación y validación.
- [`02-despliegue-ecs.md`](02-despliegue-ecs.md) — despliegue ECS y ejecución del smoke test.
- [OpenTelemetry Python exporters](https://opentelemetry.io/docs/languages/python/exporters/) y [Collector troubleshooting](https://opentelemetry.io/docs/collector/troubleshooting/).
