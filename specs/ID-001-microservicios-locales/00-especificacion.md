# ID-001 — Especificación: catálogo y pedidos locales

## Identificación

| Campo | Detalle |
|---|---|
| ID | ID-001 |
| Título | Microservicios básicos de catálogo y pedidos con persistencia y dependencia HTTP. |
| Origen | Solicitud de dos servicios básicos, ambos consumidores de una base de datos y preparados para ejecución local. |
| Sprint / iteración | No documentado. |
| Estado de la especificación | Aprobada: alcance y plan acordados; generación documental solicitada el 2026-10-14. |
| Iniciativas relacionadas | ID-002 — agrega instrumentación OTel sin cambiar los contratos funcionales de estos servicios. |

## Problema

El repositorio contiene una plantilla documental, pero no un ejemplo ejecutable ni contratos para demostrar comunicación entre servicios y persistencia. Falta una definición verificable para construir y probar ese ejemplo en desarrollo local.

## Resultado esperado

Se pueden crear y consultar productos y pedidos en dos servicios locales. Crear un pedido obtiene información de un producto mediante HTTP antes de persistirlo; ambos servicios conservan datos propios en una base compartida y se inician con un procedimiento reproducible.

## Actores y sistemas involucrados

| Actor o sistema | Rol en el flujo | Qué cambia para él |
|---|---|---|
| Cliente local | Crea y consulta productos y pedidos. | APIs documentadas y ejemplos reproducibles. |
| Catálogo | Administra productos y responde consultas de pedidos. | Persistencia de productos e información consultable. |
| Pedidos | Valida el producto y registra su compra. | Consumo HTTP de catálogo y persistencia de pedidos. |
| Base compartida | Conserva datos de ambos servicios. | Accesos separados sin compartir propiedad de registros. |
| Entorno local | Arranca, comprueba y detiene el conjunto. | Conservación de datos y diagnóstico de fallos. |

## Requisitos funcionales

| Id | Requisito | Criterio de aceptación | Prioridad |
|---|---|---|---|
| RF-001 | Cuando se recibe un producto válido, catálogo lo crea. | 201 con identificador, nombre y precio; una consulta posterior recupera los mismos valores. | Obligatorio |
| RF-002 | Catálogo permite listar productos y consultar uno por identificador. | Base vacía devuelve lista vacía; producto existente se devuelve con 200. | Obligatorio |
| RF-003 | Crear un pedido consulta el producto mediante HTTP antes de guardar el pedido. | 201 y un pedido con producto, nombre y precio consultados, cantidad, total y fecha. | Obligatorio |
| RF-004 | Pedidos permite listar y consultar pedidos sin volver a consultar catálogo. | Se recuperan con 200 incluso si catálogo está detenido, mientras la base esté disponible. | Obligatorio |
| RF-005 | Las entradas inválidas se rechazan sin escribir datos. | Nombre vacío, precio no positivo o con exceso de decimales, cantidad no entera positiva o UUID mal formado producen 422. | Obligatorio |
| RF-006 | Los recursos inexistentes se informan como ausentes. | Consultar un UUID desconocido devuelve 404; crear pedido de producto ausente devuelve 404 sin persistirlo. | Obligatorio |
| RF-007 | Una dependencia de catálogo fallida impide crear el pedido. | Conexión rechazada o respuesta 5xx: 503; timeout: 504; respuesta inválida o inesperada: 502. Sin escritura. | Obligatorio |
| RF-008 | Un fallo de base de datos no publica un éxito. | Fallo de conexión o consulta devuelve 503; transacción fallida se revierte sin exponer detalles internos. | Obligatorio |
| RF-009 | Ambos servicios permiten comprobar vida y disponibilidad. | Vida: 200 sin dependencias; disponibilidad: 200 si están listas, 503 si fallan. Pedidos comprueba también catálogo. | Obligatorio |
| RF-010 | Los datos se conservan tras reinicio o apagado normal. | Se recuperan productos y pedidos previamente creados. | Obligatorio |
| RF-011 | El entorno inicializa almacenamiento y arranca APIs con prerrequisitos listos. | Arranque limpio ejecuta inicialización y migraciones; segundo arranque no duplica ni borra datos. | Obligatorio |
| RF-012 | Ambos servicios leen y escriben sus propios datos en la base compartida. | Su credencial permite operaciones propias y rechaza lectura y escritura del otro servicio. | Obligatorio |

## Requisitos no funcionales

| Id | Categoría | Requisito | Criterio de aceptación |
|---|---|---|---|
| RNF-001 | Operación | Ejecución local sin runtimes de aplicación fuera de contenedores, salvo Python 3 para generar configuración. | La guía permite configurar, construir y levantar con Docker Compose. |
| RNF-002 | Seguridad | Credenciales externas al código; solo las APIs publican puertos, en loopback. | Sin secretos en ejemplos o logs; base sin puerto publicado y APIs en 127.0.0.1. |
| RNF-003 | Observabilidad | Log JSON e identificador de solicitud propagado por HTTP. | Mismo identificador en respuesta, llamada HTTP y logs; servicio, método, ruta, estado y duración presentes. |
| RNF-004 | Resiliencia | Espera HTTP acotada y sin reintentos automáticos. | Cinco segundos para conexión, lectura, escritura y pool; plazo total de cinco segundos; una sola tentativa. |
| RNF-005 | Integridad | Cálculo decimal y conservación del precio utilizado. | Precio 0.10 y cantidad 3 producen exactamente 0.30; consulta devuelve la información persistida. |
| RNF-006 | Mantenibilidad | Contratos y procedimientos locales documentados. | OpenAPI en ambas APIs; guía con arranque, ejemplos, diagnóstico y apagado. |
| RNF-007 | Verificabilidad | Caminos principales, rechazos y fallos con validaciones trazables. | Cada requisito tiene fase y prueba o procedimiento; no se declara validación no ejecutada. |
| RNF-008 | Evolución de datos | Migraciones independientes y repetibles. | Historial propio por servicio; repetir upgrade no altera registros ni el otro esquema. |

## Casos y comportamiento esperado

| Id | Caso | Condición de entrada | Comportamiento esperado |
|---|---|---|---|
| C-001 | Crear y recuperar producto | Nombre válido y precio 12.50. | 201 y recuperación por ID y lista con 200. |
| C-002 | Crear y recuperar pedido | Producto existente y cantidad 2. | Consulta HTTP; 201 con total 25.00; lectura posterior persistida. |
| C-003 | Entrada inválida | Campos ausentes, extra o fuera de límites, JSON o UUID inválido. | 422 sin escritura; detalles sin cuerpos completos ni datos sensibles. |
| C-004 | Recurso inexistente | UUID válido desconocido. | 404 al consultar o crear pedido; sin nuevas escrituras. |
| C-005 | Catálogo caído | Conexión rechazada o respuesta 5xx. | Creación de pedido: 503 sin escritura; listado de pedidos disponible. |
| C-006 | Catálogo lento | Consulta supera cinco segundos. | 504 sin escritura ni reintento. |
| C-007 | Catálogo inválido | JSON inválido, datos inconsistentes, 3xx u otro estado inesperado. | 502 sin escritura; no se siguen redirecciones. |
| C-008 | Base caída | Base detenida antes de la operación. | Datos y readiness: 503; liveness: 200. |
| C-009 | Recuperación | Se restablece catálogo o base. | Siguientes solicitudes funcionan sin recrear APIs; readiness: 200. |
| C-010 | Persistencia | Datos existentes y apagado normal. | Reinicio conserva identificadores y contenido. |
| C-011 | Acceso cruzado | Credencial de un servicio intenta acceder al otro esquema. | Lectura y escritura rechazadas; esquema propio accesible. |
| C-012 | Arranque repetido | Volumen vacío y luego existente. | Migraciones sin duplicados ni carga automática de ejemplos. |
| C-013 | Dinero | Precio 0.10, cantidad 3. | Total persistido y devuelto como 0.30. |
| C-014 | Listado | Base vacía o más registros que el límite. | Lista vacía o página ordenada de forma determinista. |
| C-015 | Correlación | Cabecera válida, ausente o inválida. | Se conserva la válida o genera otra; se propaga y devuelve. |
| C-016 | POST repetido | Dos solicitudes válidas iguales. | Dos recursos con identificadores distintos. |
| C-017 | Configuración ausente | Falta credencial obligatoria o está vacía. | Arranque falla sin mostrar valores ni usar contraseñas predeterminadas. |
| C-018 | Escritura incierta | Conexión perdida durante confirmación. | 503 sin reintento; no se garantiza ausencia de escritura si el resultado de commit es desconocido. |
| C-019 | Tipo de contenido no admitido | POST con un tipo distinto de application/json. | 415 sin escritura. |
| C-020 | Error HTTP general | Ruta desconocida, método no admitido o fallo inesperado. | 404, 405 o 500 con sobre normalizado y correlación, sin detalles internos. |

## Supuestos

| Verificado | Id | Supuesto | Impacto si resulta falso |
|---|---|---|---|
| Sí, respuestas de alcance | S-001 | Ejemplo local con dos servicios, base compartida, sin stock ni pagos. | Revisar requisitos y contratos. |
| No; comprobación operativa pendiente | S-002 | Docker Engine/Desktop con Compose v2, acceso a imágenes y puertos 8001/8002 libres. | Bloquea validación local. |
| No; comprobación operativa pendiente | S-003 | Python 3 y curl disponibles para configuración y ejemplos. | Instalar herramientas antes de los procedimientos. |
| Valor por defecto del diseño aceptado | S-004 | Unidad monetaria única de demostración, sin conversión. | Ampliar modelo y reglas monetarias. |

## Fuera de alcance

- Implementar servicios durante esta entrega documental; las fases describen su implementación futura.
- Autenticación HTTP, frontend, stock, pagos, múltiples productos por pedido, actualización y eliminación.
- Métricas y Collector dentro de ID-001; su instrumentación se define en [ID-002](../ID-002-observabilidad-otel/00-especificacion.md). Visor, Kubernetes, nube y pipeline CI/CD quedan fuera de ambos planes.
- Idempotencia de negocio, exactamente una vez, reintentos y transacciones distribuidas.
- Acceso cruzado a tablas, bases separadas por servicio y permisos propios de producción.
- Backups productivos, alta disponibilidad y publicación fuera de loopback.

## Aclaraciones pendientes

No quedan aclaraciones abiertas que afecten el diseño.

| Estado | Id | Pregunta | Bloquea a |
|---|---|---|---|
| Resuelta → D-001 | A-001 | Tecnología: Python/FastAPI. | Ninguna fase. |
| Resuelta → D-002 | A-002 | Ejemplo: pedidos y catálogo. | Ninguna fase. |
| Resuelta → D-003 | A-003 | Observabilidad: logs y salud. | Ninguna fase. |
| Resuelta → D-004 | A-004 | Base: PostgreSQL compartido. | Ninguna fase. |
| Resuelta → D-005 | A-005 | Propiedad: datos propios por servicio. | Ninguna fase. |
| Resuelta → D-006 | A-006 | Funcionalidad: crear y consultar. | Ninguna fase. |

## Bitácora de decisiones

D-001 a D-006 proceden de respuestas explícitas; D-007 a D-010 concretan el plan aceptado. Las restantes fijan valores técnicos mínimos para hacerlo implementable y se revisan en esta bitácora si cambian.

| Id | Decisión | Alternativas consideradas | Motivo | Origen |
|---|---|---|---|---|
| D-001 | Python y FastAPI en ambos servicios. | Node.js/TypeScript; Java/Spring Boot. | Ejemplo pequeño con contratos HTTP. | Respuesta de alcance. |
| D-002 | Pedidos consulta productos de catálogo por HTTP. | A/B; clientes/pedidos. | Dependencia funcional verificable. | Respuesta de alcance. |
| D-003 | Logs JSON y salud. | OTLP; stack OpenTelemetry. | Primera versión básica. | Respuesta de alcance. |
| D-004 | Una instancia y una base PostgreSQL. | MySQL; MongoDB. | Persistencia relacional compartida. | Respuesta de alcance. |
| D-005 | Esquemas catalog y orders con roles propios usados también por migraciones. | Tablas compartidas; roles DDL separados. | Separación y operación sencilla; se acepta DDL sobre esquema propio. | Respuesta y plan. |
| D-006 | Crear, listar y consultar; un producto por pedido. | CRUD completo. | Limitar reglas de ciclo de vida. | Respuesta de alcance. |
| D-007 | SQLAlchemy 2, Psycopg 3, Alembic y HTTPX asíncrono reutilizable. | SQL directo; crear tablas al arrancar; cliente por solicitud. | Migraciones explícitas y gestión de conexiones. | Plan aceptado. |
| D-008 | APIs en 127.0.0.1:8001/8002, base sin publicar y credenciales generadas. | Puertos públicos; contraseñas de ejemplo. | Operación local sin secretos versionados. | Plan aceptado. |
| D-009 | Sin autenticación HTTP ni idempotencia de POST. | Tokens; deduplicación persistida. | Alcance local básico. | Plan aceptado. |
| D-010 | Documentación ahora; implementación pendiente e informe de cierre reservado. | Implementar durante la especificación. | Entrega solicitada basada en plantilla SDD. | Plan aceptado. |
| D-011 | Python 3.12, PostgreSQL 17 y versiones exactas de dependencias directas registradas en `requirements.txt`. | Versiones flotantes sin registro. | Conservar versiones reproducibles de dependencias directas; la instalación y compatibilidad ejecutada quedan pendientes. | Diseño e implementación. |
| D-012 | UUID, UTC, dinero decimal como texto de dos decimales y páginas limit/offset. | Secuenciales; float; listas ilimitadas. | Precisión y respuestas acotadas. | Diseño documental. |
| D-013 | HTTPX: cinco segundos por fase y plazo total de cinco segundos con cancelación. | Solo timeout de inactividad; reintentos. | Acotar la llamada completa. | Concreción del plan; referencia HTTPX. |
| D-014 | Migraciones como tareas Compose; bootstrap solo en volumen vacío. | Migrar desde APIs; regenerar esquema. | Separar inicialización y servicio. | Diseño; referencias Docker y Alembic. |
| D-015 | Errores estables y X-Request-ID. | Errores internos expuestos. | Diagnóstico sin filtrar detalles. | Diseño documental. |

## Referencias

- [Guía de trabajo](../GUIA-AGENTE.md) y [constitución](../CONSTITUCION.md).
- [Plan general](00-plan-general.md): contratos técnicos y referencias oficiales verificadas el 2026-10-14.
- Solicitud y respuestas de alcance de esta conversación; sin documentos externos privados.

## Gate 1 — revisión de la especificación

- [x] Comportamiento y aceptación separados del diseño; elecciones registradas en bitácora.
- [x] Requisitos identificados y fuera de alcance explícito.
- [x] Sin aclaraciones abiertas que afecten el diseño.
- [x] Revisión documental del 2026-10-14; no constituye validación de software.
