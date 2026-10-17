# ID-003 — Informe final: Game Day de caos local

## Identificación

| Campo | Detalle |
|---|---|
| **ID** | ID-003 |
| **Título** | Game Day de caos local |
| **Sprint / iteración** | No documentado |
| **Estado de cierre** | En implementación: fase 1 completada; fases 2 y 3 implementadas sin validar |
| **Sistemas y repositorios afectados** | Proyecto actual; harness de laboratorio local |
| **Iniciativas relacionadas** | ID-001 e ID-002 |

## Resumen

La fase 1 queda completada en su alcance de diseño documental. La fase 2 entrega manifiesto Compose autónomo, CLI Python, supervisor independiente y carga. La fase 3 añade captura Prometheus, Collector detallado exclusivo, verificador y analizador offline. La suite conjunta aprueba 90 pruebas unitarias en 2,122 s; sintaxis AST de once archivos, ayuda CLI y Compose normalizado sin daemon también resultan correctos. Las fases 2 y 3 se mantienen Implementadas sin validar porque no se han ejecutado builds, servicios, inyecciones ni pruebas operativas de reversión. Las fases 4–5, los resultados reales, la recuperación y la remediación basada en mediciones permanecen pendientes. Las capturas son manuales y el PDF original de 4–5 páginas está diferido.

## Problema atendido

La dependencia HTTP de pedidos hacia catálogo carece de evidencia de resiliencia obtenida mediante fallos controlados en este plan. La documentación define cómo comprobar aislamiento, errores, integridad y recuperación sin afectar los datos de la instancia cotidiana.

## Resultado por fase

| Estado | Fase | Resultado entregado | Desviación respecto al diseño |
|---|---|---|---|
| Completada | 1 — Diseño | Hipótesis, SLI, fichas, aborto, reversión y evidencia del código revisados documentalmente; Gate 3 cerrado | Ninguna; comprobaciones operativas corresponden a fases posteriores |
| Implementada sin validar | 2 — Harness | Manifiesto, CLI, supervisor, carga, artefactos básicos y pruebas unitarias implementados; validación operativa pendiente | Captura avanzada y análisis se mantienen en fase 3 |
| Implementada sin validar | 3 — Observabilidad | Captura cruda indexada, Collector detallado, verificador y analizador offline implementados | Formato versión 2 y límites temporales conservadores explícitos; informe Markdown reservado a fase 5 |
| Pendiente | 4 — Ejecución | Procedimiento manual especificado; sin resultados | Ninguna |
| Pendiente | 5 — Entregable | Contenido del informe y PDF posterior especificados | PDF diferido por alcance acordado |

## Cumplimiento de requisitos

| Estado | Requisito | Evidencia |
|---|---|---|
| Cumplido y validado documentalmente | RF-001 | Formulación H1–H3 revisada en fase 1; no afirma que las hipótesis hayan sido confirmadas experimentalmente |
| Diseño validado; harness implementado sin validación operativa | RF-002 | E1–E3 revisados; manifiesto, CLI y supervisor de fase 2 |
| Cumplido parcialmente: captura y análisis implementados | RF-003 | SLI de H1–H3 revisados; captura y analizador disponibles sin evidencia operativa |
| Cumplido parcialmente: harness disponible; ejecución pendiente | RF-004 | CLI de fase 2 y procedimiento de fase 4; sin corrida real |
| No cumplido: ejecución pendiente | RF-005 | No hay artefactos de corrida |
| No cumplido: mediciones pendientes | RF-006 | No hay comparación real |
| No cumplido: hallazgo pendiente | RF-007 | Solo método de remediación y seguimiento |
| Cumplido parcialmente: planificación Markdown | RF-008 | Carpeta documental; results.md del ensayo pendiente |
| No cumplido: diferido | RF-009 | PDF no producido |
| Cumplido parcialmente: implementación | RNF-001 | Topología aislada implementada; operación pendiente |
| Cumplido parcialmente: implementación | RNF-002 | Supervisor PID 1, TTL, concesión y limpieza implementados; reversión real pendiente |
| Cumplido parcialmente: implementación | RNF-003 | Configuración privada separada de metadatos; preservación operativa pendiente |
| Cumplido parcialmente: implementación | RNF-004 | CLI, artefactos versión 2 y análisis reproducible disponibles; corrida pendiente |
| Cumplido parcialmente: documentación y pruebas | RNF-005 | 90 pruebas unitarias de harness y evidencia aprobadas; verificaciones operativas separadas y pendientes |

## Cambios entregados

| Ubicación | Cambio aplicado | Efecto observable |
|---|---|---|
| `specs/ID-003-gameday-caos-local/` | Ocho documentos derivados de la estructura de plantilla | Especificación, plan, cinco fases e informe de transferencia disponibles |
| `01-diseno-gameday.md` y documentos de seguimiento | Diseño completado y estado propagado | Hipótesis, indicadores, controles y límites trazados a requisitos |
| `compose.chaos.yaml`, `docker/chaos/` y `scripts/chaos/` | Laboratorio, supervisor y CLI implementados | Preparación, ejecución, estado, retirada y apagado disponibles; sin validación operativa |
| `tests/chaos/` | Pruebas unitarias con dobles y fixtures de evidencia | Suite conjunta de 90 pruebas aprobadas en 2,122 s, sin Docker real |
| `docker/otel-collector/chaos.yaml` y captura del laboratorio | Collector detallado exclusivo y Prometheus crudo indexado | Captura sin cambiar Collector habitual; entrega completa no presupuesta y validación real pendiente |
| `scripts/chaos/evidence.py`, `check_evidence.py` y `analyze.py` | Análisis offline, verificador de solo lectura y generación de summary.json | Integridad separada del resultado de H1; ningún resultado sintético se presenta como corrida real |

## Evidencia de validación

| Tipo | Qué se verificó | Resultado |
|---|---|---|
| Estática documental de fase 1 | Hipótesis, SLI, enlaces al código, criterios de aborto, Gates 1–2, trazabilidad y estados | Diseño validado; Gate 3 de fase 1 cerrado; no valida el laboratorio |
| Automatizada de fase 2 | Unitarias del harness | 50 pruebas aprobadas en 1,008 s con `python3 -m unittest discover -s tests/chaos -p 'test_*.py'` |
| Automatizada conjunta tras fase 3 | Harness, captura y evidencia offline con fixtures temporales | 90 pruebas aprobadas en 2,122 s; datos sintéticos sin validación operativa |
| Sintaxis y CLI | AST de once archivos y ayuda de comandos | Correctos; sin ejecutar servicios |
| Estática Compose | Sintaxis e interpolación con valores ficticios y normalización | Aprobada sin daemon; Collector exclusivo montado en solo lectura y puertos loopback |
| Funcional / operativa | Inyección, mediciones y recuperación | Pendiente de confirmación; no ejecutado |
| Reversión y compatibilidad | Retirada real del fallo y datos conservados | Diseño documentado; comprobación operativa pendiente |

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

- La CLI, la captura avanzada y el análisis offline están implementados; el informe results.md sigue pendiente de fase 5.
- El laboratorio usa Collector propio en modo `detailed`; el habitual conserva su configuración. La captura, el margen de exportación y el formato debug concreto requieren validación operativa.
- El analizador exige formato versión 2 y no completa evidencia faltante con supuestos; los fixtures temporales están identificados como sintéticos.
- El filtro cubre IPv4 TCP sin fragmentación y cabecera IPv4 de veinte bytes; IPv6 se rechaza.
- Las capacidades del daemon, el efecto de netem y los umbrales no se han confirmado en una corrida local.
- El watchdog no garantiza recuperación ante pérdida completa del daemon o del propio auxiliar.
- No hay capturas nuevas, resultados reales ni PDF de este Game Day.

## Pendientes y bloqueantes

| Id | Pendiente o bloqueante | Impacto | Siguiente acción | Dónde continúa |
|---|---|---|---|---|
| 1 | Capacidades y límites operativos pendientes | Impide aceptar aislamiento y reversión reales | Confirmar manualmente preflight, filtros, identidad, TTL y concesión implementados | Fases 2 y 4 |
| 2 | Captura avanzada y análisis implementados sin confirmación operativa | Impide aceptar la completitud de evidencia real | Verificar métricas, exportación detallada, correlación y análisis sobre una corrida real | Fases 3 y 4 |
| 3 | Corrida real y reversión no verificadas | Impide validar RF-004 a RF-007 | Ejecución manual y confirmación | Fase 4 |
| 4 | Informe con resultados y capturas | Entrega empírica pendiente | Generar informe y vincular imágenes existentes | Fase 5 |
| 5 | PDF original diferido | Impide cumplimiento integral | Producir y revisar 4–5 páginas posteriormente | Fase 5 / RF-009 |

## Estado de cierre

La fase 1 de diseño queda Completada y su Gate 3 cerrado con validación estática documental. Las fases 2 y 3 quedan Implementadas sin validar y conservan pendiente el cierre operativo de sus Gates 3. No se afirma validación de resiliencia ni operación real. El plan permanece En implementación; las fases 4–5 y el Gate 4 integral conservan estado pendiente y los resultados originales siguen abiertos.

## Próximos pasos recomendados

1. Confirmar manualmente precondiciones, reversión y una corrida completa de E1 con captura avanzada.
2. Verificar evidencia y generar summary.json offline; contrastar métricas, logs y span cliente.
3. Incorporar resultados y capturas; producir el PDF solo al ampliar el alcance de entrega.

## Verificación de cierre documental

La revisión cierra el Gate 3 de la fase 1, cuyo entregable es diseño documental. Los Gates 1 y 2 se revisan documentalmente en esa fase. El Gate 4 de cierre integral permanece pendiente hasta completar las fases restantes y disponer de resultados reales.

- [x] Los estados Completada de fase 1, Implementada sin validar de fases 2–3 y Pendiente de fases 4–5 se propagan al plan general.
- [x] Se distingue diseño de implementación y ejecución real.
- [x] Todos los requisitos aparecen con cobertura y pendientes explícitos.
- [x] Las decisiones del diseño están registradas.
- [x] No quedan aclaraciones de diseño abiertas; los riesgos operativos se conservan pendientes.
- [x] Los enlaces entre documentos se revisan localmente en esta entrega.
- [x] Se usa redacción impersonal y no se incluye estado efímero de control de versiones.
