# [ID] — Informe final: [Título del plan]

> **Uso:** se completa al cerrar, pausar o transferir el plan, después de ejecutar el **Gate 4** (revisión general) de [`GUIA-AGENTE.md`](../GUIA-AGENTE.md). Diferencia siempre entre implementado, validado, integrado y en operación: no se declara cierre integral si queda alguna fase, validación o bloqueante abierto. Redacción impersonal; sin estado de repositorio.

## Identificación

| Campo | Detalle |
|---|---|
| **ID** | [ID-000] |
| **Título** | [Título del plan] |
| **Sprint / iteración** | [Sprint o `No documentado`] |
| **Estado de cierre** | [Cerrado y validado / Cierre funcional con pendientes declarados / Implementación parcial / En espera / Descartado] |
| **Sistemas y repositorios afectados** | [Ubicaciones] |
| **Iniciativas relacionadas** | [IDs y tipo de relación] |

## Resumen

[Tres o cuatro frases: qué problema resolvía el plan, qué quedó entregado, qué quedó validado y qué sigue abierto. Es la única parte que se lee sin contexto previo, por lo que no depende del resto del documento.]

## Problema atendido

[Resumen del problema original y de su impacto, tomado de `00-especificacion.md`.]

## Resultado por fase

| Estado | Fase | Resultado entregado | Desviación respecto al diseño |
|---|---|---|---|
| [Completada / Implementada sin validar / Parcial / No implementada] | [Fase 1 — nombre] | [Qué quedó funcionando] | [Ninguna, o qué cambió y por qué] |
| [Estado] | [Fase N — nombre] | [Resultado] | [Desviación] |

## Cumplimiento de requisitos

| Estado | Requisito | Evidencia |
|---|---|---|
| [Cumplido / Cumplido parcialmente: (alcance real) / No cumplido: (motivo)] | RF-001 | [Prueba, ejecución, verificación o comprobación registrada] |
| [Estado] | RNF-001 | [Evidencia] |

## Cambios entregados

| Ubicación | Cambio aplicado | Efecto observable |
|---|---|---|
| `[ruta, componente o sistema]` | [Qué quedó implementado ahí] | [Cómo se nota en el comportamiento del sistema] |

## Evidencia de validación

| Tipo | Qué se verificó | Resultado |
|---|---|---|
| Automatizada / estática | [Alcance de las pruebas ejecutadas] | [Resultado concreto] |
| Funcional / operativa | [Flujo verificado contra sistemas reales] | [Resultado confirmado, o `Pendiente de confirmación`] |
| Reversión y compatibilidad | [Qué se comprobó] | [Resultado / `No aplica`] |

## Decisiones técnicas relevantes

| Id | Decisión | Alternativa descartada | Motivo | Consecuencia asumida |
|---|---|---|---|---|
| D-001 | [Qué quedó decidido] | [Opción evaluada y descartada] | [Por qué] | [Limitación o compromiso que deja abierto] |

## Limitaciones conocidas

Comportamiento que el resultado entregado **no** cubre, aunque el plan esté cerrado. Se declara aquí para que no se descubra en operación.

- [Limitación, con el escenario concreto en que se manifiesta]
- [Cobertura parcial aceptada, con la decisión que la respalda]

## Pendientes y bloqueantes

[Si no queda ninguno, se declara explícitamente: «No quedan pendientes ni bloqueantes abiertos».]

| Id | Pendiente o bloqueante | Impacto | Siguiente acción | Dónde continúa |
|---|---|---|---|---|
| 1 | [Qué falta] | [Consecuencia de no resolverlo] | [Acción concreta] | [Este plan / Plan relacionado / Fuera de alcance] |

## Estado de cierre

[Qué se puede afirmar y qué no. Distinguir de forma explícita entre: implementado (el cambio existe), validado (se comprobó que funciona), integrado (está en el flujo definitivo) y en operación (está en uso real). Si alguna de esas afirmaciones no se sostiene con evidencia, se declara aquí y no se presenta como cierre completo.]

## Próximos pasos recomendados

1. [Acción siguiente, con el motivo por el que importa]
2. [Acción siguiente]

## Verificación de cierre documental

Confirmación de que el **Gate 4** de `../GUIA-AGENTE.md` se ejecutó sobre esta carpeta.

- [ ] El estado de cada fase coincide entre su archivo y la tabla de `00-plan-general.md`.
- [ ] Lo documentado corresponde al comportamiento real del sistema.
- [ ] Todos los requisitos aparecen con estado y evidencia.
- [ ] La bitácora de decisiones está completa.
- [ ] No quedan aclaraciones abiertas ni riesgos con estado incorrecto.
- [ ] Los enlaces entre documentos resuelven.
- [ ] No hay referencias en tercera persona ni estado de control de versiones en ningún archivo.
