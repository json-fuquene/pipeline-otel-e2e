# ID-003 — Fase 4: Ejecución local y análisis

## Identificación

| Campo | Detalle |
|---|---|
| **Plan** | ID-003 — Game Day de caos local |
| **Fase** | 4 — Ejecución y análisis |
| **Estado** | Implementada sin validar |
| **Requisitos que cubre** | RF-004, RF-005, RF-006, RF-007; RNF-001 a RNF-005 |
| **Sistemas y repositorios** | Laboratorio local y evidencia de corrida |
| **Dependencias previas** | Fases 2 y 3 implementadas; unitarias aprobadas; reversión confirmada |
| **Habilita a** | Informe con resultados de fase 5 |

## Objetivo

Obtener y analizar una ejecución real de latencia con baseline, fallo y recuperación verificables, comparando hipótesis y mediciones sin inferir causalidad no demostrada. La fase utiliza el analizador y el verificador offline implementados en fase 3; la generación de `results.md` corresponde a fase 5.

## Contexto de la fase

Esta fase combina la ejecución manual del ensayo con el análisis offline de los artefactos resultantes. `run.py`, `analyze.py` y `check_evidence.py` ya están implementados; la fase no añade herramientas ni crea `results.md`. La corrida `fase4-01` terminó con `executed`, la limpieza se confirmó y el análisis correlaciona los timeouts elegibles con el log y los spans de la operación; H1 queda aceptada para el ensayo.

## Alcance técnico

### Cambios previstos

| Ubicación | Cambio | Requisito asociado |
|---|---|---|
| `artifacts/chaos/fase4-01/` | Evidencia de la corrida real; `run.py` generó `summary.json` y el análisis verificó la correlación de solicitudes, logs y spans | RF-004, RF-005, RF-006, RNF-004 |
| Documentos de este plan | Registro de ejecución, limpieza, mediciones, integridad y límites realmente confirmados | RF-006, RF-007, RNF-005 |

### No incluido en esta fase

- Ejecutar los experimentos de CPU y partición.
- Implementar remediaciones ni introducir reintentos o circuit breaker.
- Implementar `report.py` o generar `results.md`; ambos se reservan para fase 5.
- Capturas automáticas y generación del PDF.

## Diseño

### Procedimiento y resultado de `fase4-01`

La corrida se preparó y ejecutó localmente con un identificador nuevo. Los comandos de análisis operan sobre el directorio real existente; no crean el experimento. El generador del informe Markdown sigue pendiente de fase 5.

1. Preparar el laboratorio local: `python3 scripts/chaos/run.py prepare --run-id fase4-01`.
2. Ejecutar baseline, inyección, retirada, drenaje y recuperación: `python3 scripts/chaos/run.py run --run-id fase4-01`. El artefacto reporta estado `executed`.
3. Consultar y comprobar limpieza: `python3 scripts/chaos/run.py status --run-id fase4-01`. El supervisor reportó `clean`, sin filtros; `python3 scripts/chaos/run.py down --run-id fase4-01` dejó el proyecto `stopped`, conservando volumen y evidencia.
4. Analizar y verificar: `python3 scripts/chaos/analyze.py artifacts/chaos/fase4-01` y `python3 scripts/chaos/check_evidence.py artifacts/chaos/fase4-01`. La integridad quedó completa y la clasificación de H1 fue `aceptada`.
5. La captura de inyección se integró en `results.md` de fase 5. La fase 4 no genera ese informe.

La frecuencia de carga no depende de la respuesta anterior. Las solicitudes omitidas, timeout del generador o errores sin respuesta se conservan en denominadores. El ensayo completo se invalida si no hay baseline estable, se afecta un control, cambia el destino o no puede comprobarse la retirada.

### Ventanas y criterio de hipótesis

El baseline requiere 100 % de creaciones 201, controles 200 y p95 menor de 1 s por operación. Para verificar timeout bajo fallo estable, usar solicitudes iniciadas al menos 10 s después de confirmar la inyección y cuya terminación preceda a la retirada. Exigir al menos 30 muestras elegibles; no seleccionar ventanas después de conocer resultados. Las solicitudes de transición se reportan separadamente y nunca desaparecen del conteo total.

En la ventana elegible se espera al menos 95 % de `504 catalog_timeout` sobre los intentos elegibles y al menos 95 % de esas respuestas con duración dentro de 4,5–6,5 s. Los controles de lectura deben mantenerse 100 % en 200 y p95 menor de 1 s. No debe existir ningún pedido persistido atribuible a una creación fallida. No hay evidencia suficiente para afirmar un timeout controlado si solo se observó el timeout del cliente de carga.

La recuperación exige readiness 200 dentro de 60 s desde la retirada confirmada, creaciones 100 % en 201 y controles 100 % en 200 en la ventana de recuperación, con p95 menor de 1 s por operación. Informar tiempo desde retirada hasta primer éxito y hasta readiness recuperado. La diferencia entre pedidos finales e iniciales debe igualar el total de POST exitosos de todas las ventanas, incluidas transiciones, una vez drenadas solicitudes. La exclusividad de datos y ausencia de escritores ajenos permiten esa comprobación.

En `fase4-01`, las 45 solicitudes elegibles devolvieron `504 catalog_timeout` dentro del intervalo de duración esperado de 4,5–6,5 s. Las 45 quedaron enlazadas por `request_id` entre respuesta y log, y por `trace_id` con el span `orders.order.create` en error y su span HTTP cliente hijo hacia catálogo. El conteo de pedidos pasó de 1 a 125 y concilió 124 pedidos persistidos. Readiness se recuperó entre 1,19 y 1,46 s. La integridad quedó completa y H1 aceptada para las condiciones de este ensayo.

### Análisis y aprendizaje

Separar hechos observados, hipótesis causal y propuesta. Un resultado puede ser aceptado o refutado únicamente con evidencia suficiente de inyección efectiva, carga y reversión; de lo contrario es inconcluso. Una hipótesis refutada no invalida por sí sola el experimento ni impide documentar aprendizaje.

Los posibles hallazgos, aún no observados, incluyen propagación de indisponibilidad por dependencia síncrona o readiness dependiente de catálogo. Las posibles acciones incluyen revisar presupuesto de timeout, aislamiento de concurrencia y estrategia de degradación. No recomendar reintentos de POST sin resolver idempotencia. Cada propuesta tendrá prioridad, componente afectado, beneficio esperado, riesgo y criterio para repetir el ensayo. No afirmar antifragilidad conseguida hasta comprobar una mejora en un ensayo posterior.

### Comportamiento esperado por caso

| Caso | Condición | Resultado esperado |
|---|---|---|
| C-002 | Fallo válido, métricas dentro del umbral y correlación de traza presente | Hipótesis aceptada en las condiciones del ensayo |
| C-007 | Fallo válido y umbral incumplido | Hipótesis refutada y hallazgo documentado |
| C-005 | Baseline inválido | No inyectar; diagnosticar y preparar corrida nueva |
| C-006 | Faltan muestras, correlación del timeout con span, efecto o limpieza | Inconcluso; ninguna afirmación causal ni validación de hipótesis |
| C-003 | Fallo retirado | Recuperación medida sin reiniciar APIs |

## Tareas

| Estado | # | Tarea | Criterio de aceptación |
|---|---|---|---|
| [x] | 1 | Confirmar precondiciones y reversión | Laboratorio local preparado con el ID `fase4-01` |
| [x] | 2 | Ejecutar corrida completa | Estado `executed` y evidencia local guardada |
| [x] | 3 | Verificar retirada y persistencia | Supervisor `clean` sin filtros; `down` en `stopped`; conteos 1→125 conciliados |
| [x] | 4 | Comparar SLI con umbrales | Análisis de archivos: 45/45 timeouts elegibles correlacionados y dentro de duración; readiness 1,19–1,46 s; H1 aceptada |
| [ ] | 5 | `[P]` Documentar causalidad y remediación | No atribuir causalidad sin correlación; resultados y remediación editorial pasan a fase 5 |
| [x] | 6 | Actualizar fases y cobertura | Integridad confirmada y cobertura actualizada con H1 aceptada para el ensayo |

## Validación

| Estado | Tipo | Qué verifica | Cómo se ejecuta | Resultado esperado |
|---|---|---|---|---|
| Confirmada: corrida terminó `executed` | Funcional / operativa | RF-004, RF-005, RNF-001 | `run.py prepare` y `run.py run` con `--run-id fase4-01` | Ensayo local completado; H1 aceptada para las condiciones medidas |
| Confirmada | Automatizada sobre archivos | RF-005, RNF-004 | `python3 scripts/chaos/check_evidence.py artifacts/chaos/fase4-01` | Integridad completa; clasificación `aceptada` |
| Confirmada | Reversión | RNF-002, RNF-003 | `run.py status` y `run.py down` con `--run-id fase4-01` | Supervisor `clean`, sin filtros; proyecto `stopped`; volumen y evidencia preservados |
| Confirmada | Análisis offline | RF-006, RF-007 | `python3 scripts/chaos/analyze.py artifacts/chaos/fase4-01`; contrastar resumen con solicitudes, logs, métricas y eventos | 45/45 timeouts elegibles correlacionados y dentro de duración, persistencia conciliada y readiness recuperado; H1 aceptada para el ensayo |

## Riesgos y bloqueantes de la fase

| Estado | Elemento | Impacto | Mitigación o siguiente acción |
|---|---|---|---|
| Resuelto por análisis de correlación | Enlace entre timeout 504, log y spans del flujo | Alto | Correlacionar respuesta/log por `request_id` y log/traza por `trace_id`; verificar span de negocio y cliente hijo |
| Abierto | Medición incompleta o contaminación de ventanas | Medio | Reportar todas las solicitudes y transiciones |
| Abierto | Conclusiones causales sin evidencia | Medio | Marcar hipótesis y proponer ensayo de seguimiento |

## Cierre de la fase

- **Resultado obtenido:** Corrida local `fase4-01` ejecutada y limpiada; 45/45 timeouts elegibles correlacionados, con H1 aceptada para el ensayo.
- **Desviaciones respecto al diseño:** No se obtuvo la correlación de traza requerida; la evidencia conserva métricas de timeout y recuperación, pero no basta para clasificar H1.
- **Decisiones tomadas durante la fase:** D-006 y D-007 aplican al procedimiento.
- **Requisitos afectados en su cobertura:** RF-004 y reversión observados en la corrida; RF-005 cuenta con artefactos, pero su integridad está incompleta; RF-006 tiene mediciones parciales; RF-007 no se valida sin correlación causal. RNF-001 a RNF-005 conservan límites operativos documentados.
- **Actualizaciones aplicadas a `00-plan-general.md`:** Corrida ejecutada, resultado inconcluso y limpieza confirmada; Gate 3 de fase 4 permanece sin cierre.
- **Actualizaciones aplicadas a `00-especificacion.md`:** Ninguna.
- **Pendientes trasladados:** Resolver o explicar la ausencia de correlación 504-span y volver a analizar si corresponde. El informe `results.md` fue generado en fase 5; la salida PDF queda diferida.
