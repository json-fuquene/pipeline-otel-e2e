# ID-001 — Fase 3: API de pedidos y dependencia HTTP

## Identificación

| Campo | Detalle |
|---|---|
| Plan | ID-001 — Catálogo y pedidos locales. |
| Fase | 3 — API de pedidos y dependencia HTTP. |
| Estado | Implementada sin validar |
| Requisitos que cubre | RF-003, RF-004, RF-005, RF-006, RF-007, RF-008, RF-009, RNF-003, RNF-004, RNF-005, RNF-006, RNF-007 |
| Sistemas y repositorios | API pedidos, cliente HTTP de catálogo, pruebas y servicio Compose orders. |
| Dependencias previas | Fase 1 para persistencia; fase 2 implementada para validar integración HTTP real. |
| Habilita a | Integración y confirmación funcional de fase 4. |

## Objetivo

Pedidos crea registros solo después de validar un producto por HTTP y permite consultar los registros guardados sin depender de catálogo.

## Contexto de la fase

La conexión compartida no debe permitir saltarse el contrato HTTP. Las consultas de pedidos sobreviven a una caída de catálogo cuando la base sigue disponible. Se aplican la [especificación](00-especificacion.md), los contratos del [plan general](00-plan-general.md) y la [constitución](../CONSTITUCION.md). Esta fase puede implementarse usando esos documentos y el presente archivo.

## Alcance técnico

### Cambios previstos

| Ubicación | Cambio | Requisito asociado |
|---|---|---|
| `services/orders/app/` | Contratos, repositorio, cliente catálogo, rutas, salud, logs y errores. | RF-003 a RF-009, RNF-003 a RNF-006 |
| `services/orders/tests/unit/` | Dobles de repositorio y transporte HTTP; cobertura de fallos y cálculo. | RNF-007 |
| `compose.yaml` | Añadir orders dependiente de migración propia y salud de catálogo. | RF-009 |

### No incluido en esta fase

- Tablas de productos, consultas SQL a catalog y claves foráneas entre esquemas.
- Stock, pagos, reintentos, deduplicación o pedidos con múltiples productos.

## Diseño

Implementar exactamente POST /orders, GET /orders y GET /orders/{id} del plan general. Validar UUID y cantidad entera estricta 1–1000000, rechazando campos extra. Consultar producto con HTTPX AsyncClient reutilizado desde lifespan y validar Product, incluidos ID solicitado, nombre, fecha y precio válidos. No aceptar redirects; no reenviar a cliente cuerpos ni excepciones de upstream.

Configurar HTTPX con cinco segundos en cada tipo de timeout y envolver solicitud, lectura y validación en asyncio.timeout(5.0). No reintentar. Mapear 404 a product_not_found; transporte no timeout y 5xx a catalog_unavailable 503; cualquier timeout a catalog_timeout 504; resto de estados/JSON/esquema inválido a catalog_invalid_response 502.

No abrir transacción de DB antes de finalizar la llamada HTTP. Calcular Decimal(unit_price) * quantity, guardar copia de nombre/precio, generar UUID y fecha UTC, y confirmar una transacción propia. Los fallos previos a insertar no escriben; los de base producen 503 y rollback cuando es posible. Ante commit incierto, no reintentar ni prometer que no existe pedido. Dos POST válidos crean dos pedidos distintos.

GET de pedidos usa exclusivamente orders.orders. Readiness comprueba SELECT 1 y GET /health/ready de catálogo (plazo total dos segundos) y muestra ambos checks; liveness no usa dependencias. Un readiness negativo por catálogo no bloquea las rutas GET de pedidos en la aplicación. Correlación, logs, errores generales, paginación, dinero y OpenAPI siguen el plan general.

Pruebas de cliente usan HTTPX MockTransport o doble equivalente con contadores de llamadas; repositorio simulado verifica cero escrituras para cada fallo de catálogo y una escritura/confirmación en éxito. Simular tiempos con cancelación controlada sin esperar cinco segundos en cada prueba; comprobar además que los valores configurados y el plazo total corresponden a RNF-004.

### Comportamiento esperado por caso

| Caso | Condición | Resultado esperado |
|---|---|---|
| C-002/C-013 | Producto 12.50 × 2 o 0.10 × 3. | 201 con total 25.00 o 0.30 y copia del producto. |
| C-003/C-004 | Cantidad inválida, UUID inválido o producto ausente. | 422 o 404, sin escribir. |
| C-005/C-006/C-007 | Caída, timeout o respuesta inválida de catálogo. | 503/504/502; una tentativa HTTP y cero escrituras. |
| C-008/C-018 | Base caída o pérdida de confirmación. | 503 sin reintento; posible resultado incierto declarado. |
| C-009 | Restablecer dependencias. | Nuevas solicitudes funcionan sin recrear la API. |
| C-015/C-016 | Correlación y POST repetido. | UUID propagado; dos pedidos con IDs distintos. |

## Tareas

Las tareas siguen el orden listado salvo las marcadas `[P]`, que pueden realizarse en paralelo después de sus prerrequisitos. La marca no exige usar agentes paralelos.

| Estado | # | Tarea | Criterio de aceptación |
|---|---|---|---|
| [x] | 1 | Implementar contratos de pedido y validación de Product upstream. | Entradas y respuestas inválidas rechazadas antes de persistir. |
| [x] | 2 | Implementar cliente HTTP reutilizable, cancelación y mapeo de fallos. | Una tentativa; deadline total y errores acordados. |
| [x] | 3 | Implementar creación transaccional y rutas de lectura propias. | Copia de precio/nombre y total exacto; GET sin llamadas HTTP. |
| [x] | 4 | `[P]` Implementar salud, errores, logs y X-Request-ID. | Checks completos y correlación entre servicios. |
| [ ] | 5 | `[P]` Implementar unitarias de datos y fallos con dobles. | Cero escrituras para fallo HTTP y una para éxito. |
| [x] | 6 | Añadir servicio Compose orders. | Dependencias del servicio declaradas en Compose. |
| [x] | 7 | Actualizar estado y cobertura documental según el código presente. | La fase queda Implementada sin validar hasta obtener evidencia. |

## Validación

Los comandos son procedimientos previstos, aún no ejecutados. Se ejecutan desde la raíz. Las pruebas unitarias usan dobles de dependencias; los procedimientos con servicios reales son validación funcional y requieren confirmación.

| Estado | Tipo | Qué verifica | Cómo se ejecuta | Resultado esperado |
|---|---|---|---|---|
| Pendiente | Automatizada | RF-003/RF-004/RNF-005: creación, lecturas y Decimal. | `python3 -m pytest services/orders/tests/unit -k orders` | Snapshot correcto; GET sin catálogo; 0.10 × 3 = 0.30. |
| Pendiente | Automatizada | RF-005/RF-006: validación y ausencias. | `python3 -m pytest services/orders/tests/unit -k validation` | UUID/cantidad/campos inválidos: 422; ausencias: 404. |
| Pendiente | Automatizada | RF-007/RNF-004: fallos de catálogo y límite total. | `python3 -m pytest services/orders/tests/unit -k catalog_failure` | 503/504/502 según tabla; sin reintentos ni escrituras. |
| Pendiente | Automatizada | RF-008/RF-009/RNF-003: salud, recuperación y errores. | `python3 -m pytest services/orders/tests/unit -k health_and_errors` | Live 200; ready 503; GET disponible sin catálogo; logs correctos. |
| Pendiente | Automatizada | RNF-006/RNF-007: OpenAPI y conjunto unitario. | `python3 -m pytest services/orders/tests/unit` | Todas pasan sin PostgreSQL ni catálogo reales. |
| Pendiente | Estática | RNF-007. | `python3 -m ruff check services/orders`; `python3 -m compileall -q services/orders` | Salida 0. |
| Pendiente de confirmación | Funcional / operativa | RF-003/RF-004 y dependencia HTTP. | Procedimiento siguiente y fase 4. | Pedido persistido con datos del producto real. |

### Procedimiento funcional de pedidos

```sh
docker compose up -d --build --wait
product_json=$(curl -fsS -X POST http://localhost:8001/products -H 'Content-Type: application/json' -d '{"name":"Cuaderno","price":"12.50"}')
product_id=$(printf '%s' "$product_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
order_json=$(curl -fsS -X POST http://localhost:8002/orders -H 'Content-Type: application/json' -d "{\"product_id\":\"$product_id\",\"quantity\":2}")
order_id=$(printf '%s' "$order_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
printf '%s' "$order_json" | python3 -c 'import json,sys; o=json.load(sys.stdin); assert o["unit_price"]=="12.50" and o["total"]=="25.00" and o["quantity"]==2'
curl -fsS "http://localhost:8002/orders/$order_id"
curl -fsS http://localhost:8002/health/ready
```

Esperado: POST 201; GET y readiness 200. Registrar también códigos exactos, no solo la ausencia de fallo de curl. Las pruebas de selección `pytest -k` requieren nombres con esos fragmentos y al menos una prueba ejecutada por selección.


## Reversión y compatibilidad

Los contratos son nuevos. Detener el entorno con `docker compose down` conserva el volumen. No ejecutar downgrade ni reset sobre datos que deban conservarse. El procedimiento destructivo explícito figura en fase 4.

## Riesgos y bloqueantes de la fase

| Estado | Elemento | Impacto | Mitigación o siguiente acción |
|---|---|---|---|
| Abierto | Timeout por inactividad confundido con plazo total. | Medio | Configurar ambos y probar cancelación total. |
| Abierto | Commit incierto. | Medio | No reintentar; dejar limitación en documentación y respuesta 503. |
| Abierto | Catálogo puede no estar listo. | Medio | Dependencia de salud inicial y recuperación durante ejecución. |
| Abierto | Dependencias directas fijadas aún no se instalaron en este entorno. | Medio | Confirmar compatibilidad durante validación. |

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
