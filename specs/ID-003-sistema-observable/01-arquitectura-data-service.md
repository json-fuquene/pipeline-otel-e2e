# ID-003 — Fase 1: Arquitectura observable y data-service

> Se implementa leyendo este documento, [`00-especificacion.md`](00-especificacion.md) y [`00-plan-general.md`](00-plan-general.md). El cierre sigue el Gate 3 de [`GUIA-AGENTE.md`](../GUIA-AGENTE.md).

## Identificación

| Campo | Detalle |
|---|---|
| Plan | ID-003 — Sistema observable integrado en AWS. |
| Fase | 1 — Arquitectura observable y data-service (Módulo A). |
| Estado | Implementada sin validar |
| Requisitos que cubre | RF-301–RF-307, RNF-301, RNF-302, RNF-304, RNF-306, RNF-307 |
| Sistemas y repositorios | `services/data`, `services/orders`, `services/catalog`, `services/shared`, `compose.yaml`, `docker/postgres`, `docker/otel-collector`, `infra/aws-observable`, `infra/tf_modules/{vpc-observable,rds,ecs-observable}`, `infra/gcp-observable`. |
| Dependencias previas | ID-001 e ID-002. |
| Habilita a | Fases 2, 3 y 4. |

## Objetivo

Tres microservicios instrumentados con OTel se ejecutan como servicios ECS separados conectados por ECS Service Connect, con data-service persistiendo en Amazon RDS y emitiendo spans DB con convenciones semánticas estables.

## Alcance técnico

### Cambios previstos

| Ubicación | Cambio | Requisito asociado |
|---|---|---|
| `services/data/app/main.py` | API de registros y reporte; spans `data.record.create` y `data.report.summary`. | RF-301, RF-303 |
| `services/data/app/db_semconv.py` | Listeners SQLAlchemy que completan atributos DB estables y publican `db.client.operation.duration`. | RF-302 |
| `services/data/alembic/` | Tabla `data.order_records` con `order_id` único. | RF-301 |
| `services/orders/app/main.py`, `config.py` | Registro del pedido en data-service (mejor esfuerzo), `GET /orders/summary`, métrica `orders.data_record.failures`. | RF-304, RNF-301 |
| `services/*/app/config.py` | `DB_SSLMODE` opcional para RDS. | RF-306 |
| `docker/postgres/bootstrap-role.sh` | Rol y esquema idempotentes; compatible con usuario maestro no superusuario (PostgreSQL 16+). | RF-306, RNF-307 |
| `compose.yaml`, `scripts/init-local-env.py` | Servicios `data-bootstrap`, `data-migrate`, `data-service`; generador agrega claves faltantes. | RNF-307 |
| `docker/otel-collector/ecs-observable.yaml` | Scrape por alias Service Connect y conector `servicegraph`. | RF-303, RF-307 |
| `infra/tf_modules/vpc-observable` | VPC con subredes públicas (tareas) y privadas (RDS), SG N-S y E-W, VPC Flow Logs. | RF-305, RF-306, RNF-302 |
| `infra/tf_modules/rds` | PostgreSQL 17 privado, cifrado, `rds.force_ssl=1`, Performance Insights, secreto maestro gestionado. | RF-306 |
| `infra/tf_modules/ecs-observable` | Cluster, namespace Service Connect, tres servicios de aplicación y uno de observabilidad, roles separados. | RF-305, RNF-302 |
| `infra/gcp-observable` | Referencia Cloud Run + Cloud SQL, no aplicada (D-301). | — |

### No incluido en esta fase

- Alarmas y AIOps (fase 2); red y seguridad más allá de Flow Logs (fase 3); caos (fase 4).

## Diseño

### Contrato de data-service

| Método y ruta | Entrada | Respuesta |
|---|---|---|
| `POST /records` | `{order_id, product_id, quantity (1..1e6), total "NN.NN" > 0}` | 201 creado; 200 si el `order_id` ya existía; 422/415/503 con sobre de error. |
| `GET /records/{id}` | UUID | 200 o 404 `record_not_found`. |
| `GET /reports/summary` | `window_minutes` 1..10080, `limit` 1..20 | 200 `{window_minutes, orders, units, revenue, top_products[], database}`. |
| `GET /health/live`, `/health/ready` | — | Igual que ID-001; `ready` comprueba la base. |

### Atributos de los spans DB (RF-302)

| Atributo | Ejemplo | Origen |
|---|---|---|
| `db.system.name` | `postgresql` | Instrumentor (opt-in `database`) |
| `db.namespace` | `pipeline\|data` | Enriquecedor (patrón PostgreSQL) |
| `db.collection.name` | `data.order_records` | Enriquecedor |
| `db.operation.name` | `INSERT` | Enriquecedor |
| `db.query.summary` / nombre del span | `INSERT data.order_records` | Enriquecedor |
| `db.query.text` | sentencia parametrizada | Instrumentor |
| `server.address`, `server.port` | host RDS, `5432` | Instrumentor y enriquecedor |
| `error.type`, `db.response.status_code` | `23505` | Enriquecedor en `handle_error` |

El listener de error se registra antes del instrumentor (que cierra el span en `handle_error`) y los de ejecución después (para encontrar el span ya creado).

### Despliegue en ECS

Cada tarea de aplicación (0,5 vCPU / 1 GiB): `db-bootstrap` (imagen postgres, secreto maestro de RDS) → `migrate` (Alembic) → `app`. Puertos con nombre y `appProtocol=http` publicados en Service Connect como `catalog`, `orders`, `data-service` y `*-metrics`. La tarea de observabilidad (1 vCPU / 3 GiB) publica `otel-collector:4317` (`grpc`). Solo `catalog`, `orders`, Grafana, Jaeger y Prometheus aceptan entrada desde `allowed_cidr`.

### Comportamiento esperado por caso

| Caso | Condición | Resultado esperado |
|---|---|---|
| C-301 | Pedido válido | Una traza con orders, catalog, data-service y sus spans DB. |
| C-302 | `order_id` repetido | 200 con el registro original. |
| C-303 | data-service caído | Pedido 201 y `data_record_failed`. |
| C-304 | Resumen | 200 o 503/504 con `data_service_*`. |
| C-305 | Error SQL | `db.response.status_code` con SQLSTATE y 503. |

## Tareas

| Estado | # | Tarea | Criterio de aceptación |
|---|---|---|---|
| [x] | 1 | Implementar data-service, migración y enriquecedor DB. | Pruebas `tests/test_db_semconv.py` aprobadas, incluida integración PostgreSQL. |
| [x] | 2 | Integrar orders con data-service y `/orders/summary`. | Smoke local: pedidos 201 con data-service fallando al 30 %. |
| [x] | 3 | Bootstrap de roles compatible con RDS. | Probado con superusuario y con rol `CREATEROLE` no superusuario en PostgreSQL 16, dos ejecuciones idempotentes. |
| [x] | 4 | Compose con data-service. | YAML válido; servicios declarados. |
| [x] | 5 | IaC de red, RDS y ECS con Service Connect. | HCL analizado sin errores; variables de módulos coherentes. |
| [x] | 6 | Collector con alias Service Connect y `servicegraph`. | `otelcol-contrib validate` aprobado; aristas observadas en smoke local. |
| [ ] | 7 | `terraform validate/plan/apply` y trazas en Jaeger AWS. | Traza C-301 en Jaeger y métricas `AWS/ECS` de Service Connect. |
| [ ] | 8 | `docker compose up -d --build --wait` en el equipo local. | Los nueve servicios saludables o completados. |

## Validación

| Estado | Tipo | Qué verifica | Cómo se ejecuta | Resultado esperado |
|---|---|---|---|---|
| Aprobada | Automatizada | RF-301, RF-302, RF-303 | `TEST_DATA_DB_PASSWORD=… python3 -m pytest -q tests/test_db_semconv.py` | Span `INSERT data.order_records` con `db.namespace=pipeline\|data`. |
| Aprobada | Estática | Collector y HCL | `otelcol-contrib validate --config docker/otel-collector/ecs-observable.yaml`; `python-hcl2` | Sin errores. |
| Aprobada (entorno de desarrollo) | Funcional local | RF-304, RF-307 | Tres `uvicorn` + Collector + Prometheus locales | Pedidos 201, `request_id` común, `pipeline_traces_service_graph_request_total` con orders→catalog/data-service/postgresql. |
| Pendiente de confirmación | Funcional AWS | RF-305, RF-306 | Runbook `infra/aws-observable/README.md` | Tareas RUNNING, bootstrap `db_bootstrap_completed`, métricas Service Connect. |
| Pendiente | Reversión | RNF-303 | `terraform destroy` | Sin servicios ECS ni RDS. |

## Riesgos y bloqueantes de la fase

| Estado | Elemento | Impacto | Mitigación o siguiente acción |
|---|---|---|---|
| Abierto | IaC no validada con Terraform. | Alto | `terraform validate` antes de aplicar. |
| Abierto | La zona horaria de la base afecta la validación UTC de catálogo (observado con PostgreSQL local en zona no UTC). | Bajo | RDS y la imagen postgres usan UTC; no requiere cambio. |
| Abierto | Service Connect solo cuenta tráfico entre tareas del namespace. | Bajo | Los SLIs de alarmas salen de logs OTel (D-305). |

## Cierre de la fase

- **Resultado obtenido:** Implementado sin validar en AWS; validado en local.
- **Desviaciones respecto al diseño:** Ninguna.
- **Decisiones tomadas durante la fase:** D-302, D-303, D-304, D-310, D-311, D-313, D-314.
- **Requisitos afectados en su cobertura:** RF-305 y RF-306 pendientes de AWS.
- **Actualizaciones aplicadas a `00-plan-general.md`:** Estado y riesgos.
- **Actualizaciones aplicadas a `00-especificacion.md`:** Ninguna.
- **Pendientes trasladados:** Tareas 7 y 8 como pendientes abiertos del plan.
