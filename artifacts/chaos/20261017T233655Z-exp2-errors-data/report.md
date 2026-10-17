# Experimento exp2-errors-data

- Servicio: `data-service` · Falla: `{"error_rate": 0.1, "error_delay_ms": 500, "experiment": "exp2-errors-data"}`
- Inyección: 2026-10-17T23:36:56.417262+00:00 · Reversión: 2026-10-17T23:42:04.476994+00:00 · Recuperación: 2026-10-17T23:42:06.587919+00:00
- Hipótesis: Con 10 % de errores (503 tras 500 ms), la regla correlacionada error_rate > baseline+2σ Y p99 > SLO alerta en ≤ 2 min con un trace_id de una solicitud fallida.

## Detección (MTTD)

| Alarma | MTTD (s) |
|---|---|
| `pipeline-otel-obs-data-service-correlated-errors` | — |
| `pipeline-otel-obs-data-service-error-anomaly` | — |
| `pipeline-otel-obs-data-service-p99-slo` | 123.3 |
| `pipeline-otel-obs-data-service-static-error-rate` | 69.6 |

MTTD de la alarma primaria `pipeline-otel-obs-data-service-correlated-errors`: **—** (objetivo ≤ 120 s → no cumple).

## SLO y error budget durante la falla

| Indicador | Línea base (10 min) | Durante la falla |
|---|---|---|
| Solicitudes | 2728.205128205128 | 1551.472077605779 |
| Disponibilidad (SLO 99 %) | 1.0 | 0.89857 |
| Latencia p99 ms (SLO 300.0) | 61.3 | 725.4 |
| Presupuesto de la ventana consumido | — | 1014.3 % |
| Presupuesto mensual consumido | — | 0.121 % |

- ¿Se degradó el SLO de disponibilidad? Sí
- ¿Se degradó el SLO de latencia? Sí
- Impacto aguas arriba (orders): disponibilidad 1.0, p99 1074.0 ms (SLO 400.0 ms).

## Accionabilidad de la alerta

- trace_id primario: `—`
- Tiempo de enriquecimiento: —
- ¿Accionable? No / pendiente de revisar
