# Experimento exp1-latency-catalog

- Servicio: `catalog` · Falla: `{"latency_ms": 200, "experiment": "exp1-latency-catalog"}`
- Inyección: 2026-10-17T23:24:17.517360+00:00 · Reversión: 2026-10-17T23:29:25.472736+00:00 · Recuperación: 2026-10-17T23:29:27.540471+00:00
- Hipótesis: Con +200 ms en catalog, la regla de degradación de latencia alerta en ≤ 2 min; el SLO p99 de catalog (150 ms) se viola y el de orders (400 ms) se mantiene.

## Detección (MTTD)

| Alarma | MTTD (s) |
|---|---|
| `pipeline-otel-obs-catalog-latency-degradation` | — |
| `pipeline-otel-obs-catalog-p99-slo` | 61.5 |
| `pipeline-otel-obs-catalog-latency-anomaly` | — |
| `pipeline-otel-obs-orders-p99-slo` | 87.0 |

MTTD de la alarma primaria `pipeline-otel-obs-catalog-latency-degradation`: **—** (objetivo ≤ 120 s → no cumple).

## SLO y error budget durante la falla

| Indicador | Línea base (10 min) | Durante la falla |
|---|---|---|
| Solicitudes | 2124.102564102564 | 1084.7333333333333 |
| Disponibilidad (SLO 99 %) | 1.0 | 1.0 |
| Latencia p99 ms (SLO 150.0) | 48.5 | 249.5 |
| Presupuesto de la ventana consumido | — | 0.0 % |
| Presupuesto mensual consumido | — | 0.0 % |

- ¿Se degradó el SLO de disponibilidad? No
- ¿Se degradó el SLO de latencia? Sí
- Impacto aguas arriba (orders): disponibilidad 1.0, p99 487.7 ms (SLO 400.0 ms).

## Accionabilidad de la alerta

- trace_id primario: `—`
- Tiempo de enriquecimiento: —
- ¿Accionable? No / pendiente de revisar
