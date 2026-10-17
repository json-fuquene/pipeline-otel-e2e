# ID-003 — Fase 4: Ejecución local y análisis

## Identificación

| Campo | Detalle |
|---|---|
| **Plan** | ID-003 — Game Day de caos local |
| **Fase** | 4 — Ejecución y análisis |
| **Estado** | Pendiente |
| **Requisitos que cubre** | RF-004, RF-005, RF-006, RF-007; RNF-001 a RNF-005 |
| **Sistemas y repositorios** | Laboratorio local y evidencia de corrida |
| **Dependencias previas** | Fases 2 y 3 implementadas; unitarias aprobadas; reversión confirmada |
| **Habilita a** | Informe con resultados de fase 5 |

## Objetivo

Obtener una ejecución real de latencia con baseline, fallo y recuperación verificables, comparando hipótesis y mediciones sin inferir causalidad no demostrada.

## Contexto de la fase

Esta fase es operativa y se reserva para ejecución manual confirmada. La autorización de documentación no ejecuta el laboratorio. Duración estimada futura: aproximadamente cuatro minutos de medición más preparación y captura; el primer build depende de imágenes y dependencias disponibles.

## Alcance técnico

### Cambios previstos

| Ubicación | Cambio | Requisito asociado |
|---|---|---|
| `artifacts/chaos/<run-id>/` | Evidencia de una corrida real, sin sobrescribir anteriores | RF-005, RNF-004 |
| `results.md` de la corrida | Comparación, hallazgo, incertidumbre y remediación | RF-006, RF-007 |
| Documentos de este plan | Actualización de validaciones y estados confirmados | RNF-005 |

### No incluido en esta fase

- Ejecutar los experimentos de CPU y partición.
- Implementar remediaciones ni introducir reintentos o circuit breaker.
- Capturas automáticas y generación del PDF.

## Diseño

### Procedimiento manual futuro

Los comandos del harness y análisis offline están implementados en fases 2 y 3. Se ejecutarán manualmente desde la raíz después de aprobar las verificaciones locales y usando una corrida nueva de formato 2. El generador del informe Markdown sigue pendiente de fase 5.

1. Revisar configuración local del destino Docker sin leer credenciales. Solo continuar con daemon local. Verificar recursos disponibles, reversión previamente confirmada y ausencia de otra corrida activa.
2. Ejecutar `python3 scripts/chaos/run.py prepare --run-id ensayo-01`. Confirmar puertos loopback, producto/pedido de control y volumen separado. No iniciar si exige un destino externo no autorizado.
3. Ejecutar `python3 scripts/chaos/run.py run --run-id ensayo-01`. El runner mide baseline 60 s, inyecta 6000 ms durante 60 s, verifica retirada, drena 15 s y mide recuperación 60 s. No reintenta creaciones.
4. Durante un aborto, ejecutar `python3 scripts/chaos/run.py rollback --run-id ensayo-01`. No esperar al informe para retirar un fallo inseguro.
5. Ejecutar `python3 scripts/chaos/run.py status --run-id ensayo-01`. Confirmar ausencia de handles propios; readiness recuperado y cero escrituras atribuibles a POST fallidos.
6. Ejecutar `python3 scripts/chaos/analyze.py artifacts/chaos/ensayo-01` y `python3 scripts/chaos/check_evidence.py artifacts/chaos/ensayo-01`. Registrar salidas y revisar clasificación frente a evidencia cruda. La producción de `results.md` se realiza en fase 5, cuando exista el generador correspondiente.
7. Capturar manualmente las vistas de interés y agregar enlaces relativos únicamente a imágenes existentes. No capturar secretos.
8. Ejecutar `python3 scripts/chaos/run.py down --run-id ensayo-01`. Conservar volumen y evidencia; no usar `down -v`.

La frecuencia de carga no depende de la respuesta anterior. Las solicitudes omitidas, timeout del generador o errores sin respuesta se conservan en denominadores. El ensayo completo se invalida si no hay baseline estable, se afecta un control, cambia el destino o no puede comprobarse la retirada.

### Ventanas y criterio de hipótesis

El baseline requiere 100 % de creaciones 201, controles 200 y p95 menor de 1 s por operación. Para verificar timeout bajo fallo estable, usar solicitudes iniciadas al menos 10 s después de confirmar la inyección y cuya terminación preceda a la retirada. Exigir al menos 30 muestras elegibles; no seleccionar ventanas después de conocer resultados. Las solicitudes de transición se reportan separadamente y nunca desaparecen del conteo total.

En la ventana elegible se espera al menos 95 % de `504 catalog_timeout` sobre los intentos elegibles y al menos 95 % de esas respuestas con duración dentro de 4,5–6,5 s. Los controles de lectura deben mantenerse 100 % en 200 y p95 menor de 1 s. No debe existir ningún pedido persistido atribuible a una creación fallida. No hay evidencia suficiente para afirmar un timeout controlado si solo se observó el timeout del cliente de carga.

La recuperación exige readiness 200 dentro de 60 s desde la retirada confirmada, creaciones 100 % en 201 y controles 100 % en 200 en la ventana de recuperación, con p95 menor de 1 s por operación. Informar tiempo desde retirada hasta primer éxito y hasta readiness recuperado. La diferencia entre pedidos finales e iniciales debe igualar el total de POST exitosos de todas las ventanas, incluidas transiciones, una vez drenadas solicitudes. La exclusividad de datos y ausencia de escritores ajenos permiten esa comprobación.

### Análisis y aprendizaje

Separar hechos observados, hipótesis causal y propuesta. Un resultado puede ser aceptado o refutado únicamente con evidencia suficiente de inyección efectiva, carga y reversión; de lo contrario es inconcluso. Una hipótesis refutada no invalida por sí sola el experimento ni impide documentar aprendizaje.

Los posibles hallazgos, aún no observados, incluyen propagación de indisponibilidad por dependencia síncrona o readiness dependiente de catálogo. Las posibles acciones incluyen revisar presupuesto de timeout, aislamiento de concurrencia y estrategia de degradación. No recomendar reintentos de POST sin resolver idempotencia. Cada propuesta tendrá prioridad, componente afectado, beneficio esperado, riesgo y criterio para repetir el ensayo. No afirmar antifragilidad conseguida hasta comprobar una mejora en un ensayo posterior.

### Comportamiento esperado por caso

| Caso | Condición | Resultado esperado |
|---|---|---|
| C-002 | Fallo válido y métricas dentro del umbral | Hipótesis aceptada en las condiciones del ensayo |
| C-007 | Fallo válido y umbral incumplido | Hipótesis refutada y hallazgo documentado |
| C-005 | Baseline inválido | No inyectar; diagnosticar y preparar corrida nueva |
| C-006 | Faltan muestras, efecto o limpieza | Inconcluso; ninguna afirmación de recuperación comprobada |
| C-003 | Fallo retirado | Recuperación medida sin reiniciar APIs |

## Tareas

| Estado | # | Tarea | Criterio de aceptación |
|---|---|---|---|
| [ ] | 1 | Confirmar precondiciones y reversión | Registro sin secretos y objetivo local inequívoco |
| [ ] | 2 | Ejecutar corrida completa | Evidencia cruda de todas las ventanas |
| [ ] | 3 | Verificar retirada y persistencia | Handles ausentes, conteos conciliados y recuperación |
| [ ] | 4 | Comparar SLI con umbrales | Clasificación reproducible con al menos 30 muestras elegibles |
| [ ] | 5 | `[P]` Documentar causalidad y remediación | Separación entre hecho, hipótesis y propuesta |
| [ ] | 6 | Actualizar fases y cobertura | Gates 3 aplicados solo con confirmación real |

## Validación

| Estado | Tipo | Qué verifica | Cómo se ejecuta | Resultado esperado |
|---|---|---|---|---|
| Pendiente de confirmación | Operativa | RF-004, RF-005, RNF-001 | Procedimiento 1–5 | Fallo acotado, ventanas completas y objetivo local |
| Pendiente | Automatizada sobre archivos | RF-005, RNF-004 | `python3 scripts/chaos/check_evidence.py artifacts/chaos/ensayo-01` | Conteos, tiempos y archivos consistentes; sin servicios vivos |
| Pendiente de confirmación | Reversión | RNF-002, RNF-003 | Procedimiento 4, 5 y 8 | Sin reglas propias y sin borrado de datos |
| Pendiente de confirmación | Análisis | RF-006, RF-007 | Contrastar summary.json y results.md con requests.jsonl, logs y eventos | Clasificación sustentada y remediación verificable |

## Riesgos y bloqueantes de la fase

| Estado | Elemento | Impacto | Mitigación o siguiente acción |
|---|---|---|---|
| Abierto | No existe corrida real | Alto | Implementar fases previas y ejecutar manualmente |
| Abierto | Medición incompleta o contaminación de ventanas | Medio | Reportar todas las solicitudes y transiciones |
| Abierto | Conclusiones causales sin evidencia | Medio | Marcar hipótesis y proponer ensayo de seguimiento |

## Cierre de la fase

- **Resultado obtenido:** No implementado ni ejecutado; procedimiento preparado.
- **Desviaciones respecto al diseño:** Ninguna.
- **Decisiones tomadas durante la fase:** D-006 y D-007 aplican al procedimiento.
- **Requisitos afectados en su cobertura:** RF-004 a RF-007 y RNF-001 a RNF-005 pendientes de evidencia real.
- **Actualizaciones aplicadas a `00-plan-general.md`:** Fase pendiente y validaciones sin confirmar.
- **Actualizaciones aplicadas a `00-especificacion.md`:** Ninguna.
- **Pendientes trasladados:** Corrida real, análisis y confirmación; resultados para fase 5.
