# ID-001 — Fase 4: Operación local y validación integral

## Identificación

| Campo | Detalle |
|---|---|
| Plan | ID-001 — Catálogo y pedidos locales. |
| Fase | 4 — Operación local y validación integral. |
| Estado | Implementada sin validar |
| Requisitos que cubre | RF-009, RF-010, RF-011, RF-012, RNF-001, RNF-002, RNF-003, RNF-006, RNF-007, RNF-008 |
| Sistemas y repositorios | Compose completo, Dockerfiles, guía local y evidencias de integración. |
| Dependencias previas | Fases 1, 2 y 3 implementadas; Docker/Compose, Python 3, curl y red disponibles. |
| Habilita a | Cierre del plan solo tras confirmación de todas las validaciones y Gate 4. |

## Objetivo

El conjunto arranca con un procedimiento local reproducible, conserva datos y cuenta con evidencia registrada de integración y recuperación.

## Contexto de la fase

Las pruebas unitarias no comprueban arranque, permisos reales ni persistencia. Esta fase reúne los componentes y mantiene separada la confirmación funcional exigida por la guía. Se aplican la [especificación](00-especificacion.md), los contratos del [plan general](00-plan-general.md) y la [constitución](../CONSTITUCION.md). Esta fase puede implementarse usando esos documentos y el presente archivo.

## Alcance técnico

### Cambios previstos

| Ubicación | Cambio | Requisito asociado |
|---|---|---|
| `compose.yaml` y Dockerfiles de ambos servicios | Completar dependencias de salud/migración, puertos loopback y recursos mínimos por servicio. | RF-009, RF-011, RNF-001, RNF-002 |
| `README.md` | Prerrequisitos, comandos exactos, ejemplos, diagnóstico, límites y reset explícito. | RF-010, RNF-001, RNF-006 |
| Pruebas de servicios y scripts | Completar comprobaciones estáticas/unitarias y registrar resultados. | RNF-007 |
| Documentos de fases y plan | Registrar evidencia real, permisos y matriz final; completar informe solo al cierre. | RF-012, RNF-003, RNF-008 |

### No incluido en esta fase

- Cloud, CI/CD, Kubernetes, TLS, OpenTelemetry y configuración productiva.
- Reset automático o carga de datos de ejemplo al iniciar.

## Diseño

Revisar el Compose incremental con los cinco servicios previstos: postgres, catalog-migrate, orders-migrate, catalog y orders. Aplicar exactamente el grafo de salud y finalización del plan general, sin dependencias circulares. Las APIs usan la misma dirección interna de PostgreSQL pero reciben solo su contraseña, y pedidos recibe CATALOG_BASE_URL. No publicar la base ni montar .env en las APIs. Los comandos Uvicorn escuchan internamente en 8000, con las publicaciones 127.0.0.1:8001/8002.

Documentar un camino de inicio desde cero: generar .env, validar Compose sin imprimir configuración, construir y arrancar con --wait. El README debe permitir ejecutar todos los ejemplos sin instalar dependencias Python de aplicación; solo el generador local requiere Python 3 estándar. Las pruebas de desarrollo sí requieren requirements-dev.txt en un entorno de desarrollo separado.

Registrar comandos, fechas, códigos HTTP y resultados observados sin contraseñas. Las fases anteriores conservan las validaciones pendientes hasta confirmación explícita. `docker compose config --quiet` evita mostrar variables resueltas; no adjuntar .env ni salida completa de inspect/config a la evidencia.

El procedimiento siguiente comprueba fallos de conectividad y recuperación reales. Timeout y respuestas inválidas de catálogo se comprueban con los dobles HTTP en las unitarias de fase 3, sin añadir proxies o servicios de fallo al Compose. La separación de permisos se comprueba con los comandos SQL de esta fase. La persistencia se verifica con down/up sin opción -v; el reset destructivo se documenta y se ejecuta solo si se desea descartar todos los datos locales.

### Comportamiento esperado por caso

| Caso | Condición | Resultado esperado |
|---|---|---|
| C-002/C-013/C-015 | Flujo HTTP con correlación y dinero. | Pedido 201, total exacto y mismo UUID en ambos servicios. |
| C-005/C-008/C-009 | Detener catálogo o PostgreSQL y recuperarlos. | Errores acordados y recuperación sin recrear APIs. |
| C-010/C-012 | down/up con volumen y migraciones repetidas. | Mismos IDs y contenido, sin duplicados. |
| C-011 | Acceso con roles distintos. | Cada rol opera solo en su esquema. |
| C-017 | Variables obligatorias ausentes. | Configuración falla sin usar secretos por defecto. |

## Tareas

Las tareas siguen el orden listado salvo las marcadas `[P]`, que pueden realizarse en paralelo después de sus prerrequisitos. La marca no exige usar agentes paralelos.

| Estado | # | Tarea | Criterio de aceptación |
|---|---|---|---|
| [x] | 1 | Completar Compose, contextos y healthchecks según plan general. | Cinco servicios con dependencias y puertos acordados. |
| [x] | 2 | `[P]` Escribir README con arranque, ejemplos, errores, apagado y reset. | Procedimiento ejecutable desde un entorno local limpio. |
| [x] | 3 | `[P]` Revisar secretos, imports, dependencias fijadas y contratos OpenAPI. | Sin secretos ni importaciones cruzadas de repositorios/modelos. |
| [ ] | 4 | Ejecutar validaciones automatizadas y estáticas apropiadas. | Pruebas y estilo aprobados, sin casos omitidos por selecciones vacías. |
| [ ] | 5 | Registrar confirmación de integración, permisos, persistencia y recuperación. | Códigos, datos y logs respaldan los requisitos asociados. |
| [x] | 6 | Registrar el estado actual de las cuatro fases y su cobertura; reservar Gate 4 para el cierre. | Estados y cobertura reflejan código presente con validación pendiente. |

## Validación

Los comandos son procedimientos previstos, aún no ejecutados. Se ejecutan desde la raíz. Las pruebas unitarias usan dobles de dependencias; los procedimientos con servicios reales son validación funcional y requieren confirmación.

| Estado | Tipo | Qué verifica | Cómo se ejecuta | Resultado esperado |
|---|---|---|---|---|
| Pendiente | Automatizada | RNF-007 y cobertura de RF-001 a RF-009. | `python3 -m pip install -r requirements-dev.txt`; `python3 -m pytest tests/unit services/catalog/tests/unit services/orders/tests/unit` | Todas las pruebas pasan sin dependencias activas. |
| Pendiente | Estática | RNF-002/RNF-007: estilo y sintaxis. | `python3 -m ruff check services scripts`; `python3 -m compileall -q services scripts` | Salida 0. |
| Pendiente | Estática | RNF-001/RNF-002: Compose válido. | `docker compose config --quiet` | Salida 0 sin mostrar secretos. |
| Pendiente de confirmación | Funcional / operativa | RF-009/RF-010/RF-011/RNF-003/RNF-006/RNF-008. | Procedimientos A, B y C siguientes. | HTTP, logs, recuperación y persistencia correctos. |
| Pendiente de confirmación | Funcional / operativa | RF-012/RNF-002: permisos reales. | Procedimiento D. | Acceso ajeno denegado y acceso propio permitido. |
| Pendiente de confirmación | Reversión | RF-010: apagado no destructivo. | Procedimiento E, solo primera parte. | Volumen y configuración conservados. |

### A. Arranque y flujo principal

Los bloques A a C se ejecutan en la misma sesión de shell POSIX desde la raíz. Se usa un directorio temporal para respuestas sin credenciales. `set -eu` detiene el procedimiento ante un resultado inesperado; registrar el fallo antes de continuar. El procedimiento crea datos nuevos en cada ejecución; no requiere borrar registros existentes.

```sh
set -eu
python3 scripts/init-local-env.py
docker compose config --quiet
docker compose up -d --build --wait
docker compose ps -a
sdd_tmp=$(mktemp -d)
sdd_check() {
  sdd_expected="$1"
  shift
  sdd_code=$(curl -sS --max-time 20 -o "$sdd_tmp/response.json" -w '%{http_code}' "$@")
  test "$sdd_code" = "$sdd_expected"
}
sdd_check 200 http://localhost:8001/health/live
sdd_check 200 http://localhost:8001/health/ready
sdd_check 200 http://localhost:8002/health/live
sdd_check 200 http://localhost:8002/health/ready
sdd_check 200 http://localhost:8001/openapi.json
sdd_check 200 http://localhost:8002/openapi.json
sdd_check 201 -X POST http://localhost:8001/products -H 'Content-Type: application/json' -d '{"name":"Precisión decimal","price":"0.10"}'
sdd_product_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$sdd_tmp/response.json")
sdd_request_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
sdd_check 201 -D "$sdd_tmp/headers.txt" -X POST http://localhost:8002/orders -H 'Content-Type: application/json' -H "X-Request-ID: $sdd_request_id" -d "{\"product_id\":\"$sdd_product_id\",\"quantity\":3}"
cp "$sdd_tmp/response.json" "$sdd_tmp/order.json"
sdd_order_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$sdd_tmp/order.json")
python3 - "$sdd_tmp/order.json" "$sdd_product_id" <<'CHECK'
import json, sys
with open(sys.argv[1]) as f:
    order = json.load(f)
assert order['product_id'] == sys.argv[2]
assert order['product_name'] == 'Precisión decimal'
assert order['unit_price'] == '0.10'
assert order['quantity'] == 3
assert order['total'] == '0.30'
CHECK
python3 - "$sdd_tmp/headers.txt" "$sdd_request_id" <<'CHECK'
import sys
from pathlib import Path
headers = Path(sys.argv[1]).read_text().lower().splitlines()
assert 'x-request-id: ' + sys.argv[2] in headers
CHECK
sdd_check 200 "http://localhost:8001/products/$sdd_product_id"
sdd_check 200 "http://localhost:8002/orders/$sdd_order_id"
sdd_check 200 'http://localhost:8001/products?limit=1&offset=0'
sdd_check 200 'http://localhost:8002/orders?limit=1&offset=0'
docker compose logs --no-log-prefix catalog orders
```

Confirmar en los logs JSON que el UUID de `sdd_request_id` aparece en POST /orders y en GET /products/{id} del catálogo. Comprobar los campos obligatorios y la ausencia de contraseñas, cuerpos y URLs de conexión. Las tareas de migración deben figurar finalizadas con código 0; las APIs y PostgreSQL saludables. No se necesita que todos los contenedores estén en ejecución: las migraciones son tareas que terminan.

### B. Rechazos, caída de catálogo y recuperación

```sh
sdd_before=$(docker compose exec -T postgres psql -U postgres -d pipeline -Atc 'SELECT count(*) FROM orders.orders;')
sdd_check 422 -X POST http://localhost:8002/orders -H 'Content-Type: application/json' -d "{\"product_id\":\"$sdd_product_id\",\"quantity\":0}"
sdd_check 422 http://localhost:8001/products/not-a-uuid
sdd_unknown_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
sdd_check 404 -X POST http://localhost:8002/orders -H 'Content-Type: application/json' -d "{\"product_id\":\"$sdd_unknown_id\",\"quantity\":1}"
docker compose stop catalog
sdd_check 200 http://localhost:8002/health/live
sdd_check 503 http://localhost:8002/health/ready
sdd_check 200 "http://localhost:8002/orders/$sdd_order_id"
sdd_check 503 -X POST http://localhost:8002/orders -H 'Content-Type: application/json' -d "{\"product_id\":\"$sdd_product_id\",\"quantity\":1}"
python3 -c 'import json,sys; assert json.load(open(sys.argv[1]))["error"]["code"] == "catalog_unavailable"' "$sdd_tmp/response.json"
sdd_after=$(docker compose exec -T postgres psql -U postgres -d pipeline -Atc 'SELECT count(*) FROM orders.orders;')
test "$sdd_before" = "$sdd_after"
docker compose start catalog
docker compose up -d --wait catalog
sdd_check 200 http://localhost:8002/health/ready
```

Resultado: ninguno de los tres intentos fallidos crea pedidos; restaurar catálogo restablece readiness sin recrear pedidos. La comprobación con contador supone que no hay otro cliente creando pedidos durante el procedimiento. Las respuestas 502/504 y la ausencia de reintentos se confirman en las unitarias de fase 3; no se atribuyen a la detención de catálogo, que demuestra 503.

### C. Caída de base, recuperación y persistencia

```sh
docker compose stop postgres
sdd_check 200 http://localhost:8001/health/live
sdd_check 200 http://localhost:8002/health/live
sdd_check 503 http://localhost:8001/health/ready
sdd_check 503 http://localhost:8002/health/ready
sdd_check 503 "http://localhost:8001/products/$sdd_product_id"
sdd_check 503 "http://localhost:8002/orders/$sdd_order_id"
docker compose start postgres
docker compose up -d --wait postgres
sdd_check 200 http://localhost:8001/health/ready
sdd_check 200 http://localhost:8002/health/ready
sdd_check 200 "http://localhost:8002/orders/$sdd_order_id"
docker compose down
docker compose up -d --wait
sdd_check 200 "http://localhost:8001/products/$sdd_product_id"
sdd_check 200 "http://localhost:8002/orders/$sdd_order_id"
python3 - "$sdd_tmp/order.json" "$sdd_tmp/response.json" <<'CHECK'
import json, sys
with open(sys.argv[1]) as f:
    before = json.load(f)
with open(sys.argv[2]) as f:
    after = json.load(f)
assert before == after
CHECK
docker compose run --rm catalog-migrate
docker compose run --rm orders-migrate
sdd_check 200 "http://localhost:8002/orders/$sdd_order_id"
```

Resultado: las APIs recuperan conexiones sin recreación durante el fallo; el down/up posterior conserva todo el pedido, incluida fecha y dinero. Volver a aplicar migraciones no altera su contenido. Tras la última llamada, repetir la comparación de JSON anterior y comprobar también el producto por ID.

### D. Permisos y configuración

```sh
docker compose exec -T postgres psql -U catalog_app -d pipeline -c 'SELECT count(*) FROM catalog.products;'
docker compose exec -T postgres psql -U orders_app -d pipeline -c 'SELECT count(*) FROM orders.orders;'
```

Ambos comandos deben funcionar. Ejecutar individualmente los cuatro rechazos de fase 1, reproducidos aquí, esperando salida distinta de cero y un error de permisos, nunca un fallo de sintaxis o conexión:

```sh
docker compose exec -T postgres psql -U catalog_app -d pipeline -c 'SELECT * FROM orders.orders;'
docker compose exec -T postgres psql -U orders_app -d pipeline -c 'SELECT * FROM catalog.products;'
docker compose exec -T postgres psql -U catalog_app -d pipeline -c 'INSERT INTO orders.orders DEFAULT VALUES;'
docker compose exec -T postgres psql -U orders_app -d pipeline -c 'INSERT INTO catalog.products DEFAULT VALUES;'
```

Como el bloque A activó `set -e`, ejecutar estos rechazos en otra sesión o capturar cada salida con `if comando; then ...; else ...; fi`. No encadenarlos como si todos debieran tener éxito. No se verifica autenticación remota con estos comandos internos; la comprobación es de permisos del rol.

Comprobar manualmente que `compose.yaml` publica solo `127.0.0.1:8001:8000` y `127.0.0.1:8002:8000`, que postgres no contiene ports y que cada API recibe solo su credencial. Las pruebas de `tests/unit` verifican configuración vacía, no sobrescritura y permisos de .env sin tocar el archivo real. Nunca ejecutar el generador con intención de cambiar contraseñas sobre un volumen existente.

### E. Apagado y reset

Apagado habitual, sin borrar datos:

```sh
docker compose down
```

El volumen y `.env` se conservan. Para recuperar el entorno: `docker compose up -d --wait`.

**Reset destructivo opcional:** el siguiente comando elimina todos los productos, pedidos e historiales locales. Está fuera del smoke normal; usarlo solo con datos desechables y después de decidir descartarlos:

```sh
docker compose down -v
```

Conservar `.env` y arrancar con `docker compose up -d --build --wait` para reconstruir una base vacía con las mismas credenciales. Si se desea regenerar credenciales, hacerlo únicamente después de eliminar el volumen, retirando expresamente el `.env` anterior y ejecutando de nuevo el generador. No usar un downgrade de Alembic para apagar el entorno.

### Evidencia y Gate 4

Registrar por procedimiento fecha, comando, código de salida, códigos HTTP, IDs de recursos y resultado esperado/observado. No incorporar valores secretos. Si alguna validación no se ejecuta, mantenerla pendiente y la fase como Implementada sin validar cuando exista código. Solo tras completar todas las fases y revisar coherencia y trazabilidad se completa [el informe final](99-informe-final.md).


## Reversión y compatibilidad

Las APIs no tienen consumidores previos. El apagado normal conserva datos. El reset descrito en esta fase destruye todos los registros locales y se mantiene separado del procedimiento de persistencia.

## Riesgos y bloqueantes de la fase

| Estado | Elemento | Impacto | Mitigación o siguiente acción |
|---|---|---|---|
| Abierto | Docker y prerrequisitos aún no verificados. | Medio | Comprobar antes de declarar validación operativa. |
| Abierto | down -v elimina toda la base local. | Alto para datos locales | Mantener reset explícito y fuera del smoke normal. |
| Abierto | Healthcheck no reinicia automáticamente una aplicación unhealthy. | Medio | La aplicación recupera conexiones; comprobar solicitudes tras restaurar dependencias. |

## Cierre de la fase

Gate 3 registrado para la implementación del código y la actualización del plan. Las validaciones automatizadas y funcionales siguen pendientes; por ello el estado permanece `Implementada sin validar`.

- **Resultado obtenido:** Código y documentación de la fase implementados; validación pendiente.
- **Desviaciones respecto al diseño:** Las pruebas automatizadas previstas todavía no están implementadas ni ejecutadas.
- **Decisiones tomadas durante la fase:** Ninguna; decisiones previas en la especificación.
- **Requisitos afectados en su cobertura:** Implementación presente; todos los criterios quedan pendientes de validación.
- **Actualizaciones aplicadas a `00-plan-general.md`:** Fase y cobertura registradas como Implementada sin validar.
- **Actualizaciones aplicadas a `00-especificacion.md`:** No se alteraron requisitos durante la implementación.
- **Pendientes trasladados:** Pruebas automatizadas y confirmación funcional de esta fase; mantener el estado sin validar hasta registrar evidencia.

## Referencias

- [Especificación](00-especificacion.md), [plan general](00-plan-general.md) y [guía SDD](../GUIA-AGENTE.md).
- Las referencias oficiales verificadas el 2026-10-14 están en el plan general; se aplican las correspondientes a esta fase.
