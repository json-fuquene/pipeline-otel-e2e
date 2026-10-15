# [ID] — Plan general: [Título]

> **Uso:** este documento describe **cómo** se construye lo definido en [`00-especificacion.md`](00-especificacion.md): enfoque técnico, descomposición en fases y control de estado. Redacción impersonal; sin estado de repositorio (ver [`GUIA-AGENTE.md`](../GUIA-AGENTE.md)).
>
> Antes de implementar se ejecuta el **Gate 2** de `../GUIA-AGENTE.md`. Al cerrar cada fase se ejecuta el **Gate 3** y este archivo se actualiza.

## Identificación

| Campo | Detalle |
|---|---|
| **ID** | [ID-000] |
| **Título** | [Título del plan] |
| **Sprint / iteración** | [Sprint o `No documentado`] |
| **Prioridad** | [Alta / Media / Baja] |
| **Estado global** | [En análisis / En implementación / Implementado sin validar / Validado / Cerrado / Bloqueado] |
| **Sistemas y repositorios afectados** | [Ubicaciones donde se aplica el cambio] |
| **Iniciativas relacionadas** | [IDs y tipo de relación] |

## Resumen de estado

[Dos o tres frases con el estado real: qué quedó implementado, qué quedó validado y qué sigue abierto. Se actualiza al cerrar cada fase. No se declara cierre integral si queda alguna fase, validación o bloqueante abierto.]

## Enfoque técnico

[Cómo se resuelve el problema: mecanismo elegido, dónde se intercepta el flujo, qué componentes participan y cómo encaja con lo que ya existe. Las decisiones con alternativas van a la bitácora de `00-especificacion.md`.]

```mermaid
flowchart LR
  A[Origen] --> B[Proceso]
  B --> C[Resultado]
```

[El diagrama se incluye solo cuando aclara integraciones, secuencias o decisiones que la prosa no transmite; en caso contrario se elimina.]

## Contratos e interfaces afectados

| Elemento | Ubicación | Cambio | Compatibilidad hacia atrás |
|---|---|---|---|
| [Endpoint, función, esquema, parámetro o archivo de configuración] | `[ruta o componente]` | [Qué cambia en su comportamiento o firma] | [Compatible / Requiere migración / Ruptura controlada] |

## Fases de ejecución

| Estado | # | Documento | Requisitos que cubre | Sistemas | Resultado esperado |
|---|---|---|---|---|---|
| [Pendiente / En curso / Implementada sin validar / Completada / Bloqueada / No implementada] | 1 | [01-nombre-fase.md](01-nombre-fase.md) | [RF-001, RNF-001] | [Ubicaciones] | [Resultado verificable] |
| [Estado] | 2 | [02-nombre-fase.md](02-nombre-fase.md) | [Ids] | [Ubicaciones] | [Resultado] |
| [Estado] | N | [NN-nombre-fase.md](NN-nombre-fase.md) | [Ids] | [Ubicaciones] | [Resultado] |

## Cobertura de requisitos

Cada requisito de la especificación aparece aquí con la fase que lo cubre. Un requisito sin fase asignada es un hueco de descomposición y se resuelve antes de implementar.

| Estado de cobertura | Requisito | Fase que lo cubre |
|---|---|---|
| [Pendiente / Implementado / Validado / No cubierto: (motivo)] | RF-001 | [Fase N] |
| [Estado] | RNF-001 | [Fase N] |

## Dependencias y orden de ejecución

[Qué fase bloquea a cuál y por qué (el motivo técnico, no solo el orden), qué fases pueden avanzar en paralelo y qué condición debe cumplirse antes de avanzar a cada una.]

## Prerequisitos operativos

Condiciones externas al cambio que deben existir para poder implementar o validar.

| Estado | Prerequisito | Tipo | Impacto si falta |
|---|---|---|---|
| [Pendiente / Confirmado / No requerido] | [Permiso, secreto, infraestructura, acceso, configuración o decisión externa] | [Acceso / Infraestructura / Configuración / Decisión] | [Bloquea la fase N / Limita el alcance / No bloquea] |

## Riesgos y limitaciones

| Riesgo o limitación | Detalle | Impacto | Mitigación o decisión | Bloqueante |
|---|---|---|---|---|
| [Riesgo] | [Por qué existe y qué escenario lo dispara] | [Alto / Medio / Bajo] | [Mitigación aplicada, decisión registrada o seguimiento] | [Sí / No] |

## Estrategia de validación

| Estado | Nivel | Qué cubre | Ejecución |
|---|---|---|---|
| [Pendiente / Aprobada] | Automatizada / estática | [Pruebas unitarias, lint, typecheck, validación de esquema] | Directa |
| [Pendiente de confirmación / Confirmada] | Funcional / operativa | [Flujo end-to-end, integración con sistemas reales, despliegue] | Manual, con resultado confirmado y registrado |
| [Pendiente / Aprobada / No aplica] | Reversión y compatibilidad | [Cómo se revierte y qué se comprueba] | [Según corresponda] |

## Criterios de cierre del plan

- [ ] Todas las fases en estado `Completada`, o con su desviación declarada de forma explícita.
- [ ] Todos los requisitos obligatorios de la especificación cubiertos y validados.
- [ ] Validación automatizada aprobada.
- [ ] Validación funcional confirmada y su resultado registrado.
- [ ] Sin bloqueantes abiertos, o bloqueantes restantes declarados con su impacto.
- [ ] Sin aclaraciones abiertas en `00-especificacion.md`.
- [ ] Revisión general (Gate 4) ejecutada e `99-informe-final.md` escrito.

## Referencias

- [`00-especificacion.md`](00-especificacion.md) — requisitos, casos, supuestos y bitácora de decisiones.
- [`CONSTITUCION.md`](../CONSTITUCION.md) — principios que gobiernan las decisiones de este plan.
- [Documentación oficial consultada, plan relacionado, diagrama o informe]
