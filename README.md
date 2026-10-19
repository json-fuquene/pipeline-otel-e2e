# Catálogo, pedidos y data-service

Ejemplo de APIs independientes con FastAPI. La actividad 3.3 (ID-003) agrega `data-service` y el sistema observable completo en AWS; ver [Sistema observable (ID-003)](#sistema-observable-id-003).

## Entrega · Actividad 3.3

Sistema observable completo desplegado en AWS: tres microservicios instrumentados con OpenTelemetry, malla L7, AIOps con correlación, observabilidad de red y seguridad, experimentos de caos con MTTD y reporte de madurez.

**Autores**

- Santiago López Amaya · santiagoloam@unisabana.edu.co
- Jeisson Alejandro Fúquene Buitrago · jeissonfubu@unisabana.edu.co

Maestría en Arquitectura de Software · Observabilidad en ambientes productivos · Universidad de La Sabana · Profesora: María Ochoa

| Entregable | Ubicación |
|---|---|
| Reporte ejecutivo (PDF, 10 páginas) | [`docs/actividad-3.3/Informe_Actividad_3.3.pdf`](docs/actividad-3.3/Informe_Actividad_3.3.pdf) |
| Diagramas de arquitectura (Mermaid) | [`docs/actividad-3.3/arquitectura-observable.md`](docs/actividad-3.3/arquitectura-observable.md) |
| Evidencias (capturas) | [`docs/actividad-3.3/evidencias/`](docs/actividad-3.3/evidencias/) |
| Resultados de los experimentos de caos | [`artifacts/chaos/`](artifacts/chaos/) |
| Especificación y fases (SDD) | [`specs/ID-003-sistema-observable/`](specs/ID-003-sistema-observable/00-especificacion.md) |

### Infraestructura como código

| Componente | Ruta |
|---|---|
| Composición del entorno AWS (Terraform) | [`infra/aws-observable/`](infra/aws-observable/README.md) |
| Red: VPC, subredes, security groups y VPC Flow Logs | [`infra/tf_modules/vpc-observable/`](infra/tf_modules/vpc-observable/) |
| Base de datos: Amazon RDS PostgreSQL con TLS obligatorio | [`infra/tf_modules/rds/`](infra/tf_modules/rds/) |
| Cómputo: ECS Fargate, ECS Service Connect (malla L7) y parámetros SSM de caos | [`infra/tf_modules/ecs-observable/`](infra/tf_modules/ecs-observable/) |
| AIOps: metric filters, bandas 2σ, alarmas compuestas, SNS, Lambda y DevOps Guru | [`infra/tf_modules/aiops/`](infra/tf_modules/aiops/) |
| Seguridad: Security Hub, Inspector, EventBridge y Golden Signals | [`infra/tf_modules/security-observability/`](infra/tf_modules/security-observability/) |
| Repositorios de imágenes | [`infra/tf_modules/ecr/`](infra/tf_modules/ecr/) |
| Funciones Lambda (alerta enriquecida con `trace_id`, métricas de CVEs) | [`infra/lambda/`](infra/lambda/) |

### Código de instrumentación

| Componente | Ruta |
|---|---|
| Servicios `catalog`, `orders` y `data-service` (OTel SDK: trazas, métricas y logs con `trace_id`) | [`services/`](services/) |
| Convenciones semánticas de base de datos estables y spans DB | [`services/data/app/db_semconv.py`](services/data/app/db_semconv.py) |
| Middleware de inyección de fallas (latencia y errores vía SSM) | [`services/shared/chaos.py`](services/shared/chaos.py) |
| Pruebas automatizadas (caos, DB semconv, AIOps) | [`tests/`](tests/) |

### Configuraciones

| Componente | Ruta |
|---|---|
| OpenTelemetry Collector (`servicegraph`, exportador a CloudWatch Logs) | [`docker/otel-collector/ecs-observable.yaml`](docker/otel-collector/ecs-observable.yaml) |
| Prometheus y reglas SLI/SLO (error budget, burn rate) | [`docker/prometheus/`](docker/prometheus/) |
| Grafana: datasources y dashboards (Servicios y SLO, AIOps, Red L7, Golden Signals de Seguridad) | [`docker/grafana/`](docker/grafana/) |
| Entorno local con Compose | [`compose.yaml`](compose.yaml) |

### Scripts

| Script | Uso |
|---|---|
| [`scripts/push-ecs-images.py`](scripts/push-ecs-images.py) | Construye y publica las imágenes en ECR (`--profile observable`). |
| [`scripts/aws/endpoints.py`](scripts/aws/endpoints.py) | Obtiene las URLs públicas de servicios, Grafana, Jaeger y Prometheus. |
| [`scripts/load/steady.js`](scripts/load/steady.js) | Carga constante con k6 para la línea base. |
| [`scripts/chaos/run_experiment.py`](scripts/chaos/run_experiment.py) | Ejecuta los experimentos (`exp1-latency-catalog`, `exp2-errors-data`), mide MTTD, SLO y error budget, y revierte la falla. |
| [`scripts/aiops/noise_report.py`](scripts/aiops/noise_report.py) | Compara notificaciones de umbrales estáticos frente a la regla correlacionada. |
| [`scripts/security/generate_security_signals.py`](scripts/security/generate_security_signals.py) | Genera logins fallidos y sondeo de puertos para validar las alertas de seguridad. |
| [`scripts/grafana/build_dashboards.py`](scripts/grafana/build_dashboards.py) | Genera los dashboards de Grafana como código. |

### Resultados

| Experimento | Falla | Primera alarma (MTTD) | SLO |
|---|---|---|---|
| 1 · catalog | +200 ms de latencia | `catalog-p99-slo` en 61,5 s | p99 de 48,5 ms → 249,5 ms (SLO 150 ms) |
| 2 · data-service | 10 % de errores 503 | `data-service-static-error-rate` en 69,6 s | Disponibilidad de 100 % → 89,86 % (SLO 99 %) |

Ambos experimentos cumplen el objetivo de MTTD ≤ 2 minutos. El análisis de error budget, la autoevaluación de madurez en 8 dominios y el roadmap a 3 meses están en el reporte ejecutivo.

### Reproducir

```sh
cd infra/aws-observable
cp terraform.tfvars.example terraform.tfvars          # ajustar allowed_cidr (IP propia /32)
terraform init
terraform apply -target=module.ecr                    # 1) solo repositorios
mkdir -p ../../artifacts/aws
terraform output -json ecr_urls > ../../artifacts/aws/ecr_urls.json
cd ../..
python3 scripts/push-ecs-images.py us-east-1 artifacts/aws/ecr_urls.json obs-v1 --profile observable
terraform -chdir=infra/aws-observable apply           # 2) red, RDS, ECS, AIOps, seguridad
terraform -chdir=infra/aws-observable output -json lab_config > artifacts/aws/lab_config.json
python3 scripts/aws/endpoints.py artifacts/aws/lab_config.json
python3 scripts/chaos/run_experiment.py exp1-latency-catalog --config artifacts/aws/lab_config.json --prometheus http://IP:9090
python3 scripts/chaos/run_experiment.py exp2-errors-data --config artifacts/aws/lab_config.json --prometheus http://IP:9090
terraform -chdir=infra/aws-observable destroy         # limpieza
```

La guía completa está en [`infra/aws-observable/README.md`](infra/aws-observable/README.md).

Ejemplo de dos APIs independientes con FastAPI. Catálogo administra productos; pedidos valida cada producto por HTTP y conserva una copia de sus datos. Ambos servicios escriben en esquemas PostgreSQL propios.

## Requisitos

- Docker Engine o Docker Desktop con Docker Compose v2.
- Python 3 para generar las credenciales locales.
- Puertos locales 8001, 8002, 9464 y 9465 disponibles.

## Inicio

Desde la raíz del repositorio:

```sh
python3 scripts/init-local-env.py
docker compose up -d --build --wait
docker compose ps -a
```

El primer arranque descarga las imágenes, crea la base `pipeline`, genera los roles y esquemas, aplica las migraciones y espera a que las APIs estén disponibles. El archivo `.env` se crea con permisos privados y no se muestra por consola. Si ya existe, el generador termina sin sobrescribirlo. No regenerar credenciales mientras se conserve el volumen PostgreSQL.

Las APIs se publican en `http://localhost:8001` (catálogo) y `http://localhost:8002` (pedidos). PostgreSQL y el receptor OTLP del Collector no publican puertos al host. La documentación OpenAPI está disponible en `/docs` para cada API.

## Métricas y trazas

Las métricas HTTP en formato Prometheus se exponen en `http://localhost:9464/metrics` (catálogo) y `http://localhost:9465/metrics` (pedidos). Las trazas se envían por OTLP/gRPC al Collector de Compose y su exportador `debug` permite inspeccionarlas:

```sh
docker compose logs -f otel-collector
```

Crear un producto o un pedido genera spans de HTTP, PostgreSQL y negocio. La traza del pedido cruza la llamada HTTP a catálogo. Los logs JSON conservan `request_id` e incluyen `trace_id` y `span_id` cuando hay un span activo. Healthchecks no se exportan como spans. El Collector local no persiste trazas ni ofrece una interfaz de búsqueda.

## Crear y consultar un producto

```sh
curl -i -X POST http://localhost:8001/products \
  -H 'Content-Type: application/json' \
  -d '{"name":"Cuaderno","price":"12.50"}'
```

La respuesta `201` incluye `id`, `name`, `price` como texto decimal y `created_at` UTC. Con el UUID devuelto:

```sh
curl -i http://localhost:8001/products/UUID
curl -i 'http://localhost:8001/products?limit=20&offset=0'
```

Los listados devuelven `items`, `limit` y `offset`; el límite por defecto es 20 y el máximo 100.

## Crear y consultar un pedido

Reemplaza `UUID_DEL_PRODUCTO` por el identificador del producto creado:

```sh
curl -i -X POST http://localhost:8002/orders \
  -H 'Content-Type: application/json' \
  -d '{"product_id":"UUID_DEL_PRODUCTO","quantity":2}'
```

Pedidos consulta catálogo antes de escribir. La respuesta `201` contiene el UUID y la copia del nombre y precio del producto, la cantidad, el total con dos posiciones decimales y la fecha UTC. Con el UUID del pedido:

```sh
curl -i http://localhost:8002/orders/UUID_DEL_PEDIDO
curl -i 'http://localhost:8002/orders?limit=20&offset=0'
```

Cada POST válido crea un recurso nuevo. Repetirlo puede crear un producto o pedido adicional.

## Salud, errores y logs

Ambas APIs exponen `/health/live` y `/health/ready`. Liveness comprueba el proceso; readiness comprueba PostgreSQL y, en pedidos, también catálogo. Las respuestas incluyen `X-Request-ID`; enviar un UUID válido permite correlacionar el log de pedidos con la llamada al catálogo.

Los errores tienen un código estable en `error.code`: validación `422`, recurso ausente `404`, catálogo no disponible `503`, timeout `504`, respuesta de catálogo inválida `502` y base de datos no disponible `503`. Un error de catálogo no guarda el pedido. Los logs JSON no deben contener contraseñas, cuerpos de solicitudes ni URLs de conexión.

```sh
docker compose logs -f catalog orders
```

## Detener y conservar datos

```sh
docker compose down
docker compose up -d --wait
```

El apagado normal conserva el volumen y `.env`. Las credenciales del volumen se establecen al inicializar PostgreSQL. Cambiar `.env` por sí solo no rota las contraseñas existentes.

## Borrar todos los datos locales

Este comando elimina productos, pedidos y el historial de migraciones del volumen:

```sh
docker compose down -v
```

Para comenzar de nuevo se puede conservar `.env` y arrancar con `docker compose up -d --build --wait`. El reinicio de contraseñas requiere eliminar primero el volumen y el `.env`, y generar un archivo nuevo con `python3 scripts/init-local-env.py`.

## Implementación y validación

La arquitectura, los contratos, criterios de aceptación y fases de servicios están descritos en [`specs/ID-001-microservicios-locales/`](specs/ID-001-microservicios-locales/). La instrumentación y sus criterios se describen en [`specs/ID-002-observabilidad-otel/`](specs/ID-002-observabilidad-otel/).

## Prueba de observabilidad en ECS

El laboratorio efímero en AWS ECS Fargate reúne Collector, Jaeger, Prometheus, Grafana y CloudWatch Logs. Los manifiestos Terraform están en [`infra/otel-ecs-lab`](infra/otel-ecs-lab/README.md), con módulos en `infra/tf_modules`; configura el CIDR permitido, publica las imágenes en ECR y sigue su guía para aplicar los cambios. Grafana escucha en el puerto 3000 y su contraseña inicial se almacena en Secrets Manager. PostgreSQL, Jaeger y los datos de interfaz son efímeros. La revisión 8, que contiene el ajuste del panel CPU de CloudWatch, está en rollout; confirma el estado del servicio y valida los seis paneles en Grafana después de completar el despliegue. El repositorio no aplica infraestructura automáticamente.

## Sistema observable (ID-003)

`data-service` (puerto local `8003`, métricas `9466`) registra cada pedido y calcula reportes; pedidos lo consulta en `GET /orders/summary`. En Compose se inicializa su rol con `data-bootstrap` aun sobre un volumen existente; si `.env` proviene de ID-002, `python3 scripts/init-local-env.py` agrega solo `DATA_DB_PASSWORD`.

Caos local (opcional): `CATALOG_CHAOS_LATENCY_MS=200 docker compose up -d` o `DATA_CHAOS_ERROR_RATE=0.1 DATA_CHAOS_ERROR_DELAY_MS=500 docker compose up -d`.

Pruebas: `pip install -r requirements-dev.txt && python3 -m pytest -q` (la integración con PostgreSQL se activa con `TEST_DATA_DB_PASSWORD`).

Despliegue AWS, carga, experimentos de caos, reporte de ruido y limpieza: [`infra/aws-observable/README.md`](infra/aws-observable/README.md). Especificación: [`specs/ID-003-sistema-observable/`](specs/ID-003-sistema-observable/00-especificacion.md).
