# ID-003 — Informe final: Game Day de caos local

## Identificación

| Campo | Detalle |
|---|---|
| **ID** | ID-003 |
| **Título** | Game Day de caos local |
| **Sprint / iteración** | No documentado |
| **Estado de cierre** | En implementación: fase 1 completada; fases 2 y 3 implementadas sin validar; fase 4 ejecutada con H1 aceptada en el ensayo; informe Markdown de fase 5 generado |
| **Sistemas y repositorios afectados** | Proyecto actual; harness de laboratorio local |
| **Iniciativas relacionadas** | ID-001 e ID-002 |

## Resumen

La fase 1 queda completada en su alcance de diseño documental. La fase 2 entrega manifiesto Compose autónomo, CLI Python, supervisor independiente y carga. La fase 3 añade captura Prometheus, Collector detallado exclusivo, verificador y analizador offline. La suite conjunta aprueba 91 pruebas unitarias; la prueba de correlación cubre el span de negocio en error con el span HTTP cliente hijo. La corrida `fase4-01` se preparó y ejecutó localmente, terminó con estado `executed`, y la limpieza se confirmó: supervisor `clean`, sin filtros; proyecto `stopped`, con volumen y evidencia preservados. El análisis correlaciona los 45 timeouts elegibles con sus logs y spans; H1 queda aceptada para el ensayo ejecutado. El informe Markdown `artifacts/chaos/fase4-01/results.md` integra una captura existente.

## Problema atendido

La dependencia HTTP de pedidos hacia catálogo se evaluó mediante latencia controlada, medición de errores, correlación de trazas, integridad de persistencia y recuperación en un laboratorio local aislado.

## Resultado por fase

| Estado | Fase | Resultado entregado | Desviación respecto al diseño |
|---|---|---|---|
| Completada | 1 — Diseño | Hipótesis, SLI, fichas, aborto, reversión y evidencia del código revisados documentalmente; Gate 3 cerrado | Ninguna; comprobaciones operativas corresponden a fases posteriores |
| Implementada sin validar | 2 — Harness | Manifiesto, CLI, supervisor, carga, artefactos básicos y pruebas unitarias implementados; validación operativa pendiente | Captura avanzada y análisis se mantienen en fase 3 |
| Implementada sin validar | 3 — Observabilidad | Captura cruda indexada, Collector detallado, verificador y analizador offline implementados | Formato versión 2 y límites temporales conservadores explícitos; informe Markdown reservado a fase 5 |
| Completada en alcance ejecutado | 4 — Ejecución y análisis | Corrida `fase4-01` real, limpieza confirmada y análisis offline ejecutado | Correlación de solicitudes, logs y spans comprobada; H1 aceptada para el ensayo |
| Completada en alcance Markdown | 5 — Entregable | Informe `results.md` generado con datos reales y captura pertinente | PDF fuera de esta entrega |

## Cumplimiento de requisitos

| Estado | Requisito | Evidencia |
|---|---|---|
| Cumplido y validado documentalmente | RF-001 | Formulación H1–H3 revisada en fase 1; no afirma que las hipótesis hayan sido confirmadas experimentalmente |
| Diseño validado; harness implementado sin validación operativa | RF-002 | E1–E3 revisados; manifiesto, CLI y supervisor de fase 2 |
| Cumplido parcialmente: captura y análisis implementados | RF-003 | SLI de H1–H3 revisados; captura y analizador disponibles sin evidencia operativa |
| Cumplido parcialmente: corrida y limpieza observadas; H1 aceptada en el ensayo | RF-004 | `fase4-01` terminó `executed`; `status` informó `clean` sin filtros y `down` informó `stopped` |
| Cumplido: artefactos reales con integridad completa | RF-005 | `artifacts/chaos/fase4-01/`; checker reportó integridad completa |
| Cumplido parcialmente: mediciones y correlación de trazas disponibles | RF-006 | 45/45 timeouts elegibles correlacionados y dentro de 4,5–6,5 s; persistencia 1→125 (124 pedidos); readiness 1,19–1,46 s |
| Validado para las condiciones del ensayo | RF-007 | Respuestas 504, logs y spans enlazados por `request_id` y `trace_id`; no extrapolar fuera de las condiciones medidas |
| Cumplido: informe Markdown con resultados observados | RF-008 | `artifacts/chaos/fase4-01/results.md`; mediciones de E1 y correlación trazable |
| No cumplido: diferido | RF-009 | PDF no producido |
| Cumplido parcialmente: implementación | RNF-001 | Topología aislada implementada; operación pendiente |
| Cumplido parcialmente: reversión confirmada en una corrida | RNF-002 | Supervisor PID 1, TTL y concesión; `fase4-01` terminó con supervisor `clean`, sin filtros, y proyecto `stopped` |
| Cumplido parcialmente: preservación observada | RNF-003 | Configuración privada separada de metadatos; volumen y evidencia de `fase4-01` preservados |
| Cumplido parcialmente: herramientas y evidencia real con integridad completa | RNF-004 | CLI, formato versión 2 y análisis reproducible; correlación timeout 504-span comprobada |
| Cumplido parcialmente: pruebas y corrida documentadas | RNF-005 | 91 pruebas unitarias aprobadas; corrida ejecutada e informe generado |

## Cambios entregados

| Ubicación | Cambio aplicado | Efecto observable |
|---|---|---|
| `specs/ID-003-gameday-caos-local/` | Ocho documentos derivados de la estructura de plantilla y capturas existentes | Especificación, plan, cinco fases e informe de transferencia disponibles |
| `01-diseno-gameday.md` y documentos de seguimiento | Diseño completado y estado propagado | Hipótesis, indicadores, controles y límites trazados a requisitos |
| `compose.chaos.yaml`, `docker/chaos/` y `scripts/chaos/` | Laboratorio, supervisor y CLI implementados | Preparación, ejecución, estado, retirada y apagado disponibles; sin validación operativa |
| `tests/chaos/` | Pruebas unitarias con dobles y fixtures de evidencia | Suite conjunta de 91 pruebas aprobadas en 2,129 s, sin Docker real |
| `docker/otel-collector/chaos.yaml` y captura del laboratorio | Collector detallado exclusivo y Prometheus crudo indexado | Captura real de `fase4-01`; 45 timeouts elegibles correlacionados con logs y spans |
| `scripts/chaos/evidence.py`, `check_evidence.py` y `analyze.py` | Análisis offline, verificador de solo lectura y generación de `summary.json` | Aplicados a `fase4-01`; integridad completa y H1 aceptada para el ensayo |

## Evidencia de validación

| Tipo | Qué se verificó | Resultado |
|---|---|---|
| Estática documental de fase 1 | Hipótesis, SLI, enlaces al código, criterios de aborto, Gates 1–2, trazabilidad y estados | Diseño validado; Gate 3 de fase 1 cerrado; no valida el laboratorio |
| Automatizada de fase 2 | Unitarias del harness | 50 pruebas aprobadas en 1,008 s con `python3 -m unittest discover -s tests/chaos -p 'test_*.py'` |
| Automatizada conjunta tras fase 3 | Harness, captura y evidencia offline con fixtures temporales | 91 pruebas aprobadas en 2,129 s; datos sintéticos sin validación operativa |
| Sintaxis y CLI | AST de once archivos y ayuda de comandos | Correctos; sin ejecutar servicios |
| Estática Compose | Sintaxis e interpolación con valores ficticios y normalización | Aprobada sin daemon; Collector exclusivo montado en solo lectura y puertos loopback |
| Funcional / operativa | Corrida local, mediciones y recuperación de `fase4-01` | Ejecutada; 45/45 timeouts elegibles correlacionados y dentro del intervalo esperado; readiness 1,19–1,46 s; H1 aceptada para el ensayo |
| Reversión y compatibilidad | Retirada real del fallo y datos conservados | Confirmada para `fase4-01`: supervisor `clean`, sin filtros; `down` `stopped`; volumen y evidencia preservados |

## Decisiones técnicas relevantes

| Id | Decisión | Alternativa descartada | Motivo | Consecuencia asumida |
|---|---|---|---|---|
| D-001 | Ejecutar latencia; CPU y partición solo diseño | Ejecutar tres experimentos | Alcance acordado | Solo H1 tendrá evidencia real |
| D-002 | Evidencia en archivos | Stack gráfico adicional | Reutilizar telemetría | Captura explícita necesaria |
| D-003 | Markdown inmediato y PDF diferido | Renderer automático | Alcance acordado | RF-009 abierto |
| D-004, D-005 | Proyecto separado y auxiliar selectivo | Red del host o instancia cotidiana | Aislamiento | Validar capacidades y clasificación |
| D-006 | Umbrales experimentales | SLO productivos implícitos | Falta de SLO aprobado | Conclusiones limitadas al laboratorio |
| D-007 | Conservar volumen | Borrado automático | Inspección y preservación | Limpieza destructiva fuera del flujo |
| D-008 | Cerrar diseño mediante revisión estática; operación en fases posteriores | Exigir ejecución antes de construir el harness | Evitar dependencia circular | Gate 3 de fase 1 no valida resiliencia |
| D-009 | Precisar ventanas, denominadores, muestras y aborto | Resolver criterios durante el ensayo | Reproducibilidad | Reglas comunes transferidas al plan general |
| D-010 | Supervisor PID 1 con socket UNIX interno y TTL/concesión | Supervisión ligada al proceso de carga o socket Docker montado | Retirada independiente del runner y menor privilegio | Requiere confirmar disponibilidad y limpieza con infraestructura local operativa |
| D-011 | Configuración privada en `.chaos/<run-id>/env` y metadatos saneados separados | Incorporar secretos en evidencia o reutilizar `.env` cotidiano | Aislamiento de datos y credenciales | Preservar y excluir del versionado los archivos privados |
| D-012 | Distinguir relojes del host y del contenedor mediante límites de IPC | Comparar monotónicos directamente | Orígenes temporales potencialmente diferentes en Docker Desktop | El analizador debe respetar los dominios y la incertidumbre de sincronización |
| D-013 | Separar integridad de evidencia y resultado de la hipótesis | Fallar el verificador ante toda hipótesis refutada | Una refutación respaldada por datos es un resultado válido | Salida cero con evidencia completa; uno con evidencia incompleta o inconsistente; análisis genera summary.json offline |
| D-014 | Ventanas conservadoras entre relojes y límites explícitos de la salida detailed | Suponer entrega completa o comparar dominios distintos | Evitar conclusiones sin spans requeridos y clasificación temporal optimista | Collector exclusivo, parser acotado y ventanas basadas en límites IPC; formatos desconocidos o trazas insuficientes quedan incompletos |

## Limitaciones conocidas

- La aceptación de H1 se limita a las condiciones y umbrales del ensayo `fase4-01`; no se extrapola a otros perfiles de carga o fallos.
- El laboratorio usa Collector propio en modo `detailed`; el habitual conserva su configuración. La captura, el margen de exportación y el formato debug concreto requieren validación operativa.
- El analizador exige formato versión 2 y no completa evidencia faltante con supuestos; los fixtures temporales están identificados como sintéticos.
- El filtro cubre IPv4 TCP sin fragmentación y cabecera IPv4 de veinte bytes; IPv6 se rechaza.
- Las capacidades del daemon, el efecto de netem y los criterios medidos se observaron en `fase4-01` y están documentados en el informe de resultados.
- El watchdog no garantiza recuperación ante pérdida completa del daemon o del propio auxiliar.
- El informe integra una captura visual existente de `fase4-01`.

## Pendientes y bloqueantes

| Id | Pendiente o bloqueante | Impacto | Siguiente acción | Dónde continúa |
|---|---|---|---|---|
| 1 | Capacidades y límites operativos pendientes | Impide aceptar aislamiento y reversión reales | Confirmar manualmente preflight, filtros, identidad, TTL y concesión implementados | Fases 2 y 4 |
| 2 | PDF fuera de la entrega Markdown | RF-009 tiene alcance independiente | Tratarlo como entregable separado si se requiere | Fase 5 |

## Estado de cierre

La fase 1 de diseño queda Completada y su Gate 3 cerrado con validación estática documental. Las fases 2 y 3 quedan Implementadas sin validar. La corrida `fase4-01`, su limpieza y la correlación de evidencia se confirmaron; H1 queda aceptada para las condiciones del ensayo. El informe Markdown de fase 5 está generado y revisado.

## Próximos pasos recomendados

1. Conservar el alcance de H1 al perfil y las condiciones medidas en `fase4-01` al comunicar los resultados.
2. Tratar las ejecuciones de H2 y H3 como experimentos independientes si se amplía el alcance.

## Verificación de cierre documental

La revisión cierra el Gate 3 de la fase 1, cuyo entregable es diseño documental. Los Gates 1 y 2 se revisan documentalmente en esa fase. El Gate 4 de cierre integral permanece pendiente hasta completar las fases restantes y disponer de resultados reales.

- [x] Los estados Completada de fase 1, Implementada sin validar de fases 2–3 y Pendiente de fases 4–5 se propagan al plan general.
- [x] Se distingue diseño de implementación y ejecución real.
- [x] Todos los requisitos aparecen con cobertura y pendientes explícitos.
- [x] Las decisiones del diseño están registradas.
- [x] No quedan aclaraciones de diseño abiertas; los riesgos operativos se conservan pendientes.
- [x] Los enlaces entre documentos se revisan localmente en esta entrega.
- [x] Se usa redacción impersonal y no se incluye estado efímero de control de versiones.
