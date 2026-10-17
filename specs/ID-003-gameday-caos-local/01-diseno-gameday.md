# ID-003 — Fase 01: Diseño del Game Day

## Identificación

| Campo | Detalle |
|---|---|
| **Plan** | ID-003 — Game Day de caos local |
| **Fase** | 01 — Diseño del Game Day |
| **Estado** | Completada |
| **Requisitos que cubre** | RF-001, RF-002, RF-003, RNF-001, RNF-002, RNF-004 |
| **Sistemas y repositorios** | APIs catálogo y pedidos del proyecto actual; laboratorio local aislado |
| **Dependencias previas** | Especificación y plan general aprobados; contratos actuales del README y del código |
| **Habilita a** | Fases 02 y 03 |

## Objetivo

Disponer de tres hipótesis falsables y tres diseños de experimento con impacto, duración, indicadores, aborto y reversión definidos. El experimento de latencia quedará listo para una implementación local posterior, sin anticipar resultados.

## Contexto de la fase

Pedidos consulta catálogo antes de persistir una orden. La implementación actual limita esa consulta a cinco segundos y traduce el timeout a `504` con `error.code=catalog_timeout`; readiness de pedidos también consulta catálogo y puede degradarse durante el ensayo. Estos hechos provienen de `services/orders/app/main.py` y del [README](../../README.md). Los umbrales siguientes son hipótesis del laboratorio, no SLO de producción.

El entregable de esta fase es el diseño revisado. Su cierre no acredita ejecución, capacidades del daemon ni resiliencia observada. Las validaciones operativas pertenecen a las fases 02–04.

| Hecho contrastado localmente | Fuente | Consecuencia para el diseño |
|---|---|---|
| Consulta de producto limitada a 5 s y timeout traducido a 504 | [get_catalog_product](../../services/orders/app/main.py#L106) | Diferenciar timeout controlado de errores 502/503 y del timeout del generador |
| Consulta al producto antes de construir y guardar pedido | [create_order](../../services/orders/app/main.py#L143) | Comprobar ausencia de escritura cuando falla la dependencia |
| Readiness consulta catálogo con límite de 2 s | [ready](../../services/orders/app/main.py#L211) | Registrar readiness 503 como impacto esperado durante E1/E3, sin usarla como liveness |
| Logs contienen request_id, estado, duración y contexto de traza si existe | [Middleware JSON](../../services/orders/app/observability.py#L40) | Tomar error.code de la respuesta, no suponerlo en el log |
| Benchmark actual hace GET de producto y pedido existentes | [Carga de overhead](../../scripts/benchmark/overhead.js) | Crear carga POST específica para ejercitar pedidos → catálogo |
| Collector usa debug básico y batch | [Configuración actual](../../docker/otel-collector/config.yaml) | Fase 03 requiere configuración propia detallada y captura antes del apagado |

Los fragmentos de línea de estas referencias localizan el código inspeccionado; no sustituyen su revisión si cambia la implementación.

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

### Indicadores y señales por hipótesis

El universo de negocio se separa por operación: POST /orders, GET /products/{id} y GET /orders/{id}. Cada intento cuenta una vez; no se reintentan POST. La disponibilidad es respuestas esperadas divididas por intentos, incluidos errores de transporte como fallos. Se reportan siempre numerador y denominador. El p95 es el elemento `ceil(0,95 × N)` de las duraciones ordenadas, contando timeouts del cliente; sin muestras no es evaluable. Duración monotónica para cálculo y UTC para correlación.

| Hipótesis | SLI y ventana | Criterio de evaluación | Logs, trazas y evidencia de fallo |
|---|---|---|---|
| H1 | 504 con error.code catalog_timeout / POST elegibles durante fallo estable | >=95 %; mínimo 30 intentos elegibles | Respuesta registrada en requests.jsonl; log de pedidos por request_id; span cliente HTTP y span de negocio orders.order.create; activación y contadores de filtro |
| H1 | 504 catalog_timeout de duración 4,5–6,5 s / 504 catalog_timeout elegibles | >=95 %; denominador cero es inconcluso | Duración monotónica del generador y duration_ms del log; error del span cliente como señal diagnóstica |
| H2 | POST 201 / intentos iniciados durante 60 s de estrés; p95 de esos intentos hasta su finalización | >=99 % y p95 <2 s; 60 intentos programados, ninguno omitido | CPU de catálogo cada 5 s, identidad y vida del proceso de estrés, cuota aplicada; logs y spans de catálogo y cliente pedidos |
| H3 | Los dos indicadores de timeout de H1 sobre ventana estable de 30 s | Mismos umbrales >=95 %; mínimo 10 intentos elegibles | Eventos y contadores de pérdida dirigida; respuesta 504, log de pedidos y span cliente; ausencia de span servidor no demuestra por sí sola la partición |
| H1, H2, H3 | 200 / intentos de cada GET de control; p95 de cada operación por ventana | 100 % y p95 <1 s | requests.jsonl y logs de ambas APIs; tráfico directo del generador queda fuera del filtro |
| H1, H2, H3 | Pedidos finales menos pedidos iniciales menos POST 201 de toda la corrida | Exactamente cero; UUID retornados presentes y sin escritores ajenos | Listados paginados antes/después y UUID de cada creación exitosa; incluye transiciones y solicitudes drenadas |
| H1, H2, H3 | Primera readiness 200 tras retirada y SLI de recuperación de 60 s tras drenaje | Readiness en <=60 s desde retirada; POST 100 % 201, controles 100 % 200 y p95 <1 s por operación | Eventos de retirada, sondeos cada 5 s, respuestas y logs; registrar resolución de medida y primer POST exitoso |

H2 tiene como objetivo de fallo un trabajador configurado al 80 %, no una garantía de 80 % de CPU observada. La cuota de una CPU se aplica antes de su baseline; se conservan la cuota previa y el objetivo de carga para comprobar reversión. Si faltan pruebas de que el estrés o la pérdida estuvieron activos, no se puede aceptar ni refutar la hipótesis correspondiente.

Los spans servidor y cliente se correlacionan por trace_id cuando la petición alcanza catálogo. El contexto de traza del log puede faltar y debe quedar visible como limitación; el UUID request_id permite emparejar respuesta y log. La duración del cliente, la del servidor y la del span no se consideran idénticas. No se exige span servidor de catálogo para una solicitud que no llegó.

### Reglas de evaluación, aborto y transferencia

Los límites temporales son intervalos semiabiertos: inicio incluido y fin excluido. La ventana estable empieza diez segundos después de confirmar activación y termina al retirar las reglas. Los intentos que la cruzan conservan su fase de inicio y se reportan además como transición; no se descartan de resultados globales ni de conciliación de persistencia. Las muestras elegibles solo incluyen intentos iniciados en esa ventana y terminados antes de retirada. Menos de treinta muestras en E1, o diez en E3, da resultado inconcluso. La omisión de carga programada también invalida el ensayo.

Un error HTTP o de transporte en cualquier lectura de control, o un fallo de liveness de cualquiera de las APIs, activa aborto inmediato. Para latencia de controles se evalúa p95 acumulado por operación en la ventana actual desde veinte muestras; p95 >=1 s activa aborto. Si no hay veinte muestras, los datos se conservan para evaluación final. Readiness se sondea cada cinco segundos con timeout de ocho segundos y no activa aborto por sí sola durante el fallo. Liveness usa la misma frecuencia y timeout, en sondeos independientes de readiness. El vencimiento del timeout de un sondeo cuenta como fallo.

Una discrepancia de persistencia detectada, un cambio del destino o la pérdida de la garantía de retirada activa aborto y limpieza sin esperar análisis final. El incumplimiento de la tasa de 504, por sí solo y con controles sanos, refuta H1/H3 sin obligar a cortar el ensayo. Una ejecución abortada no puede presentarse como confirmación del ciclo completo de recuperación.

En E1/E3 el temporizador se arma antes del fallo; las reglas llevan identidad propia y no sustituyen reglas ajenas. Se exige retirada verificada como máximo cinco segundos después del TTL con infraestructura operativa. E1 añade una concesión de diez segundos renovada por el runner, cuyo vencimiento debe limpiar en no más de quince segundos desde la última renovación. E2 requeriría supervisor independiente que termine únicamente el proceso identificado, compruebe su salida y restaure la cuota; no basta con terminar el generador de solicitudes. La caída del daemon o del auxiliar impide garantizar estos plazos y exige declarar el resultado inconcluso hasta comprobar limpieza.

| Destino | Contrato transferido | Condición para avanzar |
|---|---|---|
| Fase 02 | Solo E1 ejecutable; filtro IPv4 TCP destino catálogo:8000, TTL 60 s, carga y controles de este diseño | Preflight local, identidad de proyecto y ausencia de reglas ajenas; watchdog independiente |
| Fase 03 | Fórmulas, ventanas, mínimo de muestras y correlación; requests.jsonl como fuente canónica | Analizador sin dependencias de servicios, métricas crudas y logs/trazas capturados |
| Fase 04 | Baseline/fallo/drenaje/recuperación de 60/60/15/60 s; decisión aceptada/refutada/inconclusa | Fases 02 y 03 implementadas y reversión comprobada manualmente |

### Revisión de entrada al diseño y a la implementación

| Gate | Comprobación documental | Resultado |
|---|---|---|
| 1 | Requisitos con criterio verificable, alcance delimitado y aclaraciones resueltas | Aprobado para este diseño; sin cambios de contrato |
| 2 | RF-001 a RF-009 y RNF-001 a RNF-005 asignados a fases | Aprobado: matriz de cobertura del plan general |
| 2 | Dependencias y trabajo paralelo definidos | Aprobado: fases 02 y 03 pueden avanzar tras este cierre; fase 04 depende de ambas |
| 2 | Diseño transferible sin contexto conversacional | Aprobado: hipótesis, carga, evidencia y aborto definidos en documentos |
| 2 | Prerequisitos y decisiones identificados | Aprobado documentalmente; daemon, netem, baseline y reversión siguen pendientes de confirmación operativa |

Este gate habilita implementar el harness; no autoriza afirmar que sus prerequisitos operativos ya se cumplen. La documentación oficial consultada para el plan se reutiliza sin nuevas consultas remotas: [tc-netem](https://man7.org/linux/man-pages/man8/tc-netem.8.html), [redes Compose](https://docs.docker.com/compose/how-tos/networking/) y [debug detallado de Collector](https://opentelemetry.io/docs/collector/troubleshooting/). No hay validación oficial de comandos de stress-ng en este alcance y no se ejecutarán.

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
| [x] | 1 | Contrastar hipótesis con código y contratos actuales | H1–H3 distinguen hechos del sistema de umbrales propuestos; fuentes enlazadas |
| [x] | 2 | `[P]` Consolidar diseños de E1–E3 | Cada diseño contiene tipo, radio, duración y reversión automática |
| [x] | 3 | `[P]` Consolidar indicadores y política de aborto | Fórmulas, muestras, ventanas, señales y eventos de aborto explícitos |
| [x] | 4 | Revisar Gate 2 y transferir contratos a fases 02 y 03 | Gates documentales revisados y contratos transferidos; prerequisitos operativos pendientes |

## Validación

| Estado | Tipo | Qué verifica | Cómo se ejecuta | Resultado esperado |
|---|---|---|---|---|
| Aprobada | Estática | RF-001, RF-002 y RF-003 | Revisión de H1–H3, E1–E3 y matriz SLI contra especificación y fuentes locales | Tres hipótesis, tres diseños e indicadores trazables; sin afirmar resultados reales |
| No aplica a esta fase | Automatizada futura | RNF-004: clasificación temporal | Pruebas transferidas a fase 03; no condicionan el cierre del diseño | Casos de límites especificados para la implementación |
| No aplica a esta fase | Funcional / operativa | H1 y aislamiento | Ejecución delegada a fase 04; no condiciona el cierre del diseño | Diseño transferido; resultados operativos pendientes en fase 04 |
| Aprobada para diseño | Revisión de reversión | RNF-002 | Revisar TTL, supervisor y procedimiento de retirada de E1–E3 | Diseño acotado; prueba real de reversión en fases 02 y 04 |

La fase queda `Completada` respecto a su entregable de diseño, cuyas validaciones son estáticas. No tiene validación funcional propia pendiente; las pruebas del harness y del experimento se conservan abiertas en sus fases respectivas. No se crean scripts ni se ejecutan servicios en este cierre.

## Riesgos y bloqueantes de la fase

| Estado | Elemento | Impacto | Mitigación o siguiente acción |
|---|---|---|---|
| Trasladado a fases 02 y 04 | La latencia observada depende del flujo y temporización reales | Medio | Medir efecto y comparar sin ajustar resultados retrospectivamente |
| Resuelto en diseño; prueba pendiente en fase 02 | Una regla amplia afectaría tráfico de control | Alto | Filtro por destino y puerto, rechazo de reglas ajenas y aborto |
| Resuelto en diseño; prueba pendiente en fase 02 | Reversión dependiente del generador | Alto | Temporizador independiente antes de activar el fallo |

## Cierre de la fase

Gate 3 aplicado al entregable documental de fase 01 conforme a [GUIA-AGENTE.md](../GUIA-AGENTE.md).

- **Resultado obtenido:** Diseño implementado y validado estáticamente; fase completada sin ejecución operativa.
- **Desviaciones respecto al diseño:** Ninguna de alcance. Se precisan denominadores, cortes temporales, condiciones de aborto y límites de reversión para evitar decisiones implícitas al implementar.
- **Decisiones tomadas durante la fase:** D-008: cierre documental independiente de la validación operativa; D-009: reglas de evaluación y aborto explícitas.
- **Requisitos afectados en su cobertura:** RF-001 validado documentalmente; RF-002 y RF-003 con diseño validado, pendientes de harness/captura en fases 02 y 03. RNF-001, RNF-002 y RNF-004 revisados en diseño, sin validación operativa.
- **Actualizaciones aplicadas a `00-plan-general.md`:** Fase 01 completada, cobertura y resumen actualizados; riesgos de ejecución trasladados a fases posteriores.
- **Actualizaciones aplicadas a `00-especificacion.md`:** Decisiones D-008 y D-009; requisitos y alcance funcional preservados.
- **Pendientes trasladados:** Harness, preflight y prueba de reversión a fase 02; captura y analizador a fase 03; corrida real y conclusiones a fase 04; informe empírico y PDF a fase 05.
