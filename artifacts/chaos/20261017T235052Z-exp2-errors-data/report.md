# Experimento exp2-errors-data

- Servicio: `data-service` · Falla: `{"error_rate": 0.1, "error_delay_ms": 500, "experiment": "exp2-errors-data"}`
- Inyección: 2026-10-17T23:50:53.908993+00:00 · Reversión: 2026-10-17T23:53:54.957941+00:00 · Recuperación: 2026-10-17T23:53:57.027714+00:00
- Hipótesis: Con 10 % de errores (503 tras 500 ms), la regla correlacionada error_rate > baseline+2σ Y p99 > SLO alerta en ≤ 2 min con un trace_id de una solicitud fallida.

## Detección (MTTD)

| Alarma | MTTD (s) |
|---|---|
| `pipeline-otel-obs-data-service-correlated-errors` | — |
| `pipeline-otel-obs-data-service-error-anomaly` | — |
| `pipeline-otel-obs-data-service-p99-slo` | 125.8 |
| `pipeline-otel-obs-data-service-static-error-rate` | 72.1 |

MTTD de la alarma primaria `pipeline-otel-obs-data-service-correlated-errors`: **—** (objetivo ≤ 120 s → no cumple).

## SLO y error budget durante la falla

| Indicador | Línea base (10 min) | Durante la falla |
|---|---|---|
| Solicitudes | 2766.1538461538457 | 913.7757575757576 |
| Disponibilidad (SLO 99 %) | 0.98406 | 0.90756 |
| Latencia p99 ms (SLO 300.0) | 593.2 | 723.0 |
| Presupuesto de la ventana consumido | — | 924.4 % |
| Presupuesto mensual consumido | — | 0.065 % |

- ¿Se degradó el SLO de disponibilidad? Sí
- ¿Se degradó el SLO de latencia? Sí
- Impacto aguas arriba (orders): disponibilidad 1.0, p99 1262.5 ms (SLO 400.0 ms).

## Accionabilidad de la alerta

- trace_id primario: `—`
- Tiempo de enriquecimiento: —
- ¿Accionable? No / pendiente de revisar
