# ID-003 — Fase 2: AIOps — anomalías, correlación y ruido

> Se implementa leyendo este documento, [`00-especificacion.md`](00-especificacion.md) y [`00-plan-general.md`](00-plan-general.md).

## Identificación

| Campo | Detalle |
|---|---|
| Plan | ID-003 — Sistema observable integrado en AWS. |
| Fase | 2 — AIOps (Módulo B). |
| Estado | Implementada sin validar |
| Requisitos que cubre | RF-311–RF-314 |
| Sistemas y repositorios | `infra/tf_modules/aiops`, `infra/lambda/alert_enricher`, `scripts/aiops/noise_report.py`, `docker/grafana/dashboards-observable/aiops.json`. |
| Dependencias previas | Fase 1 (logs OTel en CloudWatch). |
| Habilita a | Fase 4. |

## Objetivo

Una alerta enriquecida con el `trace_id` de una solicitud fallida se emite solo cuando la tasa de error supera su baseline + 2σ y, a la vez, el p99 supera el SLO; un reporte cuantifica la reducción de ruido frente a umbrales estáticos.

## Diseño

### SLIs (RF-311)

Metric filters sobre `/pipeline-otel/pipeline-otel-obs` (JSON de los logs de solicitud) publican en `PipelineOtel/Services`, dimensión `service`, excluyendo `/health/live` y `/health/ready`:

| Métrica | Filtro | Valor |
|---|---|---|
| `RequestCount` | `status_code >= 100` | 1 |
| `ServerErrorCount` | `status_code >= 500` | 1 |
| `RequestLatency` | `status_code >= 100` | `duration_ms` (admite p99) |

### Alarmas por servicio (catalog, orders, data-service)

| Alarma | Grupo | Regla | Acción |
|---|---|---|---|
| `*-static-error-rate` | Estática (comparación) | `100·errors/requests > 1 %`, 1/1 de 60 s | Tópico `alarms-static` |
| `*-p99-slo` | Estática / componente | `p99 > SLO` (150 / 400 / 300 ms) | Tópico `alarms-static` |
| `*-error-anomaly` | Componente AIOps | `error_rate > ANOMALY_DETECTION_BAND(error_rate, 2)` | Ninguna |
| `*-latency-anomaly` | Componente AIOps | `p99 > ANOMALY_DETECTION_BAND(p99, 2)` | Ninguna |
| `*-correlated-errors` | **Regla de correlación** | `ALARM(error-anomaly) AND ALARM(p99-slo)` | Lambda → tópico enriquecido |
| `*-latency-degradation` | AIOps | `ALARM(p99-slo) AND ALARM(latency-anomaly)` | Lambda → tópico enriquecido |

La descripción de cada alarma es JSON (`service`, `kind`, `group`, `rule`) y guía a la Lambda.

### Enriquecimiento (RF-313)

La Lambda consulta Logs Insights en la ventana `[cambio de estado − 10 min, ahora + 1 min]`:

- `correlated`/`error`: solicitudes 5xx del servicio con `trace_id`, más recientes primero.
- `latency`: solicitudes más lentas con `trace_id`.
- `network`/`security`: pares de flujos o hallazgos (fase 3).

Publica asunto `[ALARM] <servicio> — <tipo> — <alarma>`, cuerpo con `trace_id` primario, evidencia y runbook, y la misma alerta en JSON en su log (tabla en Grafana). Cuenta `EnrichedAlerts` y `ActionableAlerts` en `PipelineOtel/AIOps`. Si la consulta falla, publica igual con `evidence_error`.

### DevOps Guru (RF-312)

Cobertura `AWS_TAGS` con la clave `DevOps-Guru-pipeline-otel-obs = data-service` aplicada al servicio ECS data-service y a RDS; canal de notificación al tópico enriquecido (DevOps Guru agrega la política del tópico en la misma cuenta).

### Reducción de ruido (RF-314)

`scripts/aiops/noise_report.py` produce dos tablas sobre la misma ventana: transiciones reales a ALARM (estáticas vs. compuestas) y una reproducción por minuto con baseline móvil de 60 min (media + 2σ) que cuenta episodios de notificación de cada regla.

## Tareas

| Estado | # | Tarea | Criterio de aceptación |
|---|---|---|---|
| [x] | 1 | Metric filters, alarmas estáticas, de anomalía y compuestas. | HCL válido; nombres expuestos en `lab_config`. |
| [x] | 2 | Lambda enriquecedora y suscripción SNS. | `tests/test_aiops.py` aprobado (trace_id, runbook, OK sin consultas, falla de consulta). |
| [x] | 3 | DevOps Guru por etiqueta y canal SNS. | Recursos declarados con `enable_devops_guru`. |
| [x] | 4 | Reporte de ruido. | Prueba de reproducción: 1 notificación AIOps frente a varias estáticas. |
| [x] | 5 | Dashboard AIOps (bandas, SLO, alertas, cambios de caos). | JSON generado por script. |
| [ ] | 6 | Línea base ≥ 3 h y ejecución del reporte de ruido en AWS. | `artifacts/aiops/noise-*.md` con datos reales. |
| [ ] | 7 | Verificar una alerta enriquecida real (fase 4). | Correo/SNS con `primary_trace_id` abrible en Jaeger. |

## Validación

| Estado | Tipo | Qué verifica | Cómo se ejecuta | Resultado esperado |
|---|---|---|---|---|
| Aprobada | Automatizada | RF-313, RF-314 (lógica) | `python3 -m pytest -q tests/test_aiops.py` | 7 pruebas aprobadas. |
| Pendiente de confirmación | Funcional | RF-311 | CloudWatch → `PipelineOtel/Services` | Series por servicio tras la carga. |
| Pendiente de confirmación | Funcional | RF-312, RF-313 | Experimento 2 | `data-service-correlated-errors` en ALARM y alerta con trace_id. |
| Pendiente de confirmación | Funcional | RF-314 | `noise_report.py --hours 6` | Reducción reportada con datos reales. |

## Riesgos y bloqueantes de la fase

| Estado | Elemento | Impacto | Mitigación o siguiente acción |
|---|---|---|---|
| Abierto | Bandas poco entrenadas. | Alto | Línea base ≥ 3 h; la regla exige además SLO. |
| Abierto | DevOps Guru sin clientes nuevos desde 29-10-2026. | Medio | Aplicar antes o desactivar y declararlo. |
| Abierto | La regla estática puede no generar ruido si el tráfico es muy estable. | Medio | Reportar el valor medido; no forzar resultados. |

## Cierre de la fase

- **Resultado obtenido:** Implementado sin validar en AWS.
- **Desviaciones respecto al diseño:** No se declara `aws_sns_topic_policy` para el tópico enriquecido (DevOps Guru la gestiona).
- **Decisiones tomadas durante la fase:** D-305, D-306, D-307.
- **Requisitos afectados en su cobertura:** RF-311–RF-314 pendientes de datos reales.
- **Actualizaciones aplicadas a `00-plan-general.md`:** Estado y riesgos.
- **Actualizaciones aplicadas a `00-especificacion.md`:** Ninguna.
- **Pendientes trasladados:** Tareas 6 y 7.
