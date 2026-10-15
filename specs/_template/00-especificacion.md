# [ID] — Especificación: [Título]

> **Uso:** este documento describe **qué** se necesita y **por qué**, no cómo se construye. Sin elección de tecnología, sin diseño de componentes, sin estructura de código: eso vive en `00-plan-general.md`. Redacción impersonal; sin estado de repositorio (ver `../GUIA-AGENTE.md`).
>
> Antes de escribir el plan general se ejecuta el **Gate 1** de `../GUIA-AGENTE.md`.

## Identificación

| Campo | Detalle |
|---|---|
| **ID** | [ID-000] |
| **Título** | [Título breve y descriptivo] |
| **Origen** | [Item de catálogo, informe, incidente, solicitud o hallazgo que motiva el plan] |
| **Sprint / iteración** | [Sprint o `No documentado`] |
| **Estado de la especificación** | [Borrador / Con aclaraciones abiertas / Aprobada / Modificada durante la implementación] |
| **Iniciativas relacionadas** | [IDs y tipo de relación] |

## Problema

[Situación actual, qué falla o qué falta hoy, a quién o a qué afecta y con qué consecuencia. Se describe el problema observable, no la solución imaginada.]

## Resultado esperado

[Cómo se comporta el sistema cuando el plan esté terminado, en una o dos frases. Formulado como estado final observable.]

## Actores y sistemas involucrados

| Actor o sistema | Rol en el flujo | Qué cambia para él |
|---|---|---|
| [Rol de usuario, servicio, pipeline o sistema externo] | [Qué hace en el flujo] | [Diferencia respecto a hoy] |

## Requisitos funcionales

Cada requisito describe comportamiento observable y es verificable de forma independiente. Formato recomendado: **cuándo** ocurre la condición, **qué** debe hacer el sistema.

| Id | Requisito | Criterio de aceptación | Prioridad |
|---|---|---|---|
| RF-001 | [Cuando (condición), el sistema debe (comportamiento observable)] | [Cómo se comprueba que se cumple, con resultado esperado concreto] | [Obligatorio / Deseable] |
| RF-002 | [Requisito] | [Criterio verificable] | [Prioridad] |
| RF-003 | [Requisito] | [Criterio verificable] | [Prioridad] |

## Requisitos no funcionales

| Id | Categoría | Requisito | Criterio de aceptación |
|---|---|---|---|
| RNF-001 | [Seguridad / Rendimiento / Disponibilidad / Compatibilidad / Observabilidad / Operación] | [Restricción o cualidad exigida, con umbral cuando aplique] | [Cómo se comprueba] |
| RNF-002 | [Categoría] | [Requisito] | [Criterio] |

## Casos y comportamiento esperado

Casos relevantes, incluidos los caminos de error. Un caso que no está aquí no se implementa.

| Id | Caso | Condición de entrada | Comportamiento esperado |
|---|---|---|---|
| C-001 | [Caso principal] | [Estado y entrada] | [Resultado observable] |
| C-002 | [Caso de error o rechazo] | [Estado y entrada] | [Rechazo, mensaje o código esperado] |
| C-003 | [Caso límite] | [Estado y entrada] | [Resultado] |

## Supuestos

Condiciones que se dan por ciertas y sobre las que se construye el plan. Si un supuesto resulta falso, el plan se revisa.

| Verificado | Id | Supuesto | Impacto si resulta falso |
|---|---|---|---|
| [Sí, contra (fuente) / No] | S-001 | [Supuesto] | [Qué parte del plan se cae o cambia] |

## Fuera de alcance

Delimita explícitamente lo que este plan no resuelve, para acotar la exploración durante la implementación.

- [Elemento excluido y, cuando aplique, la iniciativa que sí lo cubre]
- [Alternativa evaluada y descartada, con remisión a la bitácora de decisiones]
- [Trabajo relacionado que queda para más adelante]

## Aclaraciones pendientes

Marcadores `[NECESITA ACLARACIÓN: pregunta concreta]` abiertos en cualquier documento del plan. Ninguna fase se implementa con una aclaración abierta que afecte su alcance.

| Estado | Id | Pregunta | Bloquea a |
|---|---|---|---|
| [Abierta / Resuelta: (respuesta) → registrada en D-00N] | A-001 | [Pregunta concreta, con las opciones consideradas si existen] | [Requisito o fase afectada] |

## Bitácora de decisiones

Registro acumulativo de decisiones tomadas durante la especificación, el diseño y la implementación. Se agrega una entrada por cada decisión con más de un camino razonable, incluida la alternativa descartada y su motivo.

| Id | Decisión | Alternativas consideradas | Motivo | Origen |
|---|---|---|---|---|
| D-001 | [Qué quedó decidido] | [Opciones evaluadas] | [Por qué esta] | [Especificación / Fase NN / Hallazgo durante la implementación] |

## Referencias

- [`GUIA-AGENTE.md`](../GUIA-AGENTE.md) — reglas de redacción, flujo de trabajo y gates de cierre.
- [`CONSTITUCION.md`](../CONSTITUCION.md) — principios innegociables que acotan las soluciones admisibles.
- [`00-plan-general.md`](00-plan-general.md) — enfoque técnico y descomposición en fases derivados de esta especificación.
- [Documento, informe, diagrama, item de catálogo o URL que sustenta el problema]
- [Documentación oficial consultada para verificar comportamiento de plataformas o APIs]
- [Plan relacionado]
