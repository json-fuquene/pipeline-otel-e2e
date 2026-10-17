# ID-003 — Fase 3: Observabilidad de red y seguridad

> Se implementa leyendo este documento, [`00-especificacion.md`](00-especificacion.md) y [`00-plan-general.md`](00-plan-general.md).

## Identificación

| Campo | Detalle |
|---|---|
| Plan | ID-003 — Sistema observable integrado en AWS. |
| Fase | 3 — Network and Security Observability (Módulo C). |
| Estado | Implementada sin validar |
| Requisitos que cubre | RF-321–RF-324 |
| Sistemas y repositorios | `infra/tf_modules/vpc-observable`, `infra/tf_modules/security-observability`, `infra/lambda/security_metrics`, `scripts/security`, dashboards `network.json` y `security.json`. |
| Dependencias previas | Fase 1 (VPC, logs ECS) y tópico SNS de la fase 2. |
| Habilita a | Fase 5 (evidencia). |

## Objetivo

VPC Flow Logs, Security Hub CSPM e Inspector alimentan métricas, alertas enriquecidas y el dashboard «Golden Signals de Seguridad».

## Diseño

### Red (RF-321)

- Flow Logs `ALL` de la VPC con agregación de 60 s y formato de 17 campos (v2 + `pkt-srcaddr`, `pkt-dstaddr`, `flow-direction`) en `/vpc/pipeline-otel-obs/flow-logs`.
- Filtros en `PipelineOtel/Network`: `RejectedFlows` (REJECT), `AcceptedBytes` (ACCEPT), `EastWestBytes` (origen y destino en `10.63.*`). Norte-sur = `AcceptedBytes − EastWestBytes` (expresión en Grafana). Cada flujo E-W se registra en ambas ENI; el volumen E-W está duplicado de forma consistente.
- Alarmas: `network-rejected-flows` (> 50 en 5 min) y `network-east-west-anomaly` (fuera de la banda 2σ, 2 de 3 minutos), ambas al enriquecedor, que adjunta los pares origen/destino/puerto principales.
- L7: métricas de Service Connect (`RequestCount`, `HTTPCode_Target_5XX_Count`, `TargetResponseTime`, `ActiveConnectionCount`) y el grafo `servicegraph` (fase 1).

### Seguridad (RF-322, RF-324)

- Security Hub CSPM con `control_finding_generator = SECURITY_CONTROL` y el estándar AWS Foundational Security Best Practices v1.0.0.
- Inspector para ECR: CVEs de las imágenes del laboratorio llegan a Security Hub.
- EventBridge envía hallazgos `ACTIVE` CRITICAL/HIGH/MEDIUM a `/aws/events/pipeline-otel-obs/security-findings`; un filtro cuenta HIGH/CRITICAL y dispara `security-high-findings`.
- Lambda programada cada 15 min publica `ActiveCVEs{severity}` y `ActiveFindings{severity}`.
- Logins inválidos de Grafana (`invalid username or password`, `password-auth.failed`) → `FailedAuthAttempts`; ≥ 5 en 5 min → `security-failed-auth`.
- GuardDuty opcional (`enable_guardduty`).

### Dashboard «Golden Signals de Seguridad» (RF-323)

| Señal | Panel | Fuente |
|---|---|---|
| Autenticación fallida | Stat 5 min y serie temporal | `FailedAuthAttempts` |
| Tráfico N-S / E-W | Serie bytes | `AcceptedBytes`, `EastWestBytes` |
| Tráfico rechazado | Stat y top orígenes | `RejectedFlows`, Logs Insights sobre Flow Logs |
| CVEs activos | Stat por severidad | `ActiveCVEs` |
| Postura | Barras por severidad y tabla de últimos hallazgos | `ActiveFindings`, log de hallazgos |

## Tareas

| Estado | # | Tarea | Criterio de aceptación |
|---|---|---|---|
| [x] | 1 | Flow Logs, filtros y alarmas de red. | HCL válido; patrón de 17 campos alineado con el formato. |
| [x] | 2 | Security Hub, FSBP, Inspector, EventBridge y alarmas de seguridad. | HCL válido; variables para cuentas con servicios ya habilitados. |
| [x] | 3 | Lambda de métricas de seguridad. | `tests/test_aiops.py::test_security_metrics_counts_cves_by_severity` aprobado. |
| [x] | 4 | Dashboards de red y seguridad. | 7 y 8 paneles generados. |
| [x] | 5 | Script de señales controladas (logins inválidos, sondeo de puertos). | Ayuda y validación de argumentos. |
| [ ] | 6 | Validar paneles con datos reales tras generar señales. | Paneles con valores no vacíos y alarmas en ALARM. |

## Validación

| Estado | Tipo | Qué verifica | Cómo se ejecuta | Resultado esperado |
|---|---|---|---|---|
| Aprobada | Automatizada | Conteo de CVEs | `pytest tests/test_aiops.py` | Aprobado. |
| Pendiente de confirmación | Funcional | RF-324 | `generate_security_signals.py --grafana http://IP:3000 --failed-logins 8` | `FailedAuthAttempts ≥ 5` y alerta. |
| Pendiente de confirmación | Funcional | RF-321 | `generate_security_signals.py --host IP --probe-ports` | `RejectedFlows` > 0 y top orígenes con la IP propia. |
| Pendiente de confirmación | Funcional | RF-322, RF-323 | Esperar el primer escaneo de Inspector y la ejecución de la Lambda | CVEs por severidad y tabla de hallazgos. |

## Riesgos y bloqueantes de la fase

| Estado | Elemento | Impacto | Mitigación o siguiente acción |
|---|---|---|---|
| Abierto | Security Hub/Inspector preexistentes en la cuenta. | Medio | Desactivar las variables correspondientes. |
| Abierto | Mensaje exacto del log de login fallido según versión de Grafana. | Medio | Verificar el texto en `/ecs/pipeline-otel-obs` y ajustar el filtro. |
| Abierto | La banda E-W necesita historial. | Medio | Misma línea base de la fase 2. |

## Cierre de la fase

- **Resultado obtenido:** Implementado sin validar en AWS.
- **Desviaciones respecto al diseño:** Norte-sur se calcula como diferencia en lugar de un filtro con negación.
- **Decisiones tomadas durante la fase:** D-312.
- **Requisitos afectados en su cobertura:** RF-321–RF-324 pendientes de datos reales.
- **Actualizaciones aplicadas a `00-plan-general.md`:** Estado.
- **Actualizaciones aplicadas a `00-especificacion.md`:** Ninguna.
- **Pendientes trasladados:** Tarea 6.
