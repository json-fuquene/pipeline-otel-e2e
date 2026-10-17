# ID-003 — Fase 4: Chaos Engineering controlado y MTTD

> Se implementa leyendo este documento, [`00-especificacion.md`](00-especificacion.md) y [`00-plan-general.md`](00-plan-general.md).

## Identificación

| Campo | Detalle |
|---|---|
| Plan | ID-003 — Sistema observable integrado en AWS. |
| Fase | 4 — Chaos Engineering y validación de MTTD (Módulo D). |
| Estado | Implementada sin validar |
| Requisitos que cubre | RF-331–RF-334, RNF-305 |
| Sistemas y repositorios | `services/shared/chaos.py`, parámetros SSM en `infra/tf_modules/ecs-observable`, `scripts/chaos/run_experiment.py`, `scripts/load/steady.js`, `docker/prometheus/rules/slo.yml`. |
| Dependencias previas | Fases 1 y 2; línea base de carga ≥ 3 h. |
| Habilita a | Fase 5. |

## Objetivo

Dos experimentos de caos en el sandbox demuestran detección en ≤ 2 min, cuantifican el impacto en SLO y error budget y verifican que la alerta sea accionable.

## Diseño

### Mecanismo de inyección (RF-331)

`ChaosController` lee `/pipeline-otel-obs/chaos/<servicio>` cada 5 s (local: variables `CHAOS_*`). El middleware queda dentro del middleware de logging, de modo que `duration_ms` y `status_code` reflejan la falla:

```json
{"latency_ms": 200, "error_rate": 0.10, "error_delay_ms": 500, "experiment": "exp2-errors-data"}
```

- Latencia: `sleep(latency_ms)` y evento de span `chaos.latency_injected`.
- Error: con probabilidad `error_rate`, espera `error_delay_ms` y responde 503 `chaos_injected`; atributo `chaos.injected=true` en el span.
- Cada cambio emite el log `chaos_config_changed` (inicio/fin visibles en Grafana). Salud, métricas y documentación nunca fallan.

### Experimentos (RF-332)

| | Experimento 1 | Experimento 2 |
|---|---|---|
| Servicio | `catalog` (service-b, S-306) | `data-service` |
| Falla | `latency_ms = 200` | `error_rate = 0.10`, `error_delay_ms = 500` (D-309) |
| Hipótesis | `catalog-latency-degradation` en ALARM ≤ 120 s; SLO p99 de catalog (150 ms) violado; SLO de orders (400 ms) se mantiene. | `data-service-correlated-errors` en ALARM ≤ 120 s con `trace_id` de un 503. |
| Alarma primaria | `pipeline-otel-obs-catalog-latency-degradation` | `pipeline-otel-obs-data-service-correlated-errors` |
| Duración | 300 s con falla + recuperación | 300 s con falla + recuperación |

### Medición (RF-333, RF-334)

- **MTTD** = `StateUpdatedTimestamp` de la primera transición a ALARM − instante de escritura del parámetro SSM. Incluye la latencia de sondeo (≤ 5 s) y del pipeline de telemetría.
- **SLO**: disponibilidad 99 % y latencia p99 por servicio, calculados en Prometheus sobre la ventana de la falla y comparados con los 10 min previos.
- **Error budget**: consumo en la ventana (`errores / (1 % · solicitudes)`) y proyección sobre el presupuesto mensual al ritmo observado.
- **Accionabilidad**: la alerta enriquecida contiene `primary_trace_id`, evidencia y runbook.

El runner revierte el parámetro en `finally` aun ante interrupción y guarda `report.json` y `report.md` en `artifacts/chaos/<ts>-<experimento>/`.

## Tareas

| Estado | # | Tarea | Criterio de aceptación |
|---|---|---|---|
| [x] | 1 | Controlador y middleware de caos en los tres servicios. | `tests/test_chaos.py` (7 pruebas) aprobado. |
| [x] | 2 | Parámetros SSM y permiso `ssm:GetParameter` en el rol de aplicación. | HCL válido. |
| [x] | 3 | Reglas de registro SLI/SLO en Prometheus. | `promtool check rules` y series en smoke local. |
| [x] | 4 | Runner de experimentos y generador de carga k6. | `--help` funcional; flujo revisado. |
| [x] | 5 | Smoke local de caos. | Catálogo +200 ms (~205 ms por solicitud); data-service 30 % de 503 a 100 ms; pedidos 201 con `data_record_failed`. |
| [ ] | 6 | Ejecutar experimento 1 en AWS. | `report.md` con MTTD ≤ 120 s. |
| [ ] | 7 | Ejecutar experimento 2 en AWS. | `report.md` con MTTD ≤ 120 s y `trace_id`. |

## Validación

| Estado | Tipo | Qué verifica | Cómo se ejecuta | Resultado esperado |
|---|---|---|---|---|
| Aprobada | Automatizada | RF-331 | `pytest tests/test_chaos.py` | 7 pruebas aprobadas. |
| Aprobada (entorno de desarrollo) | Funcional local | RF-331 | Variables `CHAOS_*` con los tres servicios | Latencia y 503 inyectados visibles en logs y métricas. |
| Pendiente de confirmación | Funcional AWS | RF-332–RF-334 | `python3 scripts/chaos/run_experiment.py exp1-latency-catalog --config artifacts/aws/lab_config.json --prometheus http://IP:9090` | MTTD ≤ 120 s, SLO catalog violado, orders dentro del SLO. |
| Pendiente de confirmación | Funcional AWS | RF-332–RF-334 | `… exp2-errors-data …` | MTTD ≤ 120 s, alerta con `trace_id`, presupuesto consumido reportado. |
| Pendiente | Reversión | RNF-305 | Revisar parámetro tras el runner | `{"enabled": false}` y alarmas en OK. |

## Riesgos y bloqueantes de la fase

| Estado | Elemento | Impacto | Mitigación o siguiente acción |
|---|---|---|---|
| Abierto | MTTD cercano al límite por resolución de 60 s. | Medio | Reportar el valor real; si supera 120 s, documentar la causa y el ajuste propuesto (p. ej. métricas de alta resolución). |
| Abierto | Bandas de anomalía sin entrenamiento. | Alto | Línea base ≥ 3 h antes de los experimentos. |
| Abierto | Experimento 1 podría no violar la banda si el p99 base ya es alto. | Medio | Revisar p99 base en el reporte; ajustar SLO solo con decisión registrada. |

## Cierre de la fase

- **Resultado obtenido:** Implementado sin validar en AWS.
- **Desviaciones respecto al diseño:** Ninguna.
- **Decisiones tomadas durante la fase:** D-308, D-309.
- **Requisitos afectados en su cobertura:** RF-332–RF-334 pendientes de ejecución.
- **Actualizaciones aplicadas a `00-plan-general.md`:** Estado.
- **Actualizaciones aplicadas a `00-especificacion.md`:** Ninguna.
- **Pendientes trasladados:** Tareas 6 y 7.
