# [ID] — Fase [N]: [Nombre de la fase]

> **Uso:** se duplica este archivo por cada fase, renombrándolo con su número real a partir de `01` (por ejemplo `01-preparacion.md`). Cada fase debe poder implementarse leyendo únicamente este archivo, `00-especificacion.md` y `00-plan-general.md`. Redacción impersonal; sin estado de repositorio (ver [`GUIA-AGENTE.md`](../GUIA-AGENTE.md)).
>
> **Al terminar la fase se ejecuta el Gate 3 de `../GUIA-AGENTE.md` y se actualizan este archivo y `00-plan-general.md`. Una fase no está terminada hasta que los documentos reflejan lo que realmente ocurrió.**

## Identificación

| Campo | Detalle |
|---|---|
| **Plan** | [ID — título del plan] |
| **Fase** | [Número y nombre] |
| **Estado** | [Pendiente / En curso / Implementada sin validar / Completada / Bloqueada / No implementada] |
| **Requisitos que cubre** | [RF-001, RNF-002] |
| **Sistemas y repositorios** | [Ubicaciones afectadas] |
| **Dependencias previas** | [Fases, prerequisitos operativos o `Ninguna`] |
| **Habilita a** | [Fases que dependen de esta o `Ninguna`] |

## Objetivo

[El resultado verificable que entrega esta fase, en una o dos frases. Formulado como estado final observable, no como lista de actividades.]

## Contexto de la fase

[Por qué esta fase es necesaria dentro del plan, qué parte del problema resuelve y qué hallazgo o restricción condiciona su implementación. Solo lo que se necesita para implementarla; el contexto general vive en la especificación.]

## Alcance técnico

### Cambios previstos

| Ubicación | Cambio | Requisito asociado |
|---|---|---|
| `[ruta o componente]` | [Comportamiento que debe quedar implementado ahí] | [RF-00N] |
| `[ruta o componente]` | [Comportamiento] | [RF-00N] |

### No incluido en esta fase

- [Límite explícito de la fase]
- [Trabajo delegado a otra fase, con referencia]

## Diseño

[Contrato, flujo de datos, secuencia o regla de negocio que se implementa. Se incluye un fragmento de código solo cuando el contrato no se entiende sin él, y se mantiene mínimo. Se incluye un diagrama solo si aclara una secuencia que la prosa no transmite.]

### Comportamiento esperado por caso

| Caso | Condición | Resultado esperado |
|---|---|---|
| [C-001] | [Entrada o estado] | [Salida, código de respuesta o efecto observable] |
| [C-002] | [Entrada de error] | [Rechazo esperado y mensaje] |

## Tareas

Las tareas marcadas con `[P]` pueden ejecutarse en paralelo entre sí; las demás siguen el orden listado.

| Estado | # | Tarea | Criterio de aceptación |
|---|---|---|---|
| [ ] | 1 | [Acción concreta sobre una ubicación identificada] | [Cómo se comprueba que quedó hecha] |
| [ ] | 2 | `[P]` [Acción concreta] | [Criterio verificable] |
| [ ] | 3 | `[P]` [Acción concreta] | [Criterio verificable] |
| [ ] | 4 | [Acción concreta] | [Criterio verificable] |

## Validación

| Estado | Tipo | Qué verifica | Cómo se ejecuta | Resultado esperado |
|---|---|---|---|---|
| [Pendiente / Aprobada / Fallida: (detalle)] | Automatizada | [RF-00N] | `[comando exacto]` | [Salida esperada] |
| [Pendiente / Aprobada] | Estática | [Esquema, sintaxis, tipos, existencia de archivos] | `[comando exacto]` | [Resultado esperado] |
| [Pendiente de confirmación / Confirmada: (resultado)] | Funcional / operativa | [RF-00N end-to-end] | [Pasos exactos, endpoint o flujo; queda para ejecución manual] | [Resultado observable esperado] |
| [Pendiente / Aprobada / No aplica] | Reversión | [Que el cambio se pueda deshacer] | [Pasos] | [Estado previo restaurado] |

Mientras exista validación funcional pendiente de confirmación, el estado de la fase es `Implementada sin validar`.

## Riesgos y bloqueantes de la fase

| Estado | Elemento | Impacto | Mitigación o siguiente acción |
|---|---|---|---|
| [Abierto / Resuelto: (cómo)] | [Riesgo, dependencia o bloqueante concreto de esta fase] | [Alto / Medio / Bajo] | [Acción] |

## Cierre de la fase

Sección que se completa al ejecutar el **Gate 3**. Si algo de esto queda vacío, la fase no está cerrada.

- **Resultado obtenido:** [Implementado y validado / Implementado sin validar / Parcial: (qué falta) / No implementado: (motivo)]
- **Desviaciones respecto al diseño:** [Ninguna, o qué se hizo distinto y por qué]
- **Decisiones tomadas durante la fase:** [Ids de la bitácora de `00-especificacion.md` o `Ninguna`]
- **Requisitos afectados en su cobertura:** [RF-00N: implementado / validado / no cubierto y motivo]
- **Actualizaciones aplicadas a `00-plan-general.md`:** [Estado de la fase, riesgos, prerequisitos, resumen de estado]
- **Actualizaciones aplicadas a `00-especificacion.md`:** [Ninguna, o qué requisito o caso cambió por lo aprendido al implementar]
- **Pendientes trasladados:** [A qué fase, o declarados como pendientes abiertos del plan, o `Ninguno`]
