# ID-003 — Especificación: Game Day de caos local

## Identificación

| Campo | Detalle |
|---|---|
| **ID** | ID-003 |
| **Título** | Game Day de caos local |
| **Origen** | [Requerimientos](../../requerimientos.md) y alcance documental acordado |
| **Sprint / iteración** | No documentado |
| **Estado de la especificación** | Aprobada; fase 01 completada, fases 02 y 03 implementadas sin validación operativa |
| **Iniciativas relacionadas** | ID-001: servicios y persistencia; ID-002: instrumentación reutilizada |

## Problema

Catálogo y pedidos disponen de manejo de errores e instrumentación, pero no existe un procedimiento de Game Day que contraste su comportamiento ante fallos controlados. La creación de pedidos depende de una consulta HTTP a catálogo; todavía no se ha demostrado mediante este plan qué ocurre con la latencia, las escrituras y la recuperación cuando esa dependencia se degrada.

El benchmark existente consulta productos y pedidos ya creados, por lo que no verifica la dependencia ejercitada al crear un pedido. Las evidencias de iniciativas previas no sustituyen una ejecución de caos local.

## Resultado esperado

Disponer de tres hipótesis falsables y sus experimentos, con impacto acotado, observabilidad y reversión. Una ejecución local posterior permitirá comparar resultados reales antes, durante y después del fallo, identificar una debilidad respaldada por evidencia y proponer una remediación verificable.

La entrega inicial comprendió documentación Markdown. Las fases 02 y 03 incorporan el harness, captura de telemetría y análisis offline con pruebas unitarias, sin ejecutar el experimento ni producir evidencia operativa real. El PDF original se mantiene diferido y las capturas se incorporarán manualmente.

## Actores y sistemas involucrados

| Actor o sistema | Rol en el flujo | Qué cambia para él |
|---|---|---|
| Operador del Game Day | Preparación, aborto y confirmación de resultados locales | Procedimiento reproducible y criterios explícitos |
| Catálogo | Dependencia de productos | Objetivo de los tres fallos diseñados |
| Pedidos | Consumidor HTTP y persistencia de pedidos | Verificación de errores, aislamiento y recuperación |
| PostgreSQL | Persistencia en esquemas separados | Verificación de integridad sin alterar permisos |
| Telemetría | Correlación de solicitudes y diagnóstico | Evidencia conservada por ejecución |

## Requisitos funcionales

| Id | Requisito | Criterio de aceptación | Prioridad |
|---|---|---|---|
| RF-001 | Formular tres hipótesis de fallo | Tres enunciados «En estado estable, cuando [condición], esperamos que [comportamiento del sistema]», con indicadores y umbrales definidos | Obligatorio |
| RF-002 | Diseñar un experimento por hipótesis | Cada ficha declara tipo, objetivo, radio, duración, reversión automática, aborto y relación conceptual con una herramienta de caos | Obligatorio |
| RF-003 | Definir observabilidad por hipótesis | SLI con fórmula, ventana, fuente y umbral; logs/trazas que permitan confirmar o refutar el comportamiento | Obligatorio |
| RF-004 | Disponer de un experimento local ejecutable | Inyección de latencia acotada, retirada automática y procedimiento de emergencia verificables | Obligatorio |
| RF-005 | Registrar resultados reales | Una ejecución identificada con baseline, fallo, recuperación, carga, configuración y evidencia de limpieza | Obligatorio |
| RF-006 | Contrastar esperado frente a obtenido | Cada afirmación se vincula con una medición; hipótesis aceptada, refutada o inconclusa y debilidad identificada solo si la evidencia lo permite | Obligatorio |
| RF-007 | Proponer remediación y aprendizaje SRE | Acción asociada al hallazgo, prioridad, criterio verificable y propuesta de repetición del Game Day | Obligatorio |
| RF-008 | Entregar informe en Markdown | Hipótesis, experimentos, métricas, resultados, reflexión y referencias; capturas manuales vinculadas solo cuando existan | Obligatorio |
| RF-009 | Conservar el entregable original en PDF | Documento final de 4–5 páginas con el contenido requerido; producción diferida por alcance actual, sin declararlo cumplido | Obligatorio del requerimiento original; diferido |

Los ejemplos de formato de RF-001 no son aclaraciones pendientes. Los enunciados concretos se especifican en la fase 01.

## Requisitos no funcionales

| Id | Categoría | Requisito | Criterio de aceptación |
|---|---|---|---|
| RNF-001 | Aislamiento | Operar exclusivamente en un laboratorio local separado de los datos existentes | Proyecto y volumen propios, publicación loopback, sin nube ni cambios de red del host |
| RNF-002 | Reversibilidad | Acotar y retirar el fallo aunque termine el generador de carga | Temporizador independiente armado antes de la inyección; limpieza por tiempo, aborto y repetición sin efectos adicionales |
| RNF-003 | Datos y secretos | Conservar datos previos y evitar exposición de credenciales | Sin borrado de volúmenes, sin secretos en evidencia y sin modificaciones a permisos o esquemas de aplicación |
| RNF-004 | Reproducibilidad | Conservar condiciones y evidencia suficientes | Identificador único, versiones, tiempos UTC, configuración saneada, conteos y archivos fuente; ninguna medición inventada |
| RNF-005 | Validación | Diferenciar análisis estático, pruebas unitarias y validación operativa | Estados separados; builds, servicios y experimento quedan para ejecución manual confirmada |

## Casos y comportamiento esperado

| Id | Caso | Condición de entrada | Comportamiento esperado |
|---|---|---|---|
| C-001 | Estado estable | APIs listas y datos exclusivos sembrados | Creaciones y lecturas correctas antes de inyectar |
| C-002 | Dependencia lenta | Retraso superior al límite de consulta | Error controlado, sin persistencia del pedido fallido |
| C-003 | Recuperación | Fallo retirado y solicitudes en tránsito drenadas | Creaciones y readiness recuperados sin reiniciar APIs |
| C-004 | Cancelación o interrupción | Aborto o pérdida del proceso de carga | Retirada acotada y comprobación de reglas ausentes |
| C-005 | Precondición insegura | Destino ambiguo, reglas ajenas o baseline inválido | No inyectar; conservar diagnóstico |
| C-006 | Evidencia incompleta | Solicitudes omitidas, trazas ausentes o limpieza no comprobada | Resultado inconcluso o fallo operativo; no afirmar validación completa |
| C-007 | Hipótesis refutada | Experimento válido y umbral incumplido | Registrar hallazgo y remediación; no ocultar resultados |
| C-008 | Informe sin ejecución | Solo existe planificación | Declarar resultados pendientes; no reutilizar mediciones de otros ensayos |

## Supuestos

| Verificado | Id | Supuesto | Impacto si resulta falso |
|---|---|---|---|
| Sí, código de pedidos | S-001 | Consulta de catálogo limitada a 5 s; readiness a 2 s | Revisar hipótesis y ventanas si cambia el contrato |
| Sí, README y Compose | S-002 | Entorno actual con dos APIs, PostgreSQL y Collector local | Ajustar laboratorio si cambia la topología |
| Sí, configuración del Collector | S-003 | El exportador local actual resume datos y no ofrece búsqueda persistente de trazas | Capturar explícitamente evidencia detallada |
| No; prerequisito operativo | S-004 | El daemon local permite capacidades de red y netem en contenedores | Bloquea inyección; no sustituirla por retrasos artificiales en la aplicación |
| No; hipótesis de laboratorio | S-005 | La máquina alcanza el baseline con la carga propuesta | Cancelar ensayo y revisar carga mediante decisión registrada |

## Fuera de alcance

- Arranque de servicios, ejecución de experimentos y creación de imágenes durante la validación automática de las fases 02 y 03; quedan para ejecución manual confirmada.
- Ejecución de CPU y partición de red; solo se diseñan sus experimentos.
- AWS, Kubernetes, servicios externos y despliegues remotos.
- Instalación de Chaos Monkey, Gremlin o Litmus; su uso es conceptual.
- Nuevos dashboards, interfaces gráficas de observabilidad, autenticación HTTP, stock o pagos.
- Cambios de contrato HTTP, persistencia, timeouts, reintentos o circuit breaker; las remediaciones se proponen, no se implementan.
- Generación automática de capturas y del PDF en esta entrega.

## Aclaraciones pendientes

| Estado | Id | Pregunta | Bloquea a |
|---|---|---|---|
| Resuelta → D-001 | A-001 | ¿Qué experimento se ejecutará? Latencia con tc netem | Ninguna fase de diseño |
| Resuelta → D-002 | A-002 | ¿Stack gráfico o archivos? Evidencia en archivos | Ninguna fase de diseño |
| Resuelta → D-003 | A-003 | ¿Formato inmediato? Solo Markdown y capturas manuales; PDF diferido | Producción del PDF hasta ampliar alcance |

## Bitácora de decisiones

| Id | Decisión | Alternativas consideradas | Motivo | Origen |
|---|---|---|---|---|
| D-001 | Ejecutar solo latencia con tc netem; diseñar CPU y partición | stress-ng obligatorio; ejecutar los tres | Selección acordada y mínimo del requerimiento | Especificación |
| D-002 | Evidencias en archivos aprovechando OTel existente | Prometheus, Grafana y Jaeger adicionales | Selección acordada; las herramientas gráficas no son exigidas | Especificación |
| D-003 | Entrega inmediata en Markdown; capturas manuales y PDF diferido | HTML imprimible; renderizador automático | Alcance explícito acordado | Especificación |
| D-004 | Laboratorio Compose separado con el mismo código | Inyectar sobre la instancia cotidiana | Preservar datos y limitar el radio | Plan general |
| D-005 | Inyección selectiva desde auxiliar con temporizador independiente | Modificar red del host; alterar código de la API | Reversión y aislamiento | Plan general |
| D-006 | Umbrales experimentales explícitos, sujetos a refutación | Presentarlos como SLO productivos | No existen SLO aprobados para este Game Day | Diseño |
| D-007 | Conservar volumen del laboratorio al finalizar | Eliminar datos automáticamente | Permitir inspección y evitar borrados implícitos | Plan general |
| D-008 | Cerrar fase 01 por validación estática de su entregable de diseño; operación en fases 02–04 | Exigir una corrida para cerrar el diseño que habilita construir el harness | Evitar dependencia circular sin adelantar validación de resiliencia | Fase 01 |
| D-009 | Fijar ventanas semiabiertas, denominadores, mínimos de muestra y aborto de controles explícitos | Resolver criterios durante la ejecución o mezclar readiness con liveness | Evaluación reproducible y transferencia sin decisiones implícitas | Fase 01 |
| D-010 | Supervisor PID1 con IPC UNIX privado, TTL y concesión independiente del runner; DNS en hilo separado | Temporizador dentro del generador o DNS bloqueante en el bucle de retirada | Mantener reversión ante caída del runner y no bloquearla por resolución | Fase 02 |
| D-011 | Credenciales propias en .chaos/ID/env con permisos privados, fuera de artefactos y builds | Reutilizar .env o publicar secretos junto a evidencia | Preservación de la instancia cotidiana y separación de evidencia | Fase 02 |
| D-012 | Registrar límites host_before/host_after de IPC y dominio de cada reloj | Comparar directamente monotónicos de host y contenedor | Evitar asumir un mismo origen temporal en Docker Desktop | Fase 02 |
| D-013 | Verificador offline de solo lectura; separar integridad, criterios y clasificación; resumen regenerable | Equiparar salida cero con resiliencia confirmada o modificar evidencia al verificar | Una hipótesis refutada es válida con evidencia completa; fixtures nunca acreditan operación | Fase 03 |
| D-014 | Formato 2, límites temporales conservadores, métricas crudas con hash e índice y parser debug acotado | Mezclar relojes, inventar nombres de métricas o asumir trazas completas | Reproducibilidad y evidencia insuficiente explícita; corridas nuevas para captura detallada | Fase 03 |

## Referencias

- [Guía de trabajo](../GUIA-AGENTE.md) y [constitución](../CONSTITUCION.md).
- [Plan general](00-plan-general.md), [README](../../README.md) y [requerimientos](../../requerimientos.md).
- [Servicios locales](../ID-001-microservicios-locales/00-especificacion.md) y [observabilidad](../ID-002-observabilidad-otel/00-especificacion.md).
- [Límite y manejo de errores de pedidos](../../services/orders/app/main.py).
- [tc-netem, manual upstream de iproute2](https://man7.org/linux/man-pages/man8/tc-netem.8.html), consultado el 2026-10-16: retraso por paquete, clasificación y limitaciones del kernel.
- [Docker Compose: networking](https://docs.docker.com/compose/how-tos/networking/), consultado el 2026-10-16: redes y modo `service`.
- [OpenTelemetry Collector: troubleshooting](https://opentelemetry.io/docs/collector/troubleshooting/), consultado el 2026-10-16: exportador debug detallado.

La referencia a Principios del Caos y herramientas conceptuales procede del requerimiento. No se atribuye a su documentación una equivalencia funcional con el laboratorio. La precisión temporal y la limpieza ante fallos de infraestructura siguen siendo hipótesis que necesitan validación local.
