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
