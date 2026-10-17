# ID-003 — Fase 5: Madurez de observabilidad, roadmap y entrega

> Se implementa leyendo este documento, [`00-especificacion.md`](00-especificacion.md) y [`00-plan-general.md`](00-plan-general.md).

## Identificación

| Campo | Detalle |
|---|---|
| Plan | ID-003 — Sistema observable integrado en AWS. |
| Fase | 5 — Reporte de madurez y presentación técnica (Módulo E). |
| Estado | En curso |
| Requisitos que cubre | RF-341, RF-342, RF-351, RF-352, RNF-303 |
| Sistemas y repositorios | `specs/ID-003-sistema-observable`, `artifacts/`, repositorio público. |
| Dependencias previas | Evidencia de las fases 1–4. |
| Habilita a | Ninguna. |

## Objetivo

Autoevaluar la solución en 8 dominios con escala 1–5, proponer el roadmap a 3 meses para subir un nivel y reunir la evidencia del video y del reporte ejecutivo.

## Escala de madurez

| Nivel | Nombre | Criterio |
|---|---|---|
| 1 | Inicial | Señales aisladas, sin estándares ni correlación. |
| 2 | Gestionado | Señales recolectadas y visualizadas; alertas estáticas. |
| 3 | Definido | Estándares (OTel, semconv), correlación entre pilares y SLOs definidos. |
| 4 | Medido | SLOs con error budget operativo, detección automática validada con experimentos y métricas de MTTD. |
| 5 | Optimizado | Mejora continua automatizada: remediación, caos recurrente, gobierno de datos de telemetría. |

## Autoevaluación (provisional, A-301)

Los dominios oficiales del «Observability Foundation Blueprint» no están en el repositorio. Se usan 8 dominios derivados del enunciado (tres pilares, OpenTelemetry, AIOps, red, DataOps, SRE) más seguridad y resiliencia. Los niveles marcados con * dependen de confirmar la evidencia funcional en AWS.

| # | Dominio | Nivel | Evidencia | Brecha principal |
|---|---|---|---|---|
| 1 | Telemetría: tres pilares y correlación | 3* | Trazas, métricas y logs JSON con `trace_id` en los tres servicios; pivote log → traza en Grafana. | Sin exemplars ni enlace automático traza → logs. |
| 2 | Instrumentación y estándares OTel | 3 | SDK 1.45.1, semconv HTTP y DB estables, spans de negocio, histograma `db.client.operation.duration`. | Sin muestreo configurable ni instrumentación de colas/eventos. |
| 3 | Pipeline y gestión de datos de telemetría (DataOps) | 2 | Collector con `memory_limiter`, `batch`, `resource`, `servicegraph`; métricas propias del Collector. | Sin tail sampling, control de cardinalidad, retención ni costo por señal. |
| 4 | Visualización y análisis | 3* | Cuatro dashboards versionados y generados por código; tabla de alertas enriquecidas. | Dashboards sin pruebas automáticas ni variables por entorno. |
| 5 | Alertamiento y AIOps | 3* | Bandas 2σ, regla correlacionada, Lambda con `trace_id` y runbook, DevOps Guru, reporte de ruido. | Sin deduplicación entre servicios ni supresión por dependencia (prototipo de la actividad 3.1 no integrado). |
| 6 | Observabilidad de red y seguridad | 2* | Flow Logs con N-S/E-W y rechazos, Service Connect L7, Security Hub FSBP, Inspector, logins fallidos. | Sin CloudTrail, sin detección de exfiltración ni correlación hallazgo → servicio. |
| 7 | SRE: SLO, error budget y gestión de incidentes | 3* | SLO de disponibilidad y latencia por servicio, burn rate, error budget por ventana. | Sin política de error budget aprobada, postmortems ni on-call. |
| 8 | Resiliencia y caos | 3* | Inyección en caliente, dos experimentos con hipótesis, MTTD medido y reversión automática. | Experimentos manuales, sin game days ni caos a nivel de red/infraestructura. |

**Promedio provisional: 2,75.** Objetivo a 3 meses: llevar los dominios 3 y 6 a nivel 3 y los dominios 5, 7 y 8 a nivel 4 (promedio ≥ 3,4).

## Roadmap a 3 meses

| Mes | Iniciativa | Dominio | Resultado verificable | Indicador |
|---|---|---|---|---|
| 1 | Tail sampling (errores y latencia > SLO al 100 %, resto al 10 %) y límites de cardinalidad en el Collector. | 3 | Configuración versionada y medición de volumen antes/después. | −60 % de spans almacenados sin perder trazas de error. |
| 1 | Exemplars en histogramas HTTP y enlace Jaeger → CloudWatch Logs. | 1, 4 | Clic desde un pico de p99 a la traza y de la traza a sus logs. | 100 % de alertas con navegación de un clic. |
| 1 | CloudTrail a CloudWatch Logs con métricas de `AccessDenied` y `ConsoleLogin` fallido. | 6 | Panel de autenticación AWS en Golden Signals. | Alerta ≤ 5 min ante 5 fallos. |
| 2 | Política de error budget y alertas de burn rate multi-ventana (1 h/5 min y 6 h/30 min). | 7 | Documento aprobado y alarmas compuestas por burn rate. | 0 alertas de SLO sin budget asociado. |
| 2 | Integrar deduplicación y supresión por dependencia (prototipo 3.1) en la Lambda. | 5 | Una sola notificación cuando catalog arrastra a orders. | Reducción adicional de notificaciones ≥ 30 % en caos encadenado. |
| 2 | Postmortem estándar y runbooks enlazados desde cada alarma. | 7 | Plantilla y dos postmortems de los experimentos. | MTTR medido por incidente. |
| 3 | Caos programado semanal (scheduler + runner) con criterio de aborto por SLO. | 8 | Reporte semanal automático en `artifacts/chaos`. | 4 ejecuciones/mes con MTTD ≤ 120 s. |
| 3 | AWS FIS para fallas de red/infraestructura (pérdida de paquetes, parada de tareas). | 8, 6 | Dos experimentos nuevos con hipótesis. | MTTD y MTTR por tipo de falla. |
| 3 | Despliegue de la referencia GCP (Cloud SQL, Cloud Monitoring, SCC). | 1, 6 | Vista multinube en Grafana. | Mismos SLIs en ambas nubes. |

## Evidencias para el video y el reporte ejecutivo (RF-352)

| # | Evidencia | Origen |
|---|---|---|
| 1 | Diagrama de arquitectura y `terraform apply` final. | `infra/aws-observable/README.md`, terminal. |
| 2 | Traza C-301 en Jaeger con spans DB y sus atributos. | Jaeger / Grafana Explore. |
| 3 | Dashboard de servicios con SLO, error budget y grafo de servicios. | Grafana `ID-003 · Servicios y SLO`. |
| 4 | Métricas Service Connect y Flow Logs N-S/E-W. | Grafana `ID-003 · Red L7`. |
| 5 | Golden Signals de Seguridad con logins fallidos, rechazos y CVEs. | Grafana `ID-003 · Golden Signals de Seguridad`. |
| 6 | Experimentos 1 y 2 en vivo: inyección, alarma, correo enriquecido, traza, recuperación. | Terminal, Grafana AIOps, SNS. |
| 7 | `report.md` de ambos experimentos y reporte de ruido. | `artifacts/chaos`, `artifacts/aiops`. |
| 8 | Insight de DevOps Guru (si se generó). | Consola DevOps Guru. |
| 9 | Autoevaluación y roadmap. | Este documento. |

## Tareas

| Estado | # | Tarea | Criterio de aceptación |
|---|---|---|---|
| [x] | 1 | Autoevaluación provisional y roadmap. | Tablas completas. |
| [ ] | 2 | Resolver A-301 y ajustar dominios/niveles con evidencia real. | Sin niveles marcados con *. |
| [ ] | 3 | Reunir evidencias 1–9. | Capturas y reportes en `artifacts/`. |
| [ ] | 4 | Repositorio público con etiqueta `v1.0`. | Etiqueta visible en GitHub. |
| [ ] | 5 | Video y PDF de 10 páginas. | Entregados. |
| [ ] | 6 | `terraform destroy`. | Sin recursos activos. |

## Validación

| Estado | Tipo | Qué verifica | Cómo se ejecuta | Resultado esperado |
|---|---|---|---|---|
| Pendiente | Revisión | RF-341, RF-342 | Revisión del equipo contra el blueprint oficial | Dominios y niveles confirmados. |
| Pendiente de confirmación | Operativa | RF-351 | Repositorio y etiqueta | `v1.0` publicado. |
| Pendiente | Reversión | RNF-303 | `terraform destroy` | Sin recursos. |

## Cierre de la fase

- **Resultado obtenido:** Parcial: autoevaluación y roadmap provisionales; evidencias y entregables pendientes.
- **Desviaciones respecto al diseño:** Ninguna.
- **Decisiones tomadas durante la fase:** D-315.
- **Requisitos afectados en su cobertura:** RF-341/RF-342 provisionales; RF-351/RF-352 pendientes.
- **Actualizaciones aplicadas a `00-plan-general.md`:** Estado.
- **Actualizaciones aplicadas a `00-especificacion.md`:** Ninguna.
- **Pendientes trasladados:** Tareas 2–6 como pendientes abiertos del plan.
