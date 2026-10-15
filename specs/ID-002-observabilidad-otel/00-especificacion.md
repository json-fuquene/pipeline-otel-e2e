# ID-002 — Especificación: instrumentación OpenTelemetry local

## Identificación

| Campo | Detalle |
|---|---|
| ID | ID-002 |
| Título | Instrumentación OpenTelemetry de catálogo y pedidos. |
| Origen | Requerimiento registrado en [`fases.md`](../../fases.md). |
| Sprint / iteración | No documentado. |
| Estado de la especificación | Aprobada; decisiones de alcance acordadas el 2026-10-14. |
| Iniciativas relacionadas | ID-001 — instrumenta sus dos servicios sin cambiar sus contratos funcionales. |

## Problema

Los servicios permiten crear productos y pedidos, pero no ofrecen trazas distribuidas, métricas consultables ni correlación de los logs JSON con una traza. Esto dificulta seguir el recorrido de un pedido por HTTP y PostgreSQL durante el desarrollo local.

## Resultado esperado

Cada servicio produce trazas OTel, métricas HTTP en formato Prometheus y logs JSON relacionados con el contexto de traza. En Compose, los servicios envían trazas a un Collector local y exponen sus propias métricas.

## Actores y sistemas involucrados

| Actor o sistema | Rol en el flujo | Qué cambia para él |
|---|---|---|
| Catálogo | Recibe HTTP y consulta PostgreSQL. | Emite spans, métricas HTTP y logs correlacionados. |
| Pedidos | Recibe HTTP, consulta catálogo y PostgreSQL. | Propaga contexto de traza y emite las mismas señales. |
| OTel Collector | Recibe trazas OTLP de ambas APIs. | Muestra los datos recibidos con un exportador local de depuración. |
| Cliente local | Consume APIs y puede consultar métricas. | Accede a `/metrics` en un puerto local dedicado. |

## Requisitos funcionales

| Id | Requisito | Criterio de aceptación | Prioridad |
|---|---|---|---|
| RF-001 | Cada servicio crea trazas para solicitudes HTTP entrantes. | Una solicitud a una ruta funcional produce un span de servidor identificado con el nombre del servicio correspondiente. | Obligatorio |
| RF-002 | Pedidos propaga el contexto W3C en sus llamadas HTTP a catálogo. | La llamada HTTP cliente aparece como span hijo de la solicitud de pedidos y la solicitud recibida por catálogo conserva el mismo `trace_id`. | Obligatorio |
| RF-003 | Ambos servicios crean spans para operaciones SQLAlchemy contra PostgreSQL. | Una operación de base de datos bajo una solicitud produce un span asociado a la traza activa. | Obligatorio |
| RF-004 | Las operaciones de negocio críticas tienen spans propios. | Crear producto genera `catalog.product.create`; crear pedido genera `orders.order.create`. | Obligatorio |
| RF-005 | Cada servicio expone métricas HTTP OTel en formato Prometheus. | `/metrics` responde con contenido Prometheus en el puerto configurado y contiene métricas de solicitudes HTTP. | Obligatorio |
| RF-006 | Los logs por solicitud correlacionan `request_id` y contexto OTel. | Cada registro mantiene `request_id` y contiene `trace_id`/`span_id` válidos cuando existe span activo; campos ausentes de contexto se representan como `null`. | Obligatorio |
| RF-007 | Compose levanta un Collector OTLP para las trazas. | Tras crear un producto o pedido, el Collector registra spans recibidos de ambos servicios. | Obligatorio |
| RF-008 | Los endpoints de salud no generan spans de servidor. | Consultas a `/health/live` y `/health/ready` no producen spans HTTP de entrada. | Deseable |

## Requisitos no funcionales

| Id | Categoría | Requisito | Criterio de aceptación |
|---|---|---|---|
| RNF-001 | Compatibilidad | La instrumentación no cambia contratos, códigos ni resultados funcionales de ID-001. | Las pruebas existentes y el smoke funcional de API mantienen sus resultados. |
| RNF-002 | Seguridad | No se capturan cuerpos, valores de query ni cabeceras sensibles en spans o logs. | Revisión de atributos y logs tras enviar solicitudes representativas. |
| RNF-003 | Operación | Las métricas se exponen desde las APIs y no requieren un servidor Prometheus en Compose. | Compose contiene Collector y endpoints de métricas, sin servicio Prometheus. |
| RNF-004 | Configuración | Nombres de servicio y destinos OTel son distintos o configurables por servicio y explícitos en el entorno local. | Compose configura `catalog`, `orders` y destino OTLP al Collector. |

## Casos y comportamiento esperado

| Id | Caso | Condición de entrada | Comportamiento esperado |
|---|---|---|---|
| C-001 | Crear producto | `POST /products` válido. | Traza de servidor, span de negocio y span SQL; log con IDs correlacionados; respuesta funcional sin cambios. |
| C-002 | Crear pedido | `POST /orders` válido con catálogo disponible. | Una traza enlaza servidor de pedidos, span de negocio, llamada HTTP, servidor de catálogo y spans SQL de ambos servicios. |
| C-003 | Consultar métricas | GET al endpoint de métricas de cada servicio. | Formato Prometheus con métricas HTTP; el endpoint no se atiende en el puerto funcional de la API. |
| C-004 | Contexto entrante ausente | Solicitud HTTP sin `traceparent`. | Se inicia una traza nueva; la llamada de pedidos propaga el nuevo contexto a catálogo. |
| C-005 | Collector no disponible | APIs inician mientras el Collector no acepta conexiones. | APIs siguen atendiendo solicitudes; el exportador informa fallos sin incluirlos en respuestas API. |
| C-006 | Salud | GET a `/health/live` o `/health/ready`. | Respuesta de salud conserva el contrato actual y no se crea span HTTP de servidor. |
| C-007 | Seguridad de telemetría | Solicitud con cabeceras o datos de negocio. | No se exportan cuerpos, valores de query ni secretos; los nombres de ruta usan plantillas. |

## Supuestos

| Verificado | Id | Supuesto | Impacto si resulta falso |
|---|---|---|---|
| Sí, por respuesta de alcance | S-001 | La instrumentación se gestiona en un ID SDD nuevo y no renumera las fases de ID-001. | Habría que reorganizar la trazabilidad documental. |
| Sí, por respuesta de alcance | S-002 | Cada API expone métricas; no se agrega servidor Prometheus local. | Cambiarían Compose y los criterios de operación. |
| Sí, por respuesta de alcance | S-003 | Los logs JSON existentes se enriquecen con IDs; no se exportan logs OTLP. | Cambiaría el pipeline de logs y el Collector. |
| Sí, derivado del requerimiento | S-004 | Las métricas iniciales cubren HTTP; SQLAlchemy aporta spans de DB. No se agregan métricas de negocio ni de PostgreSQL. | Se amplía el alcance de métricas. |

## Fuera de alcance

- Servidor Prometheus, Grafana, Jaeger, Tempo u otra interfaz de consulta.
- Exportación de logs al Collector mediante OTel Logs SDK/OTLP.
- Métricas específicas de negocio o del servidor PostgreSQL.
- Muestreo configurable, autenticación OTLP, despliegue fuera del Compose local y almacenamiento persistente de trazas.
- Cambios en contratos HTTP, persistencia o reglas de negocio de ID-001.

## Aclaraciones pendientes

No quedan aclaraciones abiertas que afecten el diseño.

| Estado | Id | Pregunta | Bloquea a |
|---|---|---|---|
| Resuelta → D-001 | A-001 | ¿La fase OTel continúa ID-001 o se crea una iniciativa independiente? | Ninguna fase. |
| Resuelta → D-002 | A-002 | ¿Se exponen endpoints de métricas o se agrega Prometheus a Compose? | Ninguna fase. |
| Resuelta → D-003 | A-003 | ¿Los logs JSON se correlacionan localmente o se exportan como OTel Logs? | Ninguna fase. |

## Bitácora de decisiones

| Id | Decisión | Alternativas consideradas | Motivo | Origen |
|---|---|---|---|---|
| D-001 | Crear ID-002 separado y conservar las fases numeradas de ID-001. | Reordenar o sustituir fase de ID-001. | ID-001 ya está implementado y su fase 1 es persistencia. | Respuesta de alcance. |
| D-002 | Cada servicio expone Prometheus en un puerto local dedicado; no se agrega Prometheus. | Agregar servidor Prometheus en Compose. | `fases.md` requiere endpoint y no pide servicio de consulta. | Respuesta de alcance. |
| D-003 | Mantener logs JSON en stdout e inyectar IDs del contexto OTel. | Exportar OTel Logs por OTLP. | Coincide con el requisito de logs estructurados y mantiene el flujo local existente. | Respuesta de alcance. |
| D-004 | HTTP FastAPI/HTTPX emite métricas; SQLAlchemy se instrumenta para spans. | Métricas manuales de DB o negocio. | Cubrir el requerimiento mínimo de métricas sin inventar indicadores de dominio. | Diseño derivado del requisito. |
| D-005 | Usar spans `catalog.product.create` y `orders.order.create`. | Solo spans automáticos de framework y cliente. | Marcan explícitamente las operaciones de negocio crítica de cada servicio. | Diseño de fase. |
| D-006 | Fijar SDK/exporters en 1.45.1, instrumentors en 0.66b1 y Collector contrib en 0.163.0. | Versiones flotantes o versiones previas. | Alinear paquetes del SDK y reproducir la instalación; mantener imagen del Collector fijada. | PyPI y versión upstream consultadas el 2026-10-14. |
| D-007 | Usar convenciones HTTP estables y sanitizar atributos de URL en hooks. | Convenciones legacy que pueden incluir query completa. | Evitar incluir valores de query en spans o etiquetas de métricas. | Revisión de instrumentación oficial. |

## Referencias

- [`fases.md`](../../fases.md) — requisito de la fase de instrumentación.
- [`ID-001`](../ID-001-microservicios-locales/00-especificacion.md) — servicios, contratos y requisitos funcionales relacionados.
- [OpenTelemetry Python: exportadores](https://opentelemetry.io/docs/languages/python/exporters/).
- [Instrumentación FastAPI](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html), [HTTPX](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/httpx/httpx.html) y [SQLAlchemy](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/sqlalchemy/sqlalchemy.html).
- [Collector: solución de problemas y exportador debug](https://opentelemetry.io/docs/collector/troubleshooting/).
- [PyPI: SDK 1.45.1](https://pypi.org/project/opentelemetry-sdk/1.45.1/), [exportador OTLP/gRPC 1.45.1](https://pypi.org/project/opentelemetry-exporter-otlp-proto-grpc/1.45.1/) y [exportador Prometheus 0.66b1](https://pypi.org/project/opentelemetry-exporter-prometheus/0.66b1/).
- [OpenTelemetry Collector release 0.163.0](https://github.com/open-telemetry/opentelemetry-collector-releases/releases/tag/v0.163.0).
