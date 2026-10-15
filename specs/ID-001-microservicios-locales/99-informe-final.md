# ID-001 — Informe final reservado: catálogo y pedidos locales

> Documento reservado para cierre, pausa o transferencia después de la revisión correspondiente. No constituye un informe de implementación completada ni una ejecución del Gate 4.

## Identificación

| Campo | Detalle |
|---|---|
| ID | ID-001 |
| Título | Catálogo y pedidos locales con dependencia HTTP y persistencia compartida. |
| Sprint / iteración | No documentado. |
| Estado de cierre | Implementación sin validar; el plan permanece abierto. |
| Sistemas y repositorios afectados | pipeline-otel-end-to-end; APIs y entorno local previstos. |
| Iniciativas relacionadas | Ninguna definida. |

## Resumen

Se escribieron los servicios de catálogo y pedidos, las migraciones, el bootstrap de PostgreSQL, Docker Compose y la guía local. Las validaciones automatizadas y operativas no se ejecutaron. El plan queda abierto y este informe deberá actualizarse al registrar evidencia de validación.

## Problema atendido

El resultado esperado es un ejemplo local que demuestre comunicación HTTP entre servicios y persistencia con datos propios. El código correspondiente ya está presente; su comportamiento todavía no está verificado en ejecución.

## Resultado por fase

| Estado | Fase | Resultado entregado | Desviación respecto al diseño |
|---|---|---|---|
| Implementada sin validar | 1 — Persistencia | Bootstrap, configuración, esquemas y migraciones escritos. | Pruebas de permisos y PostgreSQL pendientes. |
| Implementada sin validar | 2 — Catálogo | API de productos, salud, errores y logs escritos. | Pruebas y flujo HTTP real pendientes. |
| Implementada sin validar | 3 — Pedidos | API, persistencia de pedidos y cliente HTTP escritos. | Pruebas de fallos e integración pendientes. |
| Implementada sin validar | 4 — Operación local | Compose y guía de uso escritos. | Build, arranque y persistencia pendientes de confirmar. |

Las cuatro fases registran `Implementada sin validar` en sus archivos y en el plan general. Gate 3 documental quedó actualizado; no se ejecutó Gate 4 porque falta evidencia automatizada y funcional.

## Cumplimiento de requisitos

| Estado | Requisito | Evidencia |
|---|---|---|
| Implementado sin validar | RF-001 | Código documentado en la fase correspondiente; criterio aún sin ejecutar. |
| Implementado sin validar | RF-002 | Código documentado en la fase correspondiente; criterio aún sin ejecutar. |
| Implementado sin validar | RF-003 | Código documentado en la fase correspondiente; criterio aún sin ejecutar. |
| Implementado sin validar | RF-004 | Código documentado en la fase correspondiente; criterio aún sin ejecutar. |
| Implementado sin validar | RF-005 | Código documentado en la fase correspondiente; criterio aún sin ejecutar. |
| Implementado sin validar | RF-006 | Código documentado en la fase correspondiente; criterio aún sin ejecutar. |
| Implementado sin validar | RF-007 | Código documentado en la fase correspondiente; criterio aún sin ejecutar. |
| Implementado sin validar | RF-008 | Código documentado en la fase correspondiente; criterio aún sin ejecutar. |
| Implementado sin validar | RF-009 | Código documentado en la fase correspondiente; criterio aún sin ejecutar. |
| Implementado sin validar | RF-010 | Código documentado en la fase correspondiente; criterio aún sin ejecutar. |
| Implementado sin validar | RF-011 | Código documentado en la fase correspondiente; criterio aún sin ejecutar. |
| Implementado sin validar | RF-012 | Código documentado en la fase correspondiente; criterio aún sin ejecutar. |
| Implementado sin validar | RNF-001 | Código documentado en la fase correspondiente; criterio aún sin ejecutar. |
| Implementado sin validar | RNF-002 | Código documentado en la fase correspondiente; criterio aún sin ejecutar. |
| Implementado sin validar | RNF-003 | Código documentado en la fase correspondiente; criterio aún sin ejecutar. |
| Implementado sin validar | RNF-004 | Código documentado en la fase correspondiente; criterio aún sin ejecutar. |
| Implementado sin validar | RNF-005 | Código documentado en la fase correspondiente; criterio aún sin ejecutar. |
| Implementado sin validar | RNF-006 | Código documentado en la fase correspondiente; criterio aún sin ejecutar. |
| Implementado sin validar | RNF-007 | Código documentado en la fase correspondiente; criterio aún sin ejecutar. |
| Implementado sin validar | RNF-008 | Código documentado en la fase correspondiente; criterio aún sin ejecutar. |

## Cambios entregados

| Ubicación | Cambio aplicado | Efecto observable |
|---|---|---|
| `specs/` | Guía, constitución y plantilla reutilizable. | Convención documental disponible. |
| Esta carpeta de plan | Especificación, plan técnico y cuatro fases. | Contratos, alcance y validaciones revisables. |

Se entregaron cambios de aplicación y operación local. Su presencia en los archivos no sustituye las validaciones automatizadas y funcionales, que permanecen pendientes.

## Evidencia de validación

| Tipo | Qué se verificó | Resultado |
|---|---|---|
| Automatizada / estática de software | Pruebas y sintaxis de servicios y Compose. | Pendiente; no se ejecutaron comprobaciones estáticas ni automatizadas. |
| Funcional / operativa | Flujo real, salud, permisos, reinicios y recuperación. | Pendiente de confirmación. |
| Reversión y compatibilidad | Conservación y eliminación explícita del volumen. | Procedimiento documentado; ejecución pendiente. |

## Decisiones técnicas relevantes

Las decisiones D-001 a D-015 y sus alternativas están en la [bitácora de la especificación](00-especificacion.md). No se registraron decisiones nuevas durante ejecución de software, porque aún no se inició.

| Id | Decisión | Alternativa descartada | Motivo | Consecuencia asumida |
|---|---|---|---|---|
| D-005 | Datos y roles propios en base compartida. | Tablas compartidas. | Propiedad separada. | Una caída de base afecta ambos servicios; roles poseen DDL propio. |
| D-009 | Sin idempotencia de POST. | Deduplicación persistida. | Ejemplo básico. | Repetir solicitudes puede duplicar recursos. |
| D-010 | Entrega documental. | Implementación en esta entrega. | Alcance acordado. | Todas las fases de software siguen pendientes. |

## Limitaciones conocidas

- No existe todavía un sistema ejecutable; no puede afirmarse que los servicios funcionen en Docker Compose.
- El diseño es local, sin autenticación HTTP, OpenTelemetry, stock, pagos ni reintentos automáticos.
- Un fallo durante commit puede dejar resultado incierto y no se ofrece exactamente una vez.

## Pendientes y bloqueantes

| Id | Pendiente o bloqueante | Impacto | Siguiente acción | Dónde continúa |
|---|---|---|---|---|
| 1 | Implementar persistencia y configuración. | Bloquea acceso real a datos. | Ejecutar fase 1. | Este plan. |
| 2 | Implementar catálogo y pedidos. | Bloquea flujo funcional. | Ejecutar fases 2 y 3. | Este plan. |
| 3 | Integrar y confirmar entorno local. | Bloquea validación de operación. | Ejecutar fase 4 y registrar evidencia. | Este plan. |
| 4 | Confirmar prerrequisitos del entorno. | Puede bloquear pruebas operativas. | Verificar Docker, red, herramientas y puertos. | Plan general. |

## Estado de cierre

El código existe y las cuatro fases están implementadas sin validar. No se afirma que los servicios arranquen o que sus criterios de aceptación se cumplan; no se ejecutó Gate 4. Los requisitos permanecen pendientes de validación y este informe no cierra el plan.

## Próximos pasos recomendados

1. Implementar las pruebas unitarias previstas y fijar dependencias de desarrollo.
2. Ejecutar validaciones estáticas y levantar Compose en un entorno disponible.
3. Registrar evidencia funcional, completar Gate 4 y actualizar este informe.

## Verificación de cierre documental

Lista reservada para Gate 4; queda sin marcar hasta confirmar los resultados de software.

- [ ] Estados de implementación coherentes en todas las fases y plan general.
- [ ] Documentación contrastada con comportamiento de software real.
- [ ] Todos los requisitos con resultado y evidencia ejecutada.
- [ ] Bitácora completa con decisiones de implementación.
- [ ] Sin aclaraciones ni bloqueantes abiertos que afecten el cierre.
- [ ] Enlaces revisados durante cierre.
- [ ] Redacción impersonal y ausencia de estado de control de versiones en los documentos de trabajo.
