# ID-003 — Fase 01: Diseño del Game Day

## Identificación

| Campo | Detalle |
|---|---|
| **Plan** | ID-003 — Game Day de caos local |
| **Fase** | 01 — Diseño del Game Day |
| **Estado** | Pendiente |
| **Requisitos que cubre** | RF-001, RF-002, RF-003, RNF-001, RNF-002, RNF-004 |
| **Sistemas y repositorios** | APIs catálogo y pedidos del proyecto actual; laboratorio local aislado |
| **Dependencias previas** | Especificación y plan general aprobados; contratos actuales del README y del código |
| **Habilita a** | Fases 02 y 03 |

## Objetivo

Disponer de tres hipótesis falsables y tres diseños de experimento con impacto, duración, indicadores, aborto y reversión definidos. El experimento de latencia quedará listo para una implementación local posterior, sin anticipar resultados.

## Contexto de la fase

Pedidos consulta catálogo antes de persistir una orden. La implementación actual limita esa consulta a cinco segundos y traduce el timeout a `504` con `error.code=catalog_timeout`; readiness de pedidos también consulta catálogo y puede degradarse durante el ensayo. Estos hechos provienen de `services/orders/app/main.py` y del [README](../../README.md). Los umbrales siguientes son hipótesis del laboratorio, no SLO de producción.

## Alcance técnico

### Cambios previstos

| Ubicación | Cambio | Requisito asociado |
|---|---|---|
| Diseño del Game Day | Formalizar hipótesis y experimentos E1, E2 y E3 | RF-001, RF-002 |
| Contrato de evidencia | Definir indicadores y correlación por experimento | RF-003, RNF-004 |
| Procedimiento del laboratorio | Acotar fallos y documentar aborto y reversión | RNF-001, RNF-002 |

### No incluido en esta fase

- Implementación del inyector o despliegue del laboratorio, correspondientes a la fase 02.
- Ejecución de E2 o E3; únicamente E1 se ejecutará manualmente en la fase 04.
- Cambios en contratos HTTP, esquemas de datos, timeouts de las APIs o infraestructura remota.

## Diseño

Las hipótesis conservan el formato exigido:

- **H1:** En estado estable, cuando se añaden seis segundos de latencia al tráfico de pedidos hacia catálogo durante sesenta segundos, esperamos que las creaciones respondan `504 catalog_timeout` alrededor del límite de cinco segundos sin persistir pedidos fallidos, mientras las lecturas independientes continúan disponibles.
- **H2:** En estado estable, cuando catálogo tiene un trabajador de CPU al 80 % y una CPU disponible durante sesenta segundos, esperamos que al menos el 99 % de las creaciones de pedidos sean exitosas y su p95 sea inferior a dos segundos.
- **H3:** En estado estable, cuando se descarta el 100 % del tráfico de pedidos hacia catálogo durante treinta segundos, esperamos que las creaciones terminen con timeout controlado, que las lecturas de recursos existentes sigan disponibles y que el servicio se recupere al retirar el fallo.

| Experimento | Tipo, radio de impacto y duración | Reversión automática | Verificación |
|---|---|---|---|
| E1, obligatorio | Latencia de 6 s únicamente a la IP resuelta de catálogo, TCP puerto 8000, desde el espacio de red de pedidos; TTL 60 s | Temporizador independiente retira exclusivamente las reglas creadas por el ensayo; limpieza adicional al interrumpir y comando manual idempotente | H1; POST, lecturas de control, persistencia y spans cliente |
| E2, solo diseño | Agotamiento de CPU en catálogo: un trabajador al 80 %, contenedor limitado a una CPU; TTL 60 s | Tiempo límite independiente termina el proceso de carga, confirma su salida y restaura el límite previo | H2; éxito, p95 y uso de CPU de catálogo |
| E3, solo diseño | Partición dirigida: pérdida 100 % a la misma dependencia de E1; TTL 30 s | Temporizador independiente elimina únicamente las reglas del ensayo y confirma conectividad | H3; timeouts, lecturas, persistencia y recuperación |

El enfoque corresponde conceptualmente a experimentos de Gremlin o Litmus: hipótesis, fallo acotado, observación y reversión. Chaos Monkey ilustra la provocación deliberada de fallos, aunque no se reproducirá su terminación de instancias. No se instalará ninguna de estas plataformas.

La selección dirigida con `tc netem` se basa en su [documentación](https://man7.org/linux/man-pages/man8/tc-netem.8.html); la efectividad exacta de seis segundos sobre este flujo es una hipótesis que debe confirmarse localmente. La inyección no incluye PostgreSQL, OTLP, métricas ni respuestas de las APIs al generador. Se resolverá catálogo al inicio; un cambio de destino cancela el ensayo. Se rechazará la inyección si existen reglas ajenas que no puedan preservarse.

E1 tendrá baseline de 60 s, fallo de 60 s, drenaje de 15 s y recuperación de 60 s. La carga será un POST por segundo con máximo diez solicitudes en vuelo y timeout cliente de ocho segundos. No se reintentará un POST. Cada segundo se consultará el producto sembrado y un pedido sembrado; readiness se comprobará cada cinco segundos y quedará fuera del SLI de negocio.

E2 y E3 conservarán esa carga, baseline, drenaje y recuperación; E3 reduce el fallo a 30 s. E2 aplicaría la cuota de una CPU antes del baseline para comparar bajo la misma capacidad; guardaría la cuota original para restaurarla al terminar. Su SLI incluye todas las creaciones iniciadas durante los 60 s de estrés y sus resultados finales. E3 usaría los mismos criterios porcentuales y temporales de E1 con mínimo diez muestras elegibles. Las órdenes concretas de stress-ng no están verificadas ni forman parte de esta implementación: deberán contrastarse con su documentación oficial si se autoriza ejecutar E2.

Baseline exige 100 % de POST `201`, controles 100 % `200` y p95 inferior a un segundo por operación. La ventana estable del fallo contiene solo solicitudes iniciadas al menos diez segundos después de la inyección y finalizadas antes de la retirada, con al menos treinta muestras elegibles. H1 espera al menos 95 % de `504 catalog_timeout` y al menos 95 % de esas respuestas con duración entre 4,5 y 6,5 s; cero escrituras asociadas a creaciones fallidas; controles con 100 % `200` y p95 inferior a un segundo. En los 60 s de recuperación se espera volver a los criterios de baseline. Los inicios y finales fuera de una ventana se conservan como tránsito y no se reasignan para mejorar resultados.

Se abortará y revertirá ante fallo de liveness, escritura correspondiente a un POST fallido, degradación de operaciones de control, cambio de IP destino o pérdida del temporizador o de la capacidad de limpieza. La degradación de readiness de pedidos durante el fallo se registrará como impacto esperado de su dependencia, sin confundirla con liveness. Si baseline no cumple los criterios, no se inyectará.

### Comportamiento esperado por caso

| Caso | Condición | Resultado esperado |
|---|---|---|
| C-01 | Baseline cumple umbrales y controles de aislamiento | E1 puede comenzar con temporizador activo |
| C-02 | Baseline degradado o reglas ajenas | Inyección rechazada y motivo registrado |
| C-03 | E1 durante ventana estable | `504 catalog_timeout` acotado, sin persistencia fallida; lecturas disponibles |
| C-04 | Readiness de pedidos falla por catálogo | Registrar impacto; distinguirlo de fallo de proceso |
| C-05 | Interrupción o señal de aborto | Retirada inmediata y verificable de reglas propias |
| C-06 | Hipótesis refutada con evidencia completa | Ensayo válido como aprendizaje; no declarar éxito de resiliencia |

## Tareas

Las tareas marcadas con `[P]` pueden ejecutarse en paralelo entre sí; las demás siguen el orden listado.

| Estado | # | Tarea | Criterio de aceptación |
|---|---|---|---|
| [ ] | 1 | Contrastar hipótesis con código y contratos actuales | H1–H3 distinguen hechos del sistema de umbrales propuestos |
| [ ] | 2 | `[P]` Consolidar diseños de E1–E3 | Cada diseño contiene tipo, radio, duración y reversión automática |
| [ ] | 3 | `[P]` Consolidar indicadores y política de aborto | Indicadores calculables y eventos de aborto inequívocos |
| [ ] | 4 | Revisar Gate 2 y transferir contratos a fases 02 y 03 | Sin ambigüedades que impidan implementar E1 |

## Validación

| Estado | Tipo | Qué verifica | Cómo se ejecuta | Resultado esperado |
|---|---|---|---|---|
| Pendiente | Estática | RF-001, RF-002 y RF-003 | Revisar H1–H3 y tabla E1–E3 contra `00-especificacion.md` | Tres hipótesis, tres diseños e indicadores trazables |
| No aplica a esta fase | Automatizada futura | RNF-004: clasificación temporal | Pruebas transferidas a fase 03; no condicionan el cierre del diseño | Casos de límites especificados para la implementación |
| No aplica a esta fase | Funcional / operativa | H1 y aislamiento | Ejecución delegada a fase 04; no condiciona el cierre del diseño | Diseño transferido; resultados operativos pendientes en fase 04 |
| Pendiente | Revisión de reversión | RNF-002 | Revisar TTL y procedimiento de retirada de E1–E3 | Diseño acotado; prueba real de reversión en fases 02 y 04 |

Los comandos son interfaces futuras, no utilidades ya existentes. Mientras exista validación funcional pendiente tras implementar, el estado de la fase será `Implementada sin validar`; actualmente permanece `Pendiente`.

## Riesgos y bloqueantes de la fase

| Estado | Elemento | Impacto | Mitigación o siguiente acción |
|---|---|---|---|
| Abierto | La latencia observada depende del flujo y temporización reales | Medio | Medir efecto y comparar sin ajustar resultados retrospectivamente |
| Abierto | Una regla amplia afectaría tráfico de control | Alto | Filtro por destino y puerto, rechazo de reglas ajenas y aborto |
| Abierto | Reversión dependiente del generador | Alto | Temporizador independiente antes de activar el fallo |

## Cierre de la fase

Sección pendiente de ejecutar el Gate 3 de [GUIA-AGENTE.md](../GUIA-AGENTE.md).

- **Resultado obtenido:** No implementado: entrega actual de planificación documental.
- **Desviaciones respecto al diseño:** Ninguna registrada; no se ha ejecutado el diseño.
- **Decisiones tomadas durante la fase:** Ninguna de implementación; las decisiones de planificación se registran en la especificación.
- **Requisitos afectados en su cobertura:** RF-001, RF-002, RF-003, RNF-001, RNF-002 y RNF-004 planificados; validación pendiente.
- **Actualizaciones aplicadas a `00-plan-general.md`:** Fase planificada con estado Pendiente.
- **Actualizaciones aplicadas a `00-especificacion.md`:** Ningún cambio de requisito derivado de ejecución.
- **Pendientes trasladados:** Implementación del laboratorio a fase 02; evidencia y pruebas a fase 03; ejecución real a fase 04.
