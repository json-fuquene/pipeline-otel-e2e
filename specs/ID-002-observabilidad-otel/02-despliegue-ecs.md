# ID-002 — Fase 2: Despliegue mínimo en ECS Fargate

## Identificación

| Campo | Detalle |
|---|---|
| Plan | ID-002 — Observabilidad OpenTelemetry de catálogo y pedidos. |
| Fase | 2 — Collector y despliegue ECS |
| Estado | Implementada sin validar |
| Requisitos | RF-009–RF-017, RNF-005–RNF-007 |
| Dependencias | Fase 1; cuenta AWS, Terraform, Docker y permiso para escribir en el repositorio de infraestructura. |
| Región | `us-east-1` |

## Objetivo

Desplegar un entorno efímero que permita probar el pipeline completo en una tarea ECS Fargate: dos APIs, PostgreSQL, migraciones, OTel Collector, Jaeger y Prometheus. El Collector recibirá OTLP/gRPC y OTLP/HTTP; enviará trazas a Jaeger, métricas a Prometheus y logs estructurados a CloudWatch Logs.

## Diseño

```mermaid
flowchart LR
  U[Cliente de pruebas] -->|8001 / 8002| A[APIs]
  A -->|localhost:5432| DB[(PostgreSQL)]
  A -->|OTLP 4317 / 4318| C[OTel Collector]
  A -->|9464 / 9465| P[Prometheus]
  C -->|traces| J[Jaeger en memoria]
  C -->|metrics :8889| P
  C -->|logs OTLP| W[CloudWatch Logs]
  U -->|16686| J
  U -->|9090| P
```

Fargate usa `awsvpc`; los contenedores de una tarea comparten `localhost`. Catálogo escucha en 8001 y pedidos en 8002. Las migraciones arrancan después de que PostgreSQL está saludable; las APIs esperan migraciones exitosas, y pedidos espera catálogo. PostgreSQL y Jaeger no tienen volúmenes persistentes. El Collector scrapea los endpoints de métricas de ambas APIs; Prometheus scrapea la salida Prometheus del Collector.

Terraform crea una VPC con dos subredes públicas, Internet Gateway y sin NAT Gateway. La tarea recibe IP pública. El security group admite desde `allowed_cidr` solamente 8001, 8002, 4317, 4318, 16686 y 9090. PostgreSQL, métricas y la salud del Collector quedan accesibles solo dentro de la tarea. La variable no admite `0.0.0.0/0`.

Las credenciales se generan con `random_password`, quedan en Secrets Manager y se inyectan como campos JSON. El task execution role descarga imágenes, escribe logs de contenedor y lee el secreto. El task role tiene permisos de escritura limitados al log group de OTel. Los dos grupos CloudWatch retienen un día.

## Imágenes y configuración

| Imagen | Origen |
|---|---|
| `catalog`, `orders` | Dockerfiles existentes de los servicios. |
| `postgres` | `docker/postgres/Dockerfile`, incluye inicialización de roles/esquemas. |
| `otel-collector` | Collector Contrib 0.162.0 con `docker/otel-collector/ecs.yaml`. |
| `jaeger` | Jaeger 2.22.0 con almacenamiento en memoria y UI. |
| `prometheus` | Prometheus 3.13.3 LTS; scrapea la salida del Collector. |

Terraform crea un ECR por imagen con tags inmutables. `scripts/push-ecs-images.py` construye y publica los tags con contexto en la raíz del proyecto. El root IaC está en [`infra/otel-ecs-lab`](../../infra/otel-ecs-lab/README.md), y sus módulos compartidos en `infra/tf_modules`.

## Tareas

| Estado | Tarea | Criterio |
|---|---|---|
| [x] | Configurar OTLP/gRPC + HTTP, processors y pipelines locales. | Collector local acepta OTLP y deja las tres señales en `debug`. |
| [x] | Exportar logs JSON de cada API mediante OTel Logs además de stdout. | Los eventos del middleware se envían por OTLP y conservan contexto trace/span. |
| [x] | Crear Collector ECS, Jaeger, Prometheus y configuración de PostgreSQL. | Los contenedores auxiliares tienen versiones fijadas y config versionada. |
| [x] | Crear root Terraform, permisos, ECR, red y tarea Fargate. | Manifiestos definen los recursos mínimos y `allowed_cidr` obligatorio. |
| [x] | Documentar publicación, smoke test y limpieza. | README Terraform tiene los pasos reproducibles. |
| [x] | Formatear los manifiestos Terraform. | `terraform fmt -check -recursive` termina correctamente. |
| [ ] | Inicializar providers y validar el plan local de Terraform. | `terraform init -backend=false` y `terraform validate` terminan correctamente. |
| [x] | Publicar imágenes y aplicar en una cuenta de prueba. | Tag inmutable `phase2-test-4` publicado; rollout ECS completado y tarea activa. |
| [ ] | Verificar trazas, métricas y logs extremo a extremo. | Jaeger, Prometheus y CloudWatch muestran eventos del test. |
| [ ] | Destruir el laboratorio. | No queda servicio ECS ejecutándose. |

## Procedimiento de prueba

1. Configurar `allowed_cidr` con el CIDR público que ejecutará las pruebas; usar el archivo `terraform.tfvars.example` como base.
2. Inicializar Terraform y aplicar el target `aws_ecr_repository.images` para crear ECR.
3. Ejecutar `scripts/push-ecs-images.py`, que autentica Docker en ECR y publica las imágenes.
4. Aplicar Terraform. Revisar estado de contenedores y logs de las migraciones antes de llamar a las APIs.
5. Crear un producto en `:8001`, crear pedido en `:8002`, y verificar el mismo `trace_id` en Jaeger.
6. Consultar en Prometheus las series scrapeadas desde los endpoints internos `/metrics` de ambas APIs.
7. Verificar CloudWatch `/pipeline-otel/ecs-test` y eventos JSON correlacionados.
8. Ejecutar `terraform destroy` al finalizar.

La URL/IP pública se obtiene desde el attachment de red de la tarea ECS. No se crea balanceador para esta prueba.

## Validación registrada

Terraform se aplicó y ECS completó el rollout de la revisión 4. Las seis imágenes `catalog`, `orders`, `postgres`, `otel-collector`, `jaeger` y `prometheus` se construyeron y publicaron en ECR con el tag inmutable `phase2-test-4`. La consulta de ECS confirmó `desired=1`, `running=1`, `pending=0` y `rollout=COMPLETED`; PostgreSQL, catálogo y pedidos reportaron `HEALTHY`, Jaeger, Collector y Prometheus quedaron `RUNNING`, y las dos migraciones terminaron con código 0.

La prueba de arranque confirma que ECS ya no falla por imagen ausente y que la tarea inicia. No se han registrado aún consultas end-to-end a Jaeger, Prometheus y CloudWatch ni la destrucción del laboratorio; permanecen para esta fase y el cierre del plan. En los logs del Collector aparece `failed to convert metric up: duplicate label names ... pipeline_up`; este error debe quedar visible en las evidencias de observabilidad y no se considera resuelto por el estado `RUNNING`.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| PostgreSQL/Jaeger efímeros | Usar solo datos de prueba; destruir al finalizar. |
| Task pública | Restringir cada puerto expuesto a `allowed_cidr`; ninguna regla permite el CIDR global. |
| Estado Terraform contiene contraseñas | Mantener estado local protegido y borrarlo al destruir la prueba. |
| Consumo limitado de memoria | La tarea de fase 2 usa 1 vCPU y 2 GiB; Grafana requiere revisar el tamaño y la capacidad libre en la fase 3. |
| Imagen o config auxiliar inválida | Ejecutar build/arranque en Docker antes de aplicar y verificar estado ECS. |

## Cierre de fase

- Resultado: despliegue aplicado y rollout comprobado; validación end-to-end de señales y destrucción pendientes.
- Las APIs están saludables, los backends están en ejecución y las migraciones finalizaron correctamente.
- El Gate 3 permanece abierto hasta confirmar las consultas funcionales y actualizar la cobertura con evidencia.
