# Constitución — pipeline-otel-end-to-end

## Alcance de esta constitución

| Campo | Detalle |
|---|---|
| Aplica a | Servicios locales de catálogo y pedidos, dependencia HTTP, persistencia compartida y Docker Compose. |
| Hereda de | Ninguna política adicional documentada. |
| Última revisión | 2026-10-14 |

## Principios

Se conservan los identificadores de la plantilla con enunciados adaptados al alcance acordado.

| Id | Nivel | Principio | Cómo se verifica |
|---|---|---|---|
| P-001 | DEBE | Cada requisito tiene fase y validación; implementación y validación se registran por separado. | Matriz de cobertura y evidencia de las fases. |
| P-002 | DEBE | Las contraseñas se generan localmente y no aparecen en archivos versionados, respuestas o logs. | `.env` excluido, ejemplo sin valores secretos y revisión de salidas. |
| P-003 | DEBE | El apagado normal conserva datos y toda reversión destructiva se identifica expresamente. | Prueba de persistencia y procedimiento de reinicio. |
| P-004 | DEBE | Cada servicio usa su propio rol y esquema; los datos del otro se consultan por HTTP. | Pruebas de permisos y revisión de consultas y migraciones. |
| P-005 | DEBE | Las solicitudes se correlacionan por un identificador propagado, sin atribuir identidades no autenticadas. | Logs y cabecera de correlación en respuestas y llamadas. |
| P-006 | DEBE | Repetir arranque o migraciones ya aplicadas no duplica ni destruye datos. | Repetición con volumen existente. |
| P-007 | DEBERÍA | Se mantiene un ejemplo pequeño sin infraestructura ajena al alcance. | Dos APIs, una base y tareas auxiliares de migración. |
| P-008 | DEBE | El comportamiento externo que condiciona el diseño se verifica en documentación oficial. | Referencias fechadas en el plan. |

## Restricciones no negociables del entorno

| Restricción | Origen | Consecuencia si se incumple |
|---|---|---|
| Python/FastAPI y PostgreSQL compartido. | D-001 y D-004 de la especificación. | Incumplimiento de la elección tecnológica. |
| Docker Compose local; APIs publicadas solo en loopback. | Alcance y D-008. | Exposición o dependencia fuera de alcance. |
| Sin autenticación HTTP, stock ni pagos. OpenTelemetry se rige por ID-002. | D-003 y D-009 de ID-001; ID-002. | Ampliación de alcance que exige revisar requisitos. |
| Plantillas de origen sin completar ni modificar. | Guía SDD. | Pérdida de la base reutilizable. |
| Validación funcional pendiente hasta registrar confirmación real. | Sección 4 de la guía. | No se puede declarar la fase completada. |

## Excepciones registradas

No existen excepciones. La ausencia de autenticación HTTP pertenece al alcance local; los permisos de base de datos son obligatorios. Los roles de aplicación también ejecutan sus migraciones y poseen DDL sobre su esquema: simplificación local registrada en D-005.
