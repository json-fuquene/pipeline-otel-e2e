# ID-001 — Fase 1: Persistencia y configuración

## Identificación

| Campo | Detalle |
|---|---|
| Plan | ID-001 — Catálogo y pedidos locales. |
| Fase | 1 — Persistencia y configuración. |
| Estado | Implementada sin validar |
| Requisitos que cubre | RF-012, RNF-002, RNF-008 |
| Sistemas y repositorios | PostgreSQL, esqueletos de servicios, bootstrap, migraciones y configuración local. |
| Dependencias previas | Ninguna fase; Docker/Compose para validación real y Python 3 para configuración. |
| Habilita a | Fases 2 y 3; base para fase 4. |

## Objetivo

Ambos servicios pueden conectar con roles separados a una misma base, aplicar sus migraciones y operar solo sobre sus esquemas.

## Contexto de la fase

La propiedad de datos debe existir antes de implementar endpoints. El bootstrap solo se ejecuta al inicializar un volumen vacío; no sustituye migraciones. Se aplican la [especificación](00-especificacion.md), los contratos del [plan general](00-plan-general.md) y la [constitución](../CONSTITUCION.md). Esta fase puede implementarse usando esos documentos y el presente archivo.

## Alcance técnico

### Cambios previstos

| Ubicación | Cambio | Requisito asociado |
|---|---|---|
| `docker/postgres/init-services.sh` | Crear roles y esquemas con privilegios separados, sin secretos literales. | RF-012, RNF-002 |
| `services/catalog/` y `services/orders/` | Requisitos, Dockerfiles, configuración, motor, modelos y Alembic con historiales separados. | RF-012, RNF-008 |
| `compose.yaml`, `.env.example`, `.gitignore`, `.dockerignore` | Definir inicialmente PostgreSQL y tareas de migración; excluir secretos y contextos locales. | RNF-002, RNF-008 |
| `scripts/init-local-env.py` y `tests/unit/` | Generar configuración sin sobrescribir y probar su comportamiento. | RNF-002 |

### No incluido en esta fase

- Endpoints de negocio, logs HTTP y salud: fases 2 y 3.
- Integración de arranque de las dos APIs y guía completa: fase 4.

## Diseño

Crear los árboles `services/catalog/app` y `services/orders/app` con paquetes importables distintos. Añadir configuración validada, motor asíncrono, modelos y una migración inicial por servicio con las columnas y límites exactos del plan general. Alembic tendrá `script_location` independiente de cwd, tabla de versión en el esquema propio y filtrado de objetos al autogenerar. Usar conexiones síncronas de Psycopg en el entorno Alembic para simplificar las migraciones, manteniendo el dialecto asíncrono en la aplicación. El driver admite ambos usos.

Configurar un Compose parcial con `postgres`, `catalog-migrate` y `orders-migrate`, construidos desde la raíz. Los Dockerfiles deben permitir ejecutar Alembic aunque todavía no exista una API funcional; las fases siguientes agregan el comando Uvicorn al servicio de larga duración. Cada imagen conserva únicamente su árbol de servicio y sus dependencias.

El bootstrap corre en una transacción tras crear la base de la imagen oficial. Crea `catalog_app` y `orders_app` con LOGIN, contraseñas generadas y sin SUPERUSER/CREATEDB/CREATEROLE; crea y asigna los esquemas. Retira privilegios de PUBLIC sobre los esquemas propios, CREATE en public y privilegios generales de base; concede CONNECT a ambos roles. No se conceden derechos entre servicios. Los valores de contraseña llegan como variables y se pasan a psql como literales correctamente escapados, sin echo, trazado de shell ni logs del contenido.

`init-local-env.py` usa biblioteca estándar, genera tres secretos aleatorios hexadecimales distintos y crea `.env` exclusivamente con modo 0600. Si ya existe, no cambia bytes ni permisos y termina correctamente con mensaje sin valores. No se genera un `.env` real durante esta entrega documental. Las pruebas usan directorios temporales. La configuración de API y migración exige variables DB_* no vacías y usa URL.create para evitar problemas de escape.

Al repetir `upgrade head` no se ejecuta DDL adicional ni se altera otro esquema. El downgrade inicial elimina únicamente las tablas propias; solo se valida en datos desechables y nunca se recomienda como apagado normal.

### Comportamiento esperado por caso

| Caso | Condición | Resultado esperado |
|---|---|---|
| C-011 | Acceso con rol propio y al esquema ajeno. | Acceso propio permitido; ajeno rechazado. |
| C-012 | Dos ejecuciones de upgrade sobre mismo volumen. | Mismo esquema, versión y registros. |
| C-017 | Falta contraseña o DB_PASSWORD vacío. | Fallo de configuración sin mostrar valores. |

## Tareas

Las tareas siguen el orden listado salvo las marcadas `[P]`, que pueden realizarse en paralelo después de sus prerrequisitos. La marca no exige usar agentes paralelos.

| Estado | # | Tarea | Criterio de aceptación |
|---|---|---|---|
| [x] | 1 | Crear generador de configuración, archivos de exclusión y pruebas de no sobrescritura. | Contraseñas distintas, .env 0600 y ejemplo sin secretos. |
| [x] | 2 | Crear esqueletos de paquetes, requisitos fijados, motores y Dockerfiles independientes. | Cada imagen importa su configuración y ejecuta Alembic sin importar el otro servicio. |
| [x] | 3 | Implementar bootstrap y Compose parcial. | PostgreSQL inicia sin puerto publicado y crea roles/esquemas. |
| [x] | 4 | `[P]` Implementar modelo y migración de catálogo. | products y versión Alembic en catalog. |
| [x] | 5 | `[P]` Implementar modelo y migración de pedidos. | orders y versión Alembic en orders. |
| [ ] | 6 | Validar permisos, upgrade repetido y configuración; registrar resultados reales. | Restricciones y separación confirmadas; estados documentales actualizados. |

## Validación

Los comandos son procedimientos previstos, aún no ejecutados. Se ejecutan desde la raíz. Las pruebas unitarias usan dobles de dependencias; los procedimientos con servicios reales son validación funcional y requieren confirmación.

| Estado | Tipo | Qué verifica | Cómo se ejecuta | Resultado esperado |
|---|---|---|---|---|
| Pendiente | Automatizada | RNF-002: generación, permisos de archivo, valores vacíos y no sobrescritura. | `python3 -m pytest tests/unit` | Pruebas aprobadas sin Docker. |
| Pendiente | Estática | RNF-002/RNF-008: sintaxis y estilo. | `python3 -m ruff check services scripts`; `python3 -m compileall -q services scripts` | Salida 0. |
| Pendiente | Estática | RNF-002: Compose resuelto sin mostrar secretos. | `python3 scripts/init-local-env.py`; `docker compose config --quiet` | Archivo local creado y configuración válida. |
| Pendiente de confirmación | Funcional / operativa | RF-012/RNF-008: bootstrap y migraciones. | Procedimiento siguiente. | Versiones propias y permisos separados. |
| Pendiente de confirmación | Funcional / operativa | RNF-008: downgrade en datos desechables. | Procedimiento de reversión de migraciones descrito debajo. | Downgrade de catálogo no elimina tabla de pedidos. |

### Procedimiento funcional de persistencia

```sh
python3 scripts/init-local-env.py
docker compose config --quiet
docker compose up -d --wait postgres
docker compose run --rm catalog-migrate
docker compose run --rm orders-migrate
docker compose run --rm catalog-migrate
docker compose run --rm orders-migrate
docker compose exec -T postgres psql -U catalog_app -d pipeline -c 'SELECT version_num FROM catalog.alembic_version; SELECT count(*) FROM catalog.products;'
docker compose exec -T postgres psql -U orders_app -d pipeline -c 'SELECT version_num FROM orders.alembic_version; SELECT count(*) FROM orders.orders;'
```

Resultado esperado: cuatro migraciones terminan con 0; las repeticiones no cambian versión ni filas. Validar por separado los rechazos; los siguientes comandos deben terminar con código distinto de cero y error de permisos:

```sh
docker compose exec -T postgres psql -U catalog_app -d pipeline -c 'SELECT * FROM orders.orders;'
docker compose exec -T postgres psql -U orders_app -d pipeline -c 'SELECT * FROM catalog.products;'
docker compose exec -T postgres psql -U catalog_app -d pipeline -c "INSERT INTO orders.orders DEFAULT VALUES;"
docker compose exec -T postgres psql -U orders_app -d pipeline -c "INSERT INTO catalog.products DEFAULT VALUES;"
```

Estos comandos comprueban autorización por rol, no la autenticación remota por contraseña. Cada rechazo debe mencionar permisos; un fallo por otra causa no satisface el caso.

Solo con un volumen de prueba desechable: ejecutar `docker compose run --rm catalog-migrate alembic -c services/catalog/alembic.ini downgrade base`, comprobar que `orders.orders` sigue existiendo con la consulta anterior y volver a ejecutar `docker compose run --rm catalog-migrate`. No se realiza un downgrade sobre datos que deban conservarse. Registrar las referencias de imagen y versiones de dependencias efectivamente utilizadas.


## Reversión y compatibilidad

Los contratos son nuevos. Detener el entorno con `docker compose down` conserva el volumen. No ejecutar downgrade ni reset sobre datos que deban conservarse. El procedimiento destructivo explícito figura en fase 4.

## Riesgos y bloqueantes de la fase

| Estado | Elemento | Impacto | Mitigación o siguiente acción |
|---|---|---|---|
| Abierto | Docker/Compose y red no comprobados. | Medio | Confirmar entorno antes de ejecutar procedimientos. |
| Abierto | Bootstrap no continúa automáticamente tras fallo en volumen inicializado. | Medio | Fallar inmediatamente; diagnosticar y usar reset solo si datos son desechables. |
| Abierto | Secretos presentes en entorno local de contenedores. | Bajo, local | No imprimir configuración expandida; usar variables mínimas por contenedor. |

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
