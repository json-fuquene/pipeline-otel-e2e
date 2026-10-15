# Laboratorio ECS Fargate para las fases 2 y 3

El root está organizado en módulos compartidos en `../tf_modules`: `ecr` administra repositorios, `network` la VPC y el acceso, `foundation` los secretos, IAM y logs, y `ecs` el clúster, la tarea y el servicio. Los bloques `moved` conservan las direcciones del estado anterior al migrar los recursos al nuevo diseño. Crea siete repositorios ECR, una VPC con dos subredes públicas y sin NAT, un clúster/tarea/servicio Fargate, Secrets Manager, roles IAM acotados y grupos CloudWatch con retención de un día. Una tarea efímera aloja PostgreSQL, las migraciones, las APIs, OTel Collector, Jaeger, Prometheus y Grafana. PostgreSQL, Jaeger y los datos de interfaz de Grafana son temporales.

## Prerrequisitos

- Terraform 1.6+, AWS CLI configurado y permisos para crear los recursos descritos.
- Docker y acceso a ECR/Docker Hub.
- Un CIDR público de origen concreto; `0.0.0.0/0` no está permitido.

Ejecuta los comandos Terraform desde `infra/otel-ecs-lab` en la raíz del repositorio. Para la publicación actual, configura `image_tag = "phase3-test-4"` en `terraform.tfvars`. La revisión 8 de ECS está en rollout; no des por estable el servicio ni por validado el dashboard hasta confirmar el fin del rollout y revisar los seis paneles, incluido CPU, en la UI.

## Crear y publicar imágenes

Inicializa y aplica primero el target de ECR. Las imágenes deben publicarse antes de que ECS pueda iniciar correctamente:

```sh
cp terraform.tfvars.example terraform.tfvars
# Ajusta allowed_cidr e image_tag en terraform.tfvars
terraform init
terraform apply -target='module.ecr.aws_ecr_repository.images["grafana"]'
```

Para construir y subir las imágenes:

```sh
REGION=us-east-1
terraform output -json ecr_urls > /tmp/pipeline-otel-ecr-urls.json
python3 ../../scripts/push-ecs-images.py "$REGION" /tmp/pipeline-otel-ecr-urls.json phase3-test-4
```

Luego registra el resto de los recursos y la tarea:

```sh
terraform plan -out=/tmp/phase3.tfplan
terraform show -no-color /tmp/phase3.tfplan
# Aplica únicamente después de revisar el plan.
terraform apply /tmp/phase3.tfplan
```

La cuenta AWS debe tener conectividad de salida para que Docker descargue las imágenes base. El script autentica contra ECR, usa el root del repositorio como contexto y publica las siete imágenes; si cambias `image_tag`, pásalo como tercer argumento. Después revisa el plan antes de aplicar, porque se crea el secreto de Grafana, cambia la tarea Fargate a 3 GiB y se actualiza el grupo de seguridad para incluir el puerto 3000 únicamente desde `allowed_cidr`.

## Pruebas

Obtén la IP pública de la tarea en ECS y llama a:

- `http://IP:8001/health/ready` y `http://IP:8002/health/ready`.
- `http://IP:3000` (Grafana; la contraseña inicial está en el secreto `${name}/grafana` de Secrets Manager).
- `http://IP:16686` (Jaeger) y `http://IP:9090` (Prometheus).
- OTLP/gRPC y OTLP/HTTP en `IP:4317` y `IP:4318`.

Los endpoints de métricas de catálogo y pedidos (`9464` y `9465`) son internos a la tarea. Consulta sus series desde Prometheus.

Smoke funcional básico:

```sh
curl -sS -X POST "http://IP:8001/products" -H 'Content-Type: application/json' -d '{"name":"Cuaderno","price":"12.50"}'
# Usa el id devuelto en product_id:
curl -sS -X POST "http://IP:8002/orders" -H 'Content-Type: application/json' -d '{"product_id":"UUID_DEL_PRODUCTO","quantity":2}'
```

Luego busca la traza en Jaeger por el servicio `orders`, ejecuta una consulta PromQL en Prometheus y verifica los logs JSON del producto/pedido en CloudWatch.

El grupo `/pipeline-otel/ecs-test` recibe logs OTLP; `/ecs/pipeline-otel-test` recibe stdout/stderr de contenedores. Las credenciales aleatorias están en Secrets Manager y el estado local de Terraform contiene valores secretos: mantenerlo protegido.

## Limpieza

```sh
terraform destroy
```

`desired_count` por defecto es 1 para ejecutar el smoke test al aplicar. El despliegue no se ejecuta como parte del cambio de código.
