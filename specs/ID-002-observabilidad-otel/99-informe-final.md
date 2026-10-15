# ID-002 — Informe de implementación: instrumentación OpenTelemetry local

## Identificación

| Campo | Detalle |
|---|---|
| ID | ID-002 |
| Título | Instrumentación OpenTelemetry de catálogo y pedidos. |
| Sprint / iteración | No documentado. |
| Estado de cierre | Implementación parcial; validación operativa pendiente. |
| Sistemas y repositorios afectados | Servicios de catálogo y pedidos, Docker Compose, OTel Collector y documentación local. |
| Iniciativas relacionadas | ID-001 — servicios funcionales instrumentados por esta iniciativa. |

## Resumen

Quedó implementada la instrumentación OpenTelemetry de los servicios, incluyendo trazas HTTP/SQLAlchemy, métricas HTTP y logs JSON correlacionados. Compose incorpora un Collector OTLP con exportación `debug`, y README documenta los endpoints locales. La sintaxis Python y la configuración de Compose pasaron sus comprobaciones estáticas. No se pudo construir ni levantar el entorno porque el socket Docker está denegado y PyPI no resuelve desde este runtime; por tanto, la correlación de extremo a extremo sigue pendiente.

## Problema atendido

Los servicios no ofrecían trazas distribuidas, métricas consultables ni IDs de traza en sus logs estructurados.

## Resultado por fase

| Estado | Fase | Resultado entregado | Desviación respecto al diseño |
|---|---|---|---|
| Implementada sin validar | Fase 1 — Instrumentación OpenTelemetry | SDK e instrumentors configurados, spans de negocio, métricas HTTP, campos de correlación, Collector y documentación local. | La validación operativa queda pendiente por falta de acceso a Docker y PyPI. |

## Cumplimiento de requisitos

| Estado | Requisito | Evidencia |
|---|---|---|
| Implementado; por validar | RF-001 a RF-008 | Instrumentación en código; falta observar spans y métricas en runtime. |
| Implementado; por validar | RNF-001 a RNF-004 | Cambios aditivos; falta smoke funcional y revisión de telemetría real. |

## Cambios entregados

| Ubicación | Cambio aplicado | Efecto observable |
|---|---|---|
| `services/catalog/app` y `services/orders/app` | SDK, instrumentors, spans de negocio y logs con contexto de traza. | Las APIs quedan configuradas para producir telemetría correlacionada. |
| `compose.yaml`, `docker/otel-collector/config.yaml` | Collector local y puertos dedicados de métricas. | Collector recibe OTLP por red interna; métricas usan puertos de host 9464/9465. |
| `README.md`, `specs/ID-002-observabilidad-otel/` | Instrucciones, criterios y estado de validación. | El flujo y sus límites se documentan para ejecución y revisión. |

## Evidencia de validación

| Tipo | Qué se verificó | Resultado |
|---|---|---|
| Automatizada / estática | `python3 -m compileall -q services`; `docker compose config --quiet`. | Aprobadas. |
| Build de imágenes | `docker compose build catalog orders otel-collector`. | No ejecutado: acceso al archivo Buildx bloqueado por sandbox; reintento sin config Docker falló por permisos del socket Docker. |
| Dependencias | `python3 -m pip install --target /tmp/otel-validation -r services/catalog/requirements.txt -r services/orders/requirements.txt`. | No ejecutado: DNS de `pypi.org` no resuelve; no se instalaron paquetes. |
| Funcional / operativa | Métricas y traza pedidos→catálogo→PostgreSQL. | Pendiente de confirmación. |
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
- No se ha comprobado la compatibilidad efectiva de las nuevas dependencias en una imagen Python 3.12.

## Pendientes y bloqueantes

| Id | Pendiente o bloqueante | Impacto | Siguiente acción | Dónde continúa |
|---|---|---|---|---|
| 1 | Obtener acceso al daemon Docker y al registry de imágenes. | Sin build o arranque local no se valida Compose ni el Collector. | Ejecutar `docker compose up -d --build --wait` y revisar salud. | ID-002, fase 1 |
| 2 | Resolver DNS/acceso a PyPI para instalar las dependencias. | Las importaciones OTel no se han ejecutado en este entorno. | Construir imágenes con acceso al índice de paquetes y corregir incompatibilidades encontradas. | ID-002, fase 1 |
| 3 | Ejecutar el flujo extremo a extremo. | RF-001–RF-008 siguen sin evidencia funcional. | Crear producto y pedido; revisar `/metrics`, logs y salida del Collector. | ID-002, fase 1 |

## Estado de cierre

La implementación está presente y pasó validaciones sintácticas y de configuración Compose. La fase y el plan permanecen `Implementada sin validar`; no se afirma que las dependencias importen correctamente, que los contenedores inicien ni que se haya observado una traza real. Gate 4 queda pendiente hasta registrar la validación operativa.

## Próximos pasos recomendados

1. Construir e iniciar el entorno en una máquina con Docker y acceso a PyPI.
2. Confirmar métricas, correlación de spans y logs, y actualizar los estados de fase y plan con evidencia.

## Verificación de cierre documental

Gate 4 queda pendiente junto con la validación funcional; el estado de la fase y del plan refleja esa limitación.
