# Catálogo y pedidos locales

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

## Game Day de latencia local

El [plan ID-003](specs/ID-003-gameday-caos-local/00-plan-general.md) diseña tres experimentos y proporciona un harness para ejecutar el de latencia. Su validación operativa está pendiente: las pruebas unitarias no demuestran capacidades del daemon ni recuperación real.

El laboratorio usa `compose.chaos.yaml`, un proyecto `chaos-<run-id>`, volumen propio y puertos dinámicos publicados solo en `127.0.0.1`. El runner requiere Python 3 en un entorno POSIX, como Linux, macOS o WSL, para sus bloqueos con `fcntl`. Las credenciales nuevas se conservan con permisos privados en `.chaos/<run-id>/env`, excluido del versionado y del contexto de build; no reutiliza `.env`. Solo admite Docker mediante socket Unix o named pipe local, y rechaza destinos SSH/TCP y named pipes remotos. El auxiliar añade `NET_ADMIN` exclusivamente al espacio de red de pedidos.

Pruebas unitarias rápidas, sin Docker ni solicitudes reales:

```sh
python3 -m unittest discover -s tests/chaos -p 'test_*.py'
```

Los siguientes pasos son manuales. La preparación construye imágenes y arranca servicios; puede requerir varios minutos y descargar dependencias. Confirmar previamente el destino Docker local y los accesos de descarga que correspondan. Usar un identificador nuevo para cada corrida, sin volver a preparar un volumen con credenciales distintas:

```sh
python3 scripts/chaos/run.py prepare --run-id ensayo-01
python3 scripts/chaos/run.py status --run-id ensayo-01
```

La ejecución tarda aproximadamente cuatro minutos más captura y drenaje: baseline 60 s, fallo hasta 60 s, drenaje 15 s y recuperación 60 s. Introduce 6000 ms por paquete únicamente en tráfico IPv4 TCP de pedidos hacia catálogo:8000. Las reglas rechazan configuraciones ajenas; el supervisor retira por TTL o pérdida de la renovación de diez segundos. El fallo del daemon o auxiliar requiere comprobar limpieza antes de reutilizar el laboratorio.

```sh
python3 scripts/chaos/run.py run --run-id ensayo-01
```

En otra terminal se puede retirar el fallo de inmediato y consultar el estado. La repetición de rollback es inocua:

```sh
python3 scripts/chaos/run.py rollback --run-id ensayo-01
python3 scripts/chaos/run.py status --run-id ensayo-01
```

Después de verificar limpieza, detener el proyecto conservando el volumen y los archivos de evidencia:

```sh
python3 scripts/chaos/run.py down --run-id ensayo-01
```

Se conservan metadatos saneados, eventos, solicitudes, UUID de pedidos antes/después y logs básicos en `artifacts/chaos/<run-id>/`, incluso ante abortos cuando la captura siga disponible. El estado `executed` indica que terminó la secuencia; la evaluación de la hipótesis sigue pendiente. La captura detallada de telemetría, el verificador de evidencia y el informe pertenecen a fases posteriores. Las capturas de pantalla son manuales y el PDF permanece diferido. No publicar `.chaos/` ni mostrar configuraciones interpoladas que contengan credenciales.

## Prueba de observabilidad en ECS

El laboratorio efímero en AWS ECS Fargate reúne Collector, Jaeger, Prometheus, Grafana y CloudWatch Logs. Los manifiestos Terraform están en [`infra/otel-ecs-lab`](infra/otel-ecs-lab/README.md), con módulos en `infra/tf_modules`; configura el CIDR permitido, publica las imágenes en ECR y sigue su guía para aplicar los cambios. Grafana escucha en el puerto 3000 y su contraseña inicial se almacena en Secrets Manager. PostgreSQL, Jaeger y los datos de interfaz son efímeros. La revisión 8, que contiene el ajuste del panel CPU de CloudWatch, está en rollout; confirma el estado del servicio y valida los seis paneles en Grafana después de completar el despliegue. El repositorio no aplica infraestructura automáticamente.
