# ID-001 — Fase 2: API de catálogo

## Identificación

| Campo | Detalle |
|---|---|
| Plan | ID-001 — Catálogo y pedidos locales. |
| Fase | 2 — API de catálogo. |
| Estado | Implementada sin validar |
| Requisitos que cubre | RF-001, RF-002, RF-005, RF-006, RF-008, RF-009, RNF-003, RNF-005, RNF-006, RNF-007 |
| Sistemas y repositorios | API catálogo, pruebas unitarias y servicio Compose catalog. |
| Dependencias previas | Fase 1 implementada para acceso real a datos; diseño de fase 1 suficiente para empezar unitarias. |
| Habilita a | Validación HTTP real de fase 3 e integración de fase 4. |

## Objetivo

Catálogo crea y consulta productos, expone salud y devuelve respuestas y logs trazables con acceso exclusivo a sus datos.

## Contexto de la fase

Catálogo es el proveedor HTTP de pedidos. No depende de pedidos para servir productos ni comprobar disponibilidad. Se aplican la [especificación](00-especificacion.md), los contratos del [plan general](00-plan-general.md) y la [constitución](../CONSTITUCION.md). Esta fase puede implementarse usando esos documentos y el presente archivo.

## Alcance técnico

### Cambios previstos

| Ubicación | Cambio | Requisito asociado |
|---|---|---|
| `services/catalog/app/` | Rutas, contratos, servicio, repositorio, lifespan, errores y logs de catálogo. | RF-001, RF-002, RF-005, RF-006, RF-008, RF-009, RNF-003, RNF-005, RNF-006 |
| `services/catalog/tests/unit/` | Pruebas con repositorio/sesión sustituidos y sin PostgreSQL activo. | RNF-007 |
| `compose.yaml` | Añadir catalog con puerto, salud y dependencia de su migración. | RF-009 |

### No incluido en esta fase

- Crear pedidos o llamar a otro servicio: fase 3.
- Stock, actualización y eliminación de productos: fuera de alcance.

## Diseño

Implementar POST /products, GET /products y GET /products/{id} con los contratos exactos de Product del plan general. Validar nombre recortado de 1–200 caracteres y precio textual positivo hasta 9999999999.99, sin exponente, signo ni más de dos decimales. Rechazar campos extra. El precio se convierte a Decimal sin pasar por float; la respuesta usa texto con dos decimales. Solo se devuelve 201 tras confirmar la transacción.

Listar con limit por defecto 20 (1–100), offset no negativo y orden ascendente created_at/id. Recuperar un UUID válido ausente produce product_not_found 404; un UUID inválido o parámetros inválidos producen validation_error 422. JSON inválido y campos extra se normalizan al mismo sobre; el tipo de contenido incorrecto produce 415. Nombres iguales no generan conflicto.

Lifespan abre/cierra el motor; sesión por solicitud, transacción de escritura acotada y rollback ante fallos. SELECT 1 en readiness; liveness no usa la base. Vida devuelve status ok y service catalog; readiness devuelve ready/not_ready con checks.database up/down. Ante base caída, operaciones de datos devuelven database_unavailable 503; no se devuelve SQL ni excepción original.

Implementar middleware de X-Request-ID y logs JSON con los campos del plan general, también para 4xx/5xx. Evitar registrar cuerpos, valores de validación o credenciales. Documentar OpenAPI y errores. Las pruebas unitarias sustituyen repositorio/sesión y no usan SQLite como sustituto de PostgreSQL. Se permite implementar catálogo y pedidos en paralelo después de los contratos de fase 1; su validación real conserva dependencias.

### Comportamiento esperado por caso

| Caso | Condición | Resultado esperado |
|---|---|---|
| C-001 | Producto válido. | 201 y posteriores GET con mismo contenido. |
| C-003 | Nombre en blanco, precio 0, negativo, exceso de decimales, campos extra o JSON inválido. | 422 sin escritura; tipo de contenido incorrecto: 415. |
| C-004 | UUID desconocido o mal formado. | 404 o 422 respectivamente. |
| C-008/C-009 | Base detenida/restablecida. | Datos y ready: 503/200; live permanece 200. |
| C-014 | Colección vacía o paginada. | items vacío o página ordenada y acotada. |
| C-015/C-016 | Cabecera inválida o dos POST iguales. | UUID generado y propagado; dos productos distintos. |

## Tareas

Las tareas siguen el orden listado salvo las marcadas `[P]`, que pueden realizarse en paralelo después de sus prerrequisitos. La marca no exige usar agentes paralelos.

| Estado | # | Tarea | Criterio de aceptación |
|---|---|---|---|
| [x] | 1 | Implementar contratos de entrada/salida y validación decimal. | Límites y normalización documentados en OpenAPI. |
| [x] | 2 | Implementar repositorio y transacciones contra catalog.products. | Crear, listar y consultar sin acceder a orders. |
| [x] | 3 | `[P]` Implementar salud y lifespan. | Live sin DB; ready con SELECT 1. |
| [x] | 4 | `[P]` Implementar sobre de errores, correlación y log JSON. | Respuestas 4xx/5xx y logs respetan el contrato sin valores sensibles. |
| [x] | 5 | Añadir comando Uvicorn y servicio Compose catalog. | Comando Uvicorn y publicación 127.0.0.1:8001 configurados. |
| [ ] | 6 | Añadir unitarias con dobles para repositorio, validación y respuestas. | Los escenarios de aceptación quedan automatizados sin PostgreSQL. |
| [x] | 7 | Actualizar estado y cobertura documental según el código presente. | La fase queda Implementada sin validar hasta obtener evidencia. |

## Validación

Los comandos son procedimientos previstos, aún no ejecutados. Se ejecutan desde la raíz. Las pruebas unitarias usan dobles de dependencias; los procedimientos con servicios reales son validación funcional y requieren confirmación.

| Estado | Tipo | Qué verifica | Cómo se ejecuta | Resultado esperado |
|---|---|---|---|---|
| Pendiente | Automatizada | RF-001/RF-002: creación y lectura; C-014/C-016. | `python3 -m pytest services/catalog/tests/unit -k products` | 201/200, UUID distintos, listas vacías, orden y límites. |
| Pendiente | Automatizada | RF-005/RF-006/RNF-005: rechazos y dinero. | `python3 -m pytest services/catalog/tests/unit -k validation` | 422/404/415 correctos; valores decimales exactos. |
| Pendiente | Automatizada | RF-008/RF-009/RNF-003: fallos, salud, logs y correlación. | `python3 -m pytest services/catalog/tests/unit -k health_and_errors` | 503 con base simulada caída; live 200; sin fugas. |
| Pendiente | Automatizada | RNF-006/RNF-007: esquema y todas las unitarias. | `python3 -m pytest services/catalog/tests/unit` | Incluye OpenAPI para rutas y modelos; todas pasan sin DB real. |
| Pendiente | Estática | RNF-007. | `python3 -m ruff check services/catalog`; `python3 -m compileall -q services/catalog` | Salida 0. |
| Pendiente de confirmación | Funcional / operativa | RF-001/RF-002/RF-009: integración real. | Procedimiento siguiente. | Crear/consultar y salud 200. |

### Procedimiento funcional de catálogo

```sh
docker compose up -d --build --wait catalog
curl -fsS http://localhost:8001/health/live
curl -fsS http://localhost:8001/health/ready
curl -fsS http://localhost:8001/openapi.json
product_json=$(curl -fsS -X POST http://localhost:8001/products -H 'Content-Type: application/json' -d '{"name":"Cuaderno","price":"12.50"}')
product_id=$(printf '%s' "$product_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
curl -fsS "http://localhost:8001/products/$product_id"
curl -fsS 'http://localhost:8001/products?limit=20&offset=0'
```

Esperado: POST devuelve 201 (confirmar también el estado con `curl -i` si se registra manualmente), GET 200 y precio textual 12.50. `curl -fsS` detecta fallos HTTP pero no comprueba por sí solo el código exacto; registrar los códigos observados. Las pruebas de caída, recuperación y correlación completas figuran en fase 4. Los nombres de prueba deben contener los fragmentos usados por `pytest -k`; una selección sin pruebas ejecutadas no valida el requisito.


## Reversión y compatibilidad

Los contratos son nuevos. Detener el entorno con `docker compose down` conserva el volumen. No ejecutar downgrade ni reset sobre datos que deban conservarse. El procedimiento destructivo explícito figura en fase 4.

## Riesgos y bloqueantes de la fase

| Estado | Elemento | Impacto | Mitigación o siguiente acción |
|---|---|---|---|
| Abierto | Dependencias directas fijadas aún no se instalaron en este entorno. | Medio | Confirmar la resolución del entorno durante validación; las versiones están fijadas. |
| Abierto | Entorno real pendiente. | Medio | Confirmar acceso a PostgreSQL y migración durante la fase 4. |

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
