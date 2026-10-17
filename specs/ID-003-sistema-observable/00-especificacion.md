# ID-003 — Especificación: sistema observable integrado en AWS

## Identificación

| Campo | Detalle |
|---|---|
| ID | ID-003 |
| Título | Sistema observable completo: tercer microservicio, AIOps, red y seguridad, caos controlado y madurez. |
| Origen | Actividad 3.3 registrada en [`fases.md`](../../fases.md) (Módulos A–E). |
| Sprint / iteración | No documentado. |
| Estado de la especificación | Aprobada para implementación; la validación funcional en AWS está pendiente. |
| Iniciativas relacionadas | ID-001 (servicios y contratos), ID-002 (instrumentación OTel, Collector, Jaeger, Prometheus, Grafana). |

## Problema

ID-002 dejó dos servicios instrumentados en una sola tarea ECS con un PostgreSQL efímero. No existe acceso a una base gestionada, observabilidad de red L7 entre servicios, detección automática de anomalías, correlación de alertas con trazas, observabilidad de seguridad ni una forma repetible de validar la resiliencia y el tiempo de detección (MTTD).

## Resultado esperado

Tres microservicios (catálogo, pedidos y data-service) se ejecutan como servicios ECS independientes conectados por ECS Service Connect; data-service persiste en Amazon RDS y emite spans DB con convenciones semánticas estables. Las alertas combinan detección de anomalías (baseline + 2σ) con el SLO de latencia y llegan enriquecidas con el `trace_id` de una solicitud fallida. VPC Flow Logs, Security Hub e Inspector alimentan un dashboard de Golden Signals de Seguridad. Dos experimentos de caos validan MTTD ≤ 2 min, el consumo de error budget y la accionabilidad de la alerta. Un reporte de madurez cierra con un roadmap a 3 meses.

## Actores y sistemas involucrados

| Actor o sistema | Rol en el flujo | Qué cambia para él |
|---|---|---|
| Catálogo (`catalog`) | Servicio HTTP con esquema `catalog`; destino del experimento de latencia (service-b). | Se ejecuta como servicio ECS propio, usa RDS con TLS y admite inyección de caos. |
| Pedidos (`orders`) | Punto de entrada; llama a catálogo y a data-service. | Registra cada pedido en data-service y expone `GET /orders/summary`. |
| data-service | Nuevo servicio interno con esquema `data` en RDS. | Registro idempotente de pedidos y reporte agregado; spans DB semconv. |
| Amazon RDS for PostgreSQL | Base gestionada privada. | Reemplaza al PostgreSQL efímero en AWS; un rol y esquema por servicio. |
| ECS Service Connect | Malla L7 administrada (proxy Envoy por tarea). | Resuelve nombres y publica métricas por destino en `AWS/ECS`. |
| OTel Collector, Jaeger, Prometheus, Grafana | Servicio ECS de observabilidad. | Recibe OTLP por Service Connect, agrega `servicegraph` y nuevos dashboards. |
| CloudWatch (Logs, métricas, alarmas) | SLIs derivados de logs OTel, anomalías y alarmas compuestas. | Núcleo del Módulo B. |
| Lambda enriquecedora y SNS | Enriquecen y entregan alertas. | Adjuntan `trace_id`, evidencia y runbook. |
| DevOps Guru | Análisis ML sobre data-service y RDS. | Insights complementarios en el tópico enriquecido. |
| VPC Flow Logs, Security Hub CSPM, Inspector, EventBridge | Señales de red y seguridad. | Módulo C. |
| Equipo (operador del laboratorio) | Ejecuta carga, experimentos y reportes. | Usa scripts reproducibles y guarda evidencia en `artifacts/`. |

## Requisitos funcionales

| Id | Requisito | Criterio de aceptación | Prioridad |
|---|---|---|---|
| RF-301 | data-service registra y consulta eventos de pedido. | `POST /records` responde 201 al crear y 200 al repetir el mismo `order_id`; `GET /records/{id}` y `GET /reports/summary` responden con el contrato descrito en la fase 1. | Obligatorio |
| RF-302 | Las operaciones de base de datos de data-service emiten spans CLIENT con OTel DB Semantic Conventions estables. | Cada sentencia produce un span con `db.system.name=postgresql`, `db.namespace=pipeline\|data`, `db.collection.name`, `db.operation.name`, `db.query.summary` (también nombre del span), `db.query.text` parametrizado, `server.address`/`server.port`; en error, `error.type` y `db.response.status_code` (SQLSTATE). Se publica el histograma `db.client.operation.duration`. | Obligatorio |
| RF-303 | data-service emite los tres pilares. | Trazas OTLP con spans `data.record.create` y `data.report.summary`, métricas Prometheus en `:9466/metrics` y logs JSON con `request_id`, `trace_id` y `span_id` exportados por OTLP. | Obligatorio |
| RF-304 | Pedidos integra data-service sin alterar su contrato. | `POST /orders` conserva respuesta y códigos; registra el pedido en data-service en la misma traza y, si falla, solo registra el evento `data_record_failed` y la métrica `orders.data_record.failures`. `GET /orders/summary` devuelve el reporte de data-service. | Obligatorio |
| RF-305 | Los tres servicios se comunican por una malla L7 con métricas por destino. | Servicios ECS separados con Service Connect; `AWS/ECS` publica `RequestCount`, `HTTPCode_Target_5XX_Count` y `TargetResponseTime` para `catalog` y `data-service`. | Obligatorio |
| RF-306 | Los servicios usan Amazon RDS privado con TLS y aislamiento por esquema. | RDS sin acceso público, `rds.force_ssl=1`, un rol `*_app` y esquema propio por servicio creados de forma idempotente antes de las migraciones. | Obligatorio |
| RF-307 | El Collector deriva el grafo de servicios de las trazas. | Prometheus contiene `pipeline_traces_service_graph_request_total` con aristas orders→catalog, orders→data-service y servicio→postgresql. | Deseable |
| RF-311 | Cada servicio tiene SLIs de solicitudes, errores 5xx y latencia con percentiles en CloudWatch. | `PipelineOtel/Services` publica `RequestCount`, `ServerErrorCount` y `RequestLatency` (p99) por dimensión `service`, excluyendo rutas de salud. | Obligatorio |
| RF-312 | La detección de anomalías cubre data-service. | Alarmas con `ANOMALY_DETECTION_BAND(·, 2)` sobre tasa de error y p99 por servicio; DevOps Guru analiza data-service y RDS por etiqueta y notifica al tópico enriquecido. | Obligatorio |
| RF-313 | La regla de correlación genera una alerta enriquecida. | Cuando `error_rate > baseline + 2σ` **y** `latency_p99 > SLO`, la alarma compuesta dispara la Lambda, que publica una alerta con `primary_trace_id` de una solicitud 5xx, evidencia y runbook. | Obligatorio |
| RF-314 | Se demuestra la reducción de alertas ruidosas. | Un reporte compara, en la misma ventana, notificaciones de umbrales estáticos frente a la regla AIOps (historial real y reproducción offline) con porcentaje de reducción. | Obligatorio |
| RF-321 | VPC Flow Logs alimentan métricas y alertas de tráfico anómalo. | Métricas `RejectedFlows`, `AcceptedBytes` y `EastWestBytes`; alarma de rechazos y alarma de anomalía 2σ sobre tráfico este-oeste con acciones al enriquecedor. | Obligatorio |
| RF-322 | La observabilidad de seguridad usa Security Hub e Inspector. | Security Hub CSPM con estándar FSBP; Inspector escanea imágenes ECR; los hallazgos HIGH/CRITICAL/MEDIUM llegan a CloudWatch Logs y generan alarma; una Lambda publica CVEs activos por severidad. | Obligatorio |
| RF-323 | Existe el dashboard «Golden Signals de Seguridad». | Grafana muestra intentos de autenticación fallidos, tráfico N-S/E-W, flujos rechazados, CVEs activos y últimos hallazgos. | Obligatorio |
| RF-324 | Los intentos de autenticación fallidos son medibles y alertables. | Logins inválidos en Grafana incrementan `FailedAuthAttempts`; 5 o más en 5 min disparan alarma de seguridad. | Obligatorio |
| RF-331 | La inyección de fallas se controla en caliente por servicio. | Un parámetro SSM por servicio activa latencia, tasa de error y retardo de error en ≤ 5 s sin redesplegar; cada cambio genera `chaos_config_changed` y los spans afectados llevan eventos `chaos.*`. Las rutas de salud nunca fallan. | Obligatorio |
| RF-332 | Se ejecutan los dos experimentos definidos. | Exp. 1: +200 ms en catalog. Exp. 2: 10 % de errores en data-service. Ambos con carga constante, reversión automática y evidencia en `artifacts/chaos/`. | Obligatorio |
| RF-333 | El sistema detecta y alerta en menos de 2 minutos. | MTTD = transición a ALARM de la alarma primaria − instante de inyección ≤ 120 s en ambos experimentos. | Obligatorio |
| RF-334 | Cada experimento documenta SLO, error budget y accionabilidad. | El reporte responde si se degradó el SLO, cuánto presupuesto (ventana y mensual) se consumió y si la alerta incluyó un `trace_id` utilizable. | Obligatorio |
| RF-341 | Se autoevalúa la madurez en 8 dominios con escala 1–5. | Tabla con nivel, evidencia y brecha por dominio. | Obligatorio |
| RF-342 | Se propone un roadmap de 3 meses. | Iniciativas por mes con dominio, resultado esperado e indicador. | Obligatorio |
| RF-351 | El repositorio queda publicable como entrega. | Repositorio público con IaC, código y scripts, y etiqueta de versión final `v1.0`. | Obligatorio |
| RF-352 | Se presentan evidencias para video y reporte ejecutivo. | Lista de evidencias de la fase 5 completa; el PDF de 10 páginas y el video se elaboran a partir de ellas. | Obligatorio |

## Requisitos no funcionales

| Id | Categoría | Requisito | Criterio de aceptación |
|---|---|---|---|
| RNF-301 | Compatibilidad | Los contratos de ID-001 se mantienen; los cambios son aditivos. | Las rutas y códigos existentes no cambian; `/orders/summary` y el registro en data-service son nuevos. |
| RNF-302 | Seguridad | Sin secretos versionados, privilegio mínimo y exposición acotada. | Contraseñas en Secrets Manager (RDS gestiona la maestra); roles de tarea separados para aplicaciones y observabilidad; entrada solo desde `allowed_cidr`; data-service y RDS sin entrada pública. |
| RNF-303 | Costo y limpieza | El laboratorio es efímero. | `terraform destroy` elimina todo; `desired_count = 0` detiene cómputo; RDS sin respaldos ni snapshot final. |
| RNF-304 | Reproducibilidad | Versiones e imágenes fijadas. | Tags ECR inmutables; dashboards generados por `scripts/grafana/build_dashboards.py`; Collector contrib 0.162.0. |
| RNF-305 | Seguridad del caos | Los experimentos solo afectan al sandbox y siempre se revierten. | El runner revierte en `finally`; salud excluida; parámetros con prefijo del laboratorio. |
| RNF-306 | Privacidad de telemetría | No se exportan cuerpos ni valores literales de consultas. | `db.query.text` parametrizado; URL sin query en spans HTTP. |
| RNF-307 | Operación local | Compose sigue funcionando con tres servicios. | `docker compose up -d --build --wait` levanta data-service con bootstrap idempotente aun con un volumen previo. |

## Casos y comportamiento esperado

| Id | Caso | Condición de entrada | Comportamiento esperado |
|---|---|---|---|
| C-301 | Pedido completo | `POST /orders` válido. | Traza única: orders → catalog → PostgreSQL y orders → data-service → `INSERT data.order_records`. |
| C-302 | Registro repetido | `POST /records` con `order_id` existente. | 200 con el registro original; no se duplica. |
| C-303 | data-service caído | Pedido válido con data-service no disponible. | Pedido 201; log `data_record_failed` y métrica de fallos. |
| C-304 | Resumen | `GET /orders/summary?window_minutes=60`. | 200 con totales y top de productos; 503/504 con código estable si data-service falla. |
| C-305 | Error SQL | Sentencia rechazada por PostgreSQL. | Span DB con `error.type` y `db.response.status_code` = SQLSTATE; respuesta 503 `database_unavailable`. |
| C-306 | Exp. 1 | Parámetro de catalog con `latency_ms=200`. | `catalog-latency-degradation` en ALARM ≤ 120 s; alerta enriquecida con trazas más lentas. |
| C-307 | Exp. 2 | Parámetro de data-service con `error_rate=0.1`, `error_delay_ms=500`. | `data-service-correlated-errors` en ALARM ≤ 120 s con `primary_trace_id` de un 503. |
| C-308 | Reversión | Fin del experimento o interrupción del runner. | Parámetro `{"enabled": false}`; alarmas vuelven a OK. |
| C-309 | Login inválido repetido | 8 logins inválidos en Grafana. | `FailedAuthAttempts` ≥ 5 y alarma de seguridad enriquecida. |
| C-310 | Sondeo de puertos | Conexiones a puertos no publicados. | Flujos REJECT visibles en panel y alarma si superan el umbral. |
| C-311 | Hallazgo HIGH | Inspector o FSBP genera un hallazgo HIGH/CRITICAL. | Evento en `/aws/events/pipeline-otel-obs/security-findings` y alarma de seguridad. |

## Supuestos

| Verificado | Id | Supuesto | Impacto si resulta falso |
|---|---|---|---|
| Sí, por respuesta de alcance del 2026-10-16 | S-301 | Solo AWS se despliega y valida; GCP queda como IaC de referencia no aplicada. | La rúbrica «ambas clouds» queda parcial; habría que aplicar `infra/gcp-observable`. |
| Sí, documentación AWS | S-302 | AWS App Mesh dejó de tener soporte el 30-09-2026; ECS Service Connect es la alternativa recomendada. | Si se exigiera App Mesh no sería desplegable. |
| Sí, documentación AWS | S-303 | DevOps Guru deja de aceptar clientes nuevos el 29-10-2026 y funciona hasta el 30-09-2027. | Si la cuenta no se habilita antes, el Módulo B se apoya solo en CloudWatch anomaly detection. |
| Sí, documentación AWS | S-304 | Las métricas de metric filters admiten percentiles; las de Service Connect solo cuentan tráfico desde tareas del namespace y `TargetResponseTime` no documenta percentiles. | Cambiaría la fuente del SLI de latencia. |
| Hipótesis | S-305 | Tres horas de tráfico estable bastan para una banda de anomalía utilizable; CloudWatch recomienda más historial. | Bandas anchas o ruidosas; aumentar la línea base o el ancho de banda. |
| Hipótesis | S-306 | «service-b» del enunciado corresponde a catalog (servicio llamado por pedidos). | Cambiar el servicio objetivo del experimento 1. |

## Fuera de alcance

- Despliegue y validación en GCP (Cloud SQL, Cloud Service Mesh, Security Command Center).
- Alta disponibilidad, multi-AZ, NAT, balanceadores, WAF y respaldos de RDS.
- CloudTrail, autenticación en las APIs y respuesta automática a incidentes (auto-remediación).
- Persistencia de trazas y métricas más allá de la vida de las tareas.
- Elaboración del PDF ejecutivo y del video (se basan en las evidencias de la fase 5).

## Aclaraciones pendientes

| Estado | Id | Pregunta | Bloquea a |
|---|---|---|---|
| Abierta | A-301 | ¿Cuáles son los 8 dominios oficiales del «Observability Foundation Blueprint» del curso? Se usa una propuesta provisional en la fase 5. | Cierre de RF-341 (no bloquea la implementación). |
| Abierta | A-302 | ¿Nombre del tercer integrante del grupo para el reporte? | Reporte ejecutivo. |
| Resuelta → D-301 | A-303 | ¿Se despliega GCP? | Ninguna fase. |

## Bitácora de decisiones

| Id | Decisión | Alternativas consideradas | Motivo | Origen |
|---|---|---|---|---|
| D-301 | Desplegar y validar solo en AWS; GCP como IaC de referencia en `infra/gcp-observable`. | AWS + GCP completo; AWS + GCP mínimo. | Alcance confirmado; reduce costo y tiempo. | Respuesta de alcance, 2026-10-16. |
| D-302 | Malla L7 con ECS Service Connect. | AWS App Mesh; Istio en EKS; VPC Lattice. | App Mesh sin soporte desde 30-09-2026; Service Connect no requiere plano de control propio y publica métricas por destino. | Documentación AWS. |
| D-303 | Un servicio ECS por microservicio y uno de observabilidad. | Una sola tarea como en ID-002. | Service Connect y la frontera de DevOps Guru requieren servicios separados. | Diseño fase 1. |
| D-304 | Una instancia RDS con esquema y rol por servicio; contenedor `db-bootstrap` idempotente con el secreto maestro gestionado por RDS. | Tres instancias; proveedor Terraform `postgresql`. | Menor costo; el proveedor exigiría alcanzar RDS desde fuera de la VPC. | Diseño fase 1. |
| D-305 | SLIs de alarmas desde metric filters sobre los logs OTel en CloudWatch. | Prometheus/AMP; EMF; métricas de Service Connect. | Percentiles soportados y mismo origen que la evidencia `trace_id`; EMF no conserva percentiles; Service Connect solo cuenta tráfico interno. | Documentación AWS. |
| D-306 | CloudWatch anomaly detection (banda 2σ) como detector primario y DevOps Guru como complemento. | Solo DevOps Guru. | La banda implementa literalmente baseline + 2σ y evalúa por minuto; DevOps Guru tarda horas en generar insights y cierra a clientes nuevos. | Diseño fase 2. |
| D-307 | Correlación con alarmas compuestas y Lambda que consulta Logs Insights para el `trace_id`. | Grafana Alerting; Step Functions. | Nativo, sin estado y auditable en el historial de alarmas. | Diseño fase 2. |
| D-308 | Caos a nivel de aplicación con parámetro SSM consultado cada 5 s. | AWS FIS (`aws:ecs:task-network-latency`); variable de entorno con redespliegue. | FIS no inyecta respuestas HTTP 5xx y en Fargate requiere configuración adicional; el redespliegue impide medir MTTD con precisión. | Diseño fase 4. |
| D-309 | Los errores inyectados esperan 500 ms antes del 503 (emulan timeout de BD). | Error inmediato. | Hace observable la condición de latencia de la regla correlacionada; con error inmediato solo dispararía la anomalía de error. | Diseño fase 4. |
| D-310 | `OTEL_SEMCONV_STABILITY_OPT_IN=http,database` en los tres servicios. | Solo data-service. | Convenciones DB homogéneas; los atributos `db.statement`/`db.name` pasan a `db.query.text`/`db.namespace` en catalog y orders. | Diseño fase 1. |
| D-311 | data-service solo recibe tráfico este-oeste; orders expone `/orders/summary`. | Publicar data-service. | Menor superficie y métricas de Service Connect completas para data-service. | Diseño fase 1. |
| D-312 | Golden Signals de Seguridad con logins fallidos de Grafana, VPC Flow Logs, Security Hub CSPM e Inspector. | CloudTrail; autenticación en APIs. | Grafana es la única superficie con login; CloudTrail queda fuera de alcance. | Diseño fase 3. |
| D-313 | Healthcheck ECS sobre `/health/live`. | `/health/ready`. | Con servicios separados, `ready` depende de otros servicios y provocaría reinicios en cascada. | Diseño fase 1. |
| D-314 | Conector `servicegraph` en el Collector. | Solo métricas de Service Connect. | Aporta aristas hacia PostgreSQL y funciona también en local. | Diseño fase 1. |
| D-315 | Dominios provisionales del blueprint (A-301). | Esperar la definición oficial. | Permite completar la autoevaluación y ajustarla después. | Fase 5. |

## Referencias

- [`fases.md`](../../fases.md), [`ID-002`](../ID-002-observabilidad-otel/00-especificacion.md) y [`infra/aws-observable/README.md`](../../infra/aws-observable/README.md).
- [AWS App Mesh — fin de soporte y migración](https://docs.aws.amazon.com/app-mesh/latest/userguide/what-is-app-mesh.html) y [ECS Service Connect — métricas](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/available-metrics.html), consultadas el 2026-10-16.
- [DevOps Guru — aviso de fin de soporte](https://docs.aws.amazon.com/devops-guru/latest/userguide/sns-required-permissions.html), consultado el 2026-10-16.
- [CloudWatch: anomaly detection sobre expresiones de metric math](https://aws.amazon.com/about-aws/whats-new/2021/11/amazon-cloudwatch-supports-anomaly-detection-metric-math-expressions/) y [percentiles en metric filters](https://aws.amazon.com/about-aws/whats-new/2019/05/cloudwatch-logs-adds-support-for-percentiles-in-metric-filters/).
- [OpenTelemetry — Database semantic conventions (PostgreSQL)](https://opentelemetry.io/docs/specs/semconv/database/postgresql/) y [métricas de cliente DB](https://opentelemetry.io/docs/specs/semconv/database/database-metrics/).
- [Security Hub — estándar FSBP](https://docs.aws.amazon.com/securityhub/latest/userguide/fsbp-standard.html) y [Amazon Inspector para ECR](https://docs.aws.amazon.com/inspector/latest/user/scanning-ecr.html).
