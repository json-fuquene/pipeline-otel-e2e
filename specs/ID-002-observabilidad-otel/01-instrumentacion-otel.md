# ID-002 — Fase 1: Instrumentación OpenTelemetry

## Identificación

| Campo | Detalle |
|---|---|
| Plan | ID-002 — Instrumentación OpenTelemetry de catálogo y pedidos. |
| Fase | 1 — Instrumentación OTel |
| Estado | Implementada sin validar |
| Requisitos que cubre | RF-001–RF-008, RNF-001–RNF-004 |
| Sistemas y repositorios | `services/catalog`, `services/orders`, `compose.yaml`, `docker/otel-collector/config.yaml`, `README.md`. |
| Dependencias previas | Servicios y Compose de ID-001. |
| Habilita a | Ninguna. |

## Objetivo

Cada API genera trazas HTTP y de PostgreSQL, publica métricas HTTP en formato Prometheus y emite logs JSON correlacionados. Los spans se exportan al Collector local por OTLP/gRPC.

## Contexto de la fase

Pedidos consume catálogo por HTTP y ambos servicios usan SQLAlchemy asíncrono sobre PostgreSQL. El contexto W3C debe fluir en la llamada de pedidos a catálogo; `X-Request-ID` sigue siendo un identificador funcional independiente.

## Alcance técnico

### Cambios previstos

| Ubicación | Cambio | Requisito asociado |
|---|---|---|
| `services/*/requirements.txt` | Fijar SDK, exportadores y instrumentors de FastAPI/SQLAlchemy; HTTPX también para pedidos. | RF-001–RF-005, RNF-004 |
| `services/*/app/telemetry.py` | Configurar providers/resource, OTLP, exportador Prometheus, instrumentors y ciclo de vida del endpoint. | RF-001–RF-005, RF-007 |
| `services/*/app/main.py` | Instrumentar FastAPI, iniciar el endpoint de métricas, excluir healthchecks y agregar spans de negocio. | RF-001, RF-004, RF-005, RF-008 |
| `services/*/app/database.py` | Asociar cada engine SQLAlchemy con el SDK OTel. | RF-003 |
| `services/*/app/observability.py` | Incluir `trace_id` y `span_id` en el evento JSON por solicitud. | RF-006, RNF-002 |
| `compose.yaml`, `docker/otel-collector/config.yaml` | Incorporar Collector OTLP/debug, configuración de endpoints y puertos locales. | RF-002, RF-007, RNF-003, RNF-004 |
| `README.md` | Documentar URLs de métricas, consulta de trazas y límites locales. | RNF-003, RNF-004 |

### No incluido en esta fase

- Prometheus server, Grafana, Jaeger u otro backend/visor.
- Exportación OTLP de logs, métricas de negocio y métricas específicas de PostgreSQL.
- Cambios a los contratos y reglas funcionales de ID-001.

## Diseño

Cada proceso configura un `TracerProvider` con `service.name` (`catalog` u `orders`) y un `BatchSpanProcessor` con `OTLPSpanExporter` al Collector. `FastAPIInstrumentor` crea spans y métricas HTTP para rutas con plantillas; las rutas `/health/live` y `/health/ready` quedan excluidas. En pedidos, `HTTPXClientInstrumentor` crea el span cliente e inyecta el contexto W3C. `SQLAlchemyInstrumentor` se conecta al engine asíncrono mediante `engine.sync_engine`.

Los hooks de HTTP eliminan valores de query de los spans y se habilitan convenciones HTTP estables para impedir atributos de métricas con la URL query completa. `PrometheusMetricReader` publica métricas en el puerto interno 9464. Compose mapea catálogo al 9464 local y pedidos al 9465 local. Los logs permanecen en stdout; el middleware toma el contexto span activo, sin sustituir `request_id`. El Collector escucha OTLP/gRPC en 4317 y escribe un resumen de spans con `debug`.

### Comportamiento esperado por caso

| Caso | Condición | Resultado esperado |
|---|---|---|
| C-001 | Crear producto válido. | Span HTTP, `catalog.product.create`, span SQL y log correlacionado. |
| C-002 | Crear pedido válido. | Una traza cruza pedidos→HTTPX→catálogo y contiene spans SQL en ambos servicios. |
| C-003 | Consultar ambos endpoints `/metrics`. | Respuesta Prometheus con métricas HTTP de cada servicio. |
| C-004 | Collector fuera de servicio. | API funcional sigue respondiendo; telemetría no modifica el contrato HTTP. |
| C-005 | Consultar health. | Respuesta funcional sin span de servidor para health. |
| C-006 | Enviar datos/cabeceras de solicitud. | No se exportan cuerpos, valores query o cabeceras sensibles. |

## Tareas

Las tareas marcadas con `[P]` pueden ejecutarse en paralelo entre sí.

| Estado | # | Tarea | Criterio de aceptación |
|---|---|---|---|
| [x] | 1 | Agregar dependencias OTel fijadas a ambas imágenes. | Mismas versiones de API/SDK/exporters e instrumentors compatibles en ambos servicios. |
| [x] | 2 | `[P]` Configurar providers, instrumentación y servidor de métricas en cada servicio. | Cada servicio identifica `service.name` y expone métricas en 9464 interno. |
| [x] | 3 | `[P]` Correlacionar logs JSON y agregar spans explícitos de negocio. | Logs incluyen IDs activos; las dos operaciones de negocio tienen spans nombrados. |
| [x] | 4 | Agregar Collector OTLP/debug y puertos de métricas a Compose. | Collector recibe OTLP; ports locales no se solapan con APIs. |
| [x] | 5 | Documentar operación de métricas y trazas. | README muestra URLs y consulta de logs Collector. |
| [ ] | 6 | Ejecutar validaciones automatizadas y smoke local. | Compose inicia; respuestas API y métricas correctas; traza correlacionada registrada. |

## Validación

| Estado | Tipo | Qué verifica | Cómo se ejecuta | Resultado esperado |
|---|---|---|---|---|
| Aprobada | Automatizada | Sintaxis Python. | `python3 -m compileall -q services` | Salida 0. |
| Aprobada | Estática | Compose sin imprimir valores interpolados. | `docker compose config --quiet` | Salida 0. |
| Pendiente | Funcional / operativa | Builds, APIs, métricas y exportación de spans. | Pasos documentados en README. | Métricas HTTP en ambos puertos y spans de catálogo/pedidos en `docker compose logs otel-collector`. |
| Pendiente | Reversión | Compatibilidad de endpoints funcionales y apagado limpio. | Ejecutar smoke ID-001; `docker compose down`. | APIs mantienen respuestas; servicios detienen exporters sin perder datos. |

## Riesgos y bloqueantes de la fase

| Estado | Elemento | Impacto | Mitigación o siguiente acción |
|---|---|---|---|
| Abierto | El socket Docker no permite al usuario actual conectarse. | Alto | Ejecutar build y smoke en un entorno con acceso al daemon Docker. |
| Abierto | La resolución DNS de PyPI falla y el runtime no tiene dependencias instaladas. | Alto | Repetir instalación/build en un entorno con acceso a PyPI. |

## Cierre de la fase

- **Resultado obtenido:** Implementado sin validar.
- **Desviaciones respecto al diseño:** Ninguna conocida.
- **Decisiones tomadas durante la fase:** D-004, D-005, D-006, D-007.
- **Requisitos afectados en su cobertura:** RF-001–RF-008 y RNF-001–RNF-004 implementados; validación pendiente.
- **Actualizaciones aplicadas a `00-plan-general.md`:** Estado de fase y riesgos registrados.
- **Actualizaciones aplicadas a `00-especificacion.md`:** Ninguna.
- **Pendientes trasladados:** Validación automatizada y funcional local pendientes.
