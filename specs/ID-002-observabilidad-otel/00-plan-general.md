# ID-002 — Plan general: observabilidad local, ECS y visualización

## Identificación

| Campo | Detalle |
|---|---|
| ID | ID-002 |
| Título | Observabilidad OpenTelemetry local, ECS y visualización. |
| Sprint / iteración | No documentado. |
| Prioridad | Alta |
| Estado global | En implementación; fases 1 y 2 implementadas sin validación funcional integral; fase 3 pendiente. |
| Sistemas y repositorios afectados | APIs, Docker Compose, Collector, Jaeger, Prometheus, Grafana, CloudWatch e IaC ECS. |
| Iniciativas relacionadas | ID-001 — instrumenta los servicios definidos por ese plan. |

## Resumen de estado

Las fases 1 y 2 tienen código y manifiestos implementados. La revisión 4 de la tarea ECS terminó su rollout con una tarea `RUNNING`, APIs saludables, PostgreSQL saludable, backends en ejecución y migraciones exitosas; falta validar el flujo de señales en las interfaces. La fase 3 agrega Grafana efímero, dashboard de seis paneles y búsqueda de trazas Jaeger a partir de logs CloudWatch.

## Enfoque técnico

Cada API configura su `TracerProvider` con `service.name` propio y exportador OTLP/gRPC. FastAPI, HTTPX en pedidos y SQLAlchemy se instrumentan con instrumentors OTel; las rutas de salud se excluyen. Cada API publica métricas HTTP Prometheus; los logs JSON conservan `request_id`, `trace_id` y `span_id`.

En ECS Fargate, la tarea `awsvpc` agrupa PostgreSQL, migraciones, APIs, OTel Collector, Jaeger, Prometheus y Grafana. El Collector recibe OTLP, envía trazas a Jaeger, métricas a Prometheus y logs a CloudWatch. Grafana se configura al iniciar desde archivos de provisioning, consulta Prometheus/Jaeger por `localhost` y accede a CloudWatch mediante el task role limitado a los grupos requeridos. El panel CPU consulta CloudWatch Metrics. No se agrega un backend de trazas externo al Jaeger ECS actual.

```mermaid
flowchart LR
  U[Cliente] -->|HTTP| O[Pedidos]
  O -->|HTTP con traceparent| K[Catálogo]
  O --> DB[(PostgreSQL)]
  K --> DB
  O -->|OTLP| OT[OTel Collector]
  K -->|OTLP| OT
  OT -->|trazas| J[Jaeger]
  OT -->|métricas| P[Prometheus]
  OT -->|logs| CW[CloudWatch Logs]
  P -->|HTTP local| G[Grafana]
  J -->|HTTP local| G
  CW -->|API AWS con task role| G
  G -->|dashboard, Explore| U
```

## Contratos e interfaces afectados

| Elemento | Ubicación | Cambio | Compatibilidad hacia atrás |
|---|---|---|---|
| Endpoint Prometheus | `127.0.0.1:9464/metrics`, `127.0.0.1:9465/metrics` | Métricas HTTP de catálogo y pedidos. | Aditivo; API funcional no cambia. |
| Exportación OTLP | Red ECS, puertos 4317/4318 | Las APIs exportan telemetría al Collector. | Interno al despliegue. |
| ECS Terraform | `infra/otel-ecs-lab` y `infra/tf_modules` | Agrega imagen/contenedor Grafana, puerto 3000 y permisos/secretos acotados; aumenta memoria de tarea a 3 GiB. | Requiere actualizar ECR y task definition. |
| Datasources Grafana | `docker/grafana/provisioning/datasources/` | Prometheus, Jaeger y CloudWatch. | Aditivo a backends existentes. |
| Dashboard | `docker/grafana/dashboards/` | Seis paneles con cuatro SLIs, CPU y errores del Collector. | Aditivo; configuración reproducible. |
| Correlación de logs | CloudWatch Logs y Grafana Explore | El `trace_id` de un evento guía la búsqueda TraceID en Jaeger. | No cambia formato de API. |

## Fases de ejecución

| Estado | # | Documento | Requisitos que cubre | Sistemas | Resultado esperado |
|---|---|---|---|---|---|
| Implementada sin validar | 1 | [Instrumentación OTel](01-instrumentacion-otel.md) | RF-001–RF-008, RNF-001–RNF-004 | APIs, Compose y Collector local. | Trazas, métricas y logs locales correlacionados. |
| Implementada sin validar | 2 | [Despliegue ECS](02-despliegue-ecs.md) | RF-009–RF-017, RNF-005–RNF-007 | Collector, APIs, Jaeger, Prometheus, CloudWatch y Terraform. | Laboratorio ECS operativo para consultas y smoke tests. |
| Pendiente | 3 | [Visualización y correlación en ECS](03-visualizacion-grafana.md) | RF-018–RF-022, RNF-008–RNF-009; revalidación de RF-002, RF-011–RF-013 y RF-019. | Grafana, CloudWatch, Jaeger, Prometheus, ECS y Terraform. | Dashboard con seis paneles y recorrido reproducible log→traza. |

## Cobertura de requisitos

| Estado de cobertura | Requisito | Fase que lo cubre |
|---|---|---|
| Implementado, funcional pendiente | RF-001 | Fase 1 |
| Implementado, funcional pendiente | RF-002 | Fase 1 y validación extremo a extremo en fase 3 |
| Implementado, funcional pendiente | RF-003 | Fase 1 y validación extremo a extremo en fase 3 |
| Implementado, funcional pendiente | RF-004 | Fase 1 |
| Implementado, funcional pendiente | RF-005 | Fase 1 y dashboard fase 3 |
| Implementado, funcional pendiente | RF-006 | Fase 1 y consulta de logs fase 3 |
| Implementado, funcional pendiente | RF-007 | Fase 1 |
| Implementado, funcional pendiente | RF-008 | Fase 1 |
| Implementado; pipeline cloud por confirmar | RF-009 | Fase 2 |
| Implementado; pipeline cloud por confirmar | RF-010 | Fase 2 |
| Implementado; visualización por confirmar | RF-011 | Fase 2 y 3 |
| Implementado; visualización por confirmar | RF-012 | Fase 2 y 3 |
| Implementado; consulta por confirmar | RF-013 | Fase 2 y 3 |
| Implementado; recursos desplegados | RF-014 | Fase 2 y 3 |
| Implementado; flujo de pedido por confirmar | RF-015 | Fase 2 y 3 |
| Implementado; seguridad de Grafana pendiente | RF-016 | Fase 2 y 3 |
| Despliegue activo; limpieza pendiente | RF-017 | Fase 2 y 3 |
| Pendiente | RF-018 | Fase 3 |
| Implementado; verificación end-to-end pendiente | RF-019 | Fase 3 |
| Pendiente | RF-020 | Fase 3 |
| Pendiente | RF-021 | Fase 3 |
| Pendiente | RF-022 | Fase 3 |
| Implementado; permisos Grafana pendientes | RNF-008 | Fase 3 |
| Pendiente | RNF-009 | Fase 3 |
| Implementado, funcional pendiente | RNF-001–RNF-004 | Fase 1 |
| Implementado, AWS por confirmar | RNF-005–RNF-007 | Fase 2 |

## Dependencias y orden de ejecución

La fase 1 depende del código base de ID-001. La fase 2 depende de la instrumentación, las imágenes publicadas y permisos de creación AWS. La fase 3 depende del ECS activo, de confirmar nombres/labels reales en Prometheus y de disponer de permisos para extender el repositorio IaC, ECR, IAM, Secrets Manager, CloudWatch y ECS. Las tareas de imagen/provisioning Grafana y consultas del dashboard pueden avanzar en paralelo; el apply y las pruebas funcionales requieren que ambas estén listas.

## Prerequisitos operativos

| Estado | Prerequisito | Tipo | Impacto si falta |
|---|---|---|---|
| Confirmado | Docker Compose v2 y proyecto local disponibles. | Infraestructura | Bloquea validación local. |
| Confirmado | Cuenta AWS, región `us-east-1`, ECS/ECR y entorno de fase 2. | Acceso/infraestructura | Bloquea el smoke test AWS. |
| Confirmado | La infraestructura Terraform reside en `infra/otel-ecs-lab` y los módulos en `infra/tf_modules`, dentro de este repositorio. | Repositorio | Ninguno. |
| Confirmado | CIDR de prueba `181.61.246.55/32`. | Configuración | Bloquea el acceso web a Grafana. |
| Pendiente de ejecutar | Aprovisionar el secreto de administrador Grafana y permiso de lectura CloudWatch acotado. | Seguridad | Bloquea consulta de Grafana a CloudWatch. |
| Pendiente de ejecutar | Publicar el tag inmutable de Grafana y actualizar la task definition. | ECR/ECS | Bloquea la fase 3. |
| No requerido | GCP, X-Ray, Tempo, servicio Grafana gestionado. | Alcance | Ninguno; están fuera de alcance. |

## Riesgos y limitaciones

| Riesgo o limitación | Detalle | Impacto | Mitigación o decisión | Bloqueante |
|---|---|---|---|---|
| Instrumentors preliminares | Dependencias Python fijadas incluyen componentes beta. | Medio | Mantener versiones fijadas y completar build/smoke. | Para validar |
| Trazas/datos efímeros | Jaeger y datos locales de Grafana viven en almacenamiento efímero. | Medio | Provisionar de nuevo desde archivos y exportar evidencia antes de destruir. | No |
| Compatibilidad de métricas | El nombre de métrica/atributos cambia según semconv/exporter. | Medio | Validar contra Prometheus real antes de fijar PromQL. | Para dashboard |
| Memoria Fargate | Grafana agrega consumo a una tarea actual de 2 GiB. | Medio | Dimensionar a 1 vCPU/3 GiB para la prueba y revisar estabilidad; el costo sube mientras esté activa. | Para deploy |
| Rol compartido de tarea | Las credenciales IAM del task role están disponibles a todos los contenedores. | Medio | Limitar lectura a métricas y grupos de log requeridos, sin permisos de escritura desde Grafana. | No |
| Error de métrica Collector | Los logs recientes notifican labels duplicadas en `pipeline_up`. | Medio | Mostrar el evento en el panel, investigar recurrencia y no filtrar el error para ocultarlo. | No |
| Acceso al puerto Grafana | El contenedor expone interfaz administrativa. | Alto | CIDR explícito, contraseña desde Secrets Manager, sin `0.0.0.0/0`. | Para deploy |

## Estrategia de validación

| Estado | Nivel | Qué cubre | Ejecución |
|---|---|---|---|
| Parcialmente aprobada | Automatizada / estática | Python/Compose fase 1, scripts y formato Terraform ya existente. | Repetir validaciones después de cambios de fase 3: compileall, Compose, JSON/YAML, `terraform fmt`, `init`, `validate`, `plan`. |
| Pendiente | Automatizada / imagen | Construcción y provisioning de Grafana. | Build de Docker, validación de provisioning y carga de las tres fuentes. |
| Parcialmente confirmada | Funcional / operativa | Rollout ECS rev4 activo; falta consultar señales integrales. | Esperar estabilidad, tráfico HTTP, revisar dashboard, Explore, Jaeger, Prometheus y CloudWatch. |
| Pendiente | Seguridad | CIDR, secreto y alcance IAM. | Revisar plan Terraform y probar acceso autorizado; no ampliar la entrada pública. |
| Pendiente | Reversión y limpieza | Recursos del laboratorio. | Guardar evidencia; `terraform destroy`; confirmar servicio sin tareas. |

## Criterios de cierre del plan

- [ ] RF-001 a RF-022 y RNF-001 a RNF-009 validados o con limitación explícita aceptada.
- [ ] Dashboard Grafana con exactamente seis paneles y series no vacías para los casos generados.
- [ ] Misma traza pedidos→catálogo→PostgreSQL visible en Jaeger y localizable desde `trace_id` en Grafana Explore.
- [ ] Log de aplicación consultable en Grafana vía CloudWatch Logs.
- [ ] Puerto 3000 solo accesible desde el CIDR autorizado y contraseña fuera de archivos versionados.
- [ ] Terraform destruido o decisión documentada de mantener el entorno activo, con su impacto de costo.
- [ ] Gates 3 y 4 completados con evidencia en fase e informe final.

## Referencias

- [`00-especificacion.md`](00-especificacion.md) — requisitos, casos y decisiones.
- [`01-instrumentacion-otel.md`](01-instrumentacion-otel.md) — instrumentación y validación local.
- [`02-despliegue-ecs.md`](02-despliegue-ecs.md) — laboratorio ECS.
- [`03-visualizacion-grafana.md`](03-visualizacion-grafana.md) — fase de dashboard, correlación y evidencias.
- [Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/) y [datasource Jaeger](https://grafana.com/docs/grafana/latest/datasources/jaeger/query-editor/).
- [Grafana CloudWatch query editor](https://grafana.com/docs/grafana/latest/datasources/aws-cloudwatch/query-editor/) y [AWS ECS service utilization](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service_utilization.html).
