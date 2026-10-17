# ID-003 — Informe final: sistema observable integrado en AWS

## Identificación

| Campo | Detalle |
|---|---|
| ID | ID-003 |
| Título | Sistema observable completo en AWS. |
| Sprint / iteración | No documentado. |
| Estado de cierre | Implementación parcial: código, IaC y scripts completos; validación funcional en AWS pendiente. |
| Sistemas y repositorios afectados | Ver [`00-plan-general.md`](00-plan-general.md). |
| Iniciativas relacionadas | ID-001, ID-002. |

## Resumen

El plan extiende el laboratorio con data-service sobre Amazon RDS, una malla L7 con ECS Service Connect, detección de anomalías con regla de correlación y alertas enriquecidas con `trace_id`, observabilidad de red y seguridad, y experimentos de caos con medición de MTTD. Todo quedó implementado y la validación automatizada y el smoke local están aprobados. El despliegue en AWS, los experimentos y las evidencias para el video y el PDF siguen abiertos.

## Resultado por fase

| Estado | Fase | Resultado entregado | Desviación respecto al diseño |
|---|---|---|---|
| Implementada sin validar | Fase 1 — Arquitectura y data-service | Tres servicios, RDS, Service Connect, DB semconv, Compose. | Ninguna. |
| Implementada sin validar | Fase 2 — AIOps | SLIs, bandas 2σ, regla correlacionada, Lambda, DevOps Guru, reporte de ruido. | Sin política SNS explícita (D-306/fase 2). |
| Implementada sin validar | Fase 3 — Red y seguridad | Flow Logs, Security Hub, Inspector, dashboards. | N-S como diferencia de métricas. |
| Implementada sin validar | Fase 4 — Caos y MTTD | Middleware, SSM, runner, reglas SLO, k6. | Ninguna. |
| En curso | Fase 5 — Madurez y entrega | Autoevaluación y roadmap provisionales. | — |

## Evidencia de validación

| Tipo | Qué se verificó | Resultado |
|---|---|---|
| Automatizada | 18 pruebas (caos, DB semconv con PostgreSQL 16, enriquecedor, seguridad, ruido). | Aprobadas. |
| Estática | `otelcol-contrib validate`, `promtool check rules`, análisis HCL de 37 archivos y coherencia de variables de módulos. | Aprobadas. `terraform validate` no ejecutado (sin acceso al registro en el entorno de desarrollo). |
| Funcional local | Tres servicios con caos, Collector 0.162.0 y Prometheus 3.13.3. | Traza entre tres servicios, reglas SLI con series, `servicegraph` y histograma DB disponibles. |
| Funcional AWS | Despliegue, alarmas, experimentos. | Pendiente de confirmación. |

## Limitaciones conocidas

- GCP solo como IaC de referencia no aplicada (D-301).
- DevOps Guru no acepta clientes nuevos desde el 29-10-2026.
- Paneles CloudWatch de Grafana generados sin prueba en UI.
- Dominios del blueprint provisionales (A-301).

## Pendientes abiertos

1. `terraform validate/plan/apply` y corrección de lo que reporte.
2. Línea base ≥ 3 h, experimentos 1 y 2, reporte de ruido y señales de seguridad.
3. Evidencias, video, PDF, etiqueta `v1.0` y `terraform destroy`.
