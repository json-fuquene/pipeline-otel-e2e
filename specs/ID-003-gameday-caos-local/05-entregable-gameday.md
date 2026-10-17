# ID-003 — Fase 05: Entregable del Game Day

## Identificación

| Campo | Detalle |
|---|---|
| **Plan** | ID-003 — Game Day de caos local |
| **Fase** | 05 — Entregable del Game Day |
| **Estado** | Completada en el alcance Markdown |
| **Requisitos que cubre** | RF-008, RF-009, RNF-004, RNF-005 |
| **Sistemas y repositorios** | Informe Markdown y evidencias locales del Game Day |
| **Dependencias previas** | Fase 04 ejecutada; mediciones y correlación deben reflejar los artefactos reales |
| **Habilita a** | Revisión general del plan; PDF fuera del documento actual |

## Objetivo

Producir un informe Markdown que permita revisar hipótesis, diseños, observabilidad y resultados reales del experimento local. La extensión seguirá la evidencia necesaria para explicar los resultados.

## Contexto de la fase

La entrega incorpora el informe ejecutado de `fase4-01` en Markdown. La correlación de respuestas, logs y spans sustenta la aceptación de H1 para esta corrida. El informe también identifica la captura del primer cálculo inconcluso como diagnóstico intermedio reemplazado. No se genera PDF en esta fase.

## Alcance técnico

### Cambios previstos

| Ubicación | Cambio | Requisito asociado |
|---|---|---|
| `artifacts/chaos/fase4-01/results.md` | Informe con resultados observados y correlación de trazas | RF-008, RNF-005 |
| `specs/ID-003-gameday-caos-local/evidencias/` | Incluir capturas existentes de inyección y diagnóstico intermedio | RF-008, RNF-004 |

### No incluido en esta fase

- Instalar motores de render ni implementar exportación a PDF durante la entrega Markdown.
- Inventar capturas, valores de métricas, debilidades observadas o resultados de experimentos no ejecutados.
- Ejecutar E2 y E3 para completar visualmente el informe; ambos permanecen como diseños.

## Diseño

El informe se generó desde `summary.json` y los artefactos de `fase4-01`, sin acceder a servicios ni modificar registros originales. Conserva los valores calculados y correlaciona cada timeout elegible con el log y los spans asociados. La captura de inyección documenta esta corrida; la captura del primer cálculo muestra un diagnóstico incompleto que quedó reemplazado por el análisis final.

El informe tendrá esta secuencia:

1. Objetivo, arquitectura local, aislamiento, versión del formato e identificación del ensayo.
2. Las tres hipótesis con su redacción completa y tabla de los tres experimentos: tipo, impacto, duración y reversión. Explicación conceptual de Chaos Monkey, Gremlin o Litmus sin afirmar su instalación.
3. Indicadores, carga, ventanas, umbrales de laboratorio y evidencia esperada. Separación explícita entre SLI de negocio y readiness.
4. E1 ejecutado: configuración efectiva, baseline, fallo, drenaje y recuperación; tabla de esperado frente a obtenido con número de muestras, porcentajes, p95, errores, persistencia, tiempo de recuperación y resultado por criterio.
5. Debilidad sistémica sustentada por evidencia, remediación propuesta, prioridad y validación futura. Si el ensayo no revela una debilidad adicional, se describirán los comportamientos controlados observados y el aprendizaje.
6. Estado de reversión y referencia a la ruta principal de evidencias.

Las conclusiones se derivarán del ensayo real de fase 04. H2 y H3 mostrarán estado «Solo diseño; sin ejecución» y no tendrán columna de resultados numéricos fabricados. Los datos sintéticos de pruebas quedarán excluidos del informe de ejecución.

Las capturas se enlazan desde su ubicación existente. No se insertan imágenes vacías ni se atribuyen a una captura métricas que no contiene.

El documento Markdown se organiza por contenido y evidencia, sin una extensión prefijada. La generación del PDF no forma parte de esta entrega.

### Comportamiento esperado por caso

| Caso | Condición | Resultado esperado |
|---|---|---|
| C-01 | Evidencia real completa y H1 confirmada | Informe muestra datos y criterios satisfechos con fuentes |
| C-02 | Evidencia completa y H1 refutada | Informe conserva el resultado y propone análisis/remediación sustentados |
| C-03 | Ensayo abortado o evidencia incompleta | Resultado no evaluable o parcial con su diagnóstico |
| C-04 | E2 y E3 sin ejecución | Solo hipótesis y diseños, sin resultados observados |
| C-05 | Capturas ausentes | Ausencia explícita; enlaces únicamente a archivos existentes |
| C-06 | Markdown entregado sin PDF | RF-008 puede validarse; RF-009 continúa pendiente |

## Tareas

Las tareas marcadas con `[P]` pueden ejecutarse en paralelo entre sí; las demás siguen el orden listado.

| Estado | # | Tarea | Criterio de aceptación |
|---|---|---|---|
| [x] | 1 | Generar informe Markdown desde los artefactos reales | Valores y análisis concuerdan con `summary.json` |
| [x] | 2 | Seleccionar capturas para integrar | Dos capturas existentes respaldan inyección y análisis |
| [x] | 3 | Revisar enlaces y capturas | Todos los enlaces relativos resuelven a archivos existentes |
| [x] | 4 | Comparar esperado y observado | Métricas, persistencia, recuperación y correlación se reportan desde evidencia |
| [x] | 5 | Registrar transferencia y estado de RF-009 | Documento Markdown entregado; PDF diferido |

## Validación

| Estado | Tipo | Qué verifica | Cómo se ejecuta | Resultado esperado |
|---|---|---|---|---|
| Confirmada | Estática sobre archivos | RF-008, RNF-004 | Revisar `results.md`, vínculo de captura y cifras contra `summary.json` | Valores coinciden; trazas de los timeouts elegibles correlacionadas |
| Confirmada | Editorial | RF-008, RNF-005 | Revisar hipótesis, tablas, conclusiones y captura seleccionada | E2/E3 se presentan como diseños independientes; H1 aceptada según el ensayo ejecutado |
| Pendiente | Entregable PDF | RF-009 | Generación fuera de esta entrega | Sin afirmaciones de cumplimiento de RF-009 |

La evidencia de `fase4-01` tiene integridad completa y el informe registra la aceptación de H1 para las condiciones observadas. Incluye la captura de inyección y el diagnóstico intermedio de correlación, identificado como reemplazado por el análisis final. El alcance Markdown de esta fase queda entregado y revisado; RF-009 y cualquier salida PDF quedan fuera de esta entrega.

## Riesgos y bloqueantes de la fase

| Estado | Elemento | Impacto | Mitigación o siguiente acción |
|---|---|---|---|
| Abierto | Confundir planificación con resultados reales | Alto | Estados y tablas separadas; exigir artefactos del ensayo |
| Resuelto en esta entrega | Selección de capturas | Bajo | Enlazar inyección y diagnóstico intermedio de `fase4-01`, identificando el recálculo final |
| Diferido | PDF | RF-009 pendiente | Tratarlo como entregable separado |

## Cierre de la fase

Sección de cierre de la entrega Markdown.

- **Resultado obtenido:** Informe `results.md` generado para `fase4-01`, con mediciones, captura de inyección y diagnóstico intermedio de correlación.
- **Desviaciones respecto al diseño:** La correlación por identificadores enlaza respuestas 504, logs y spans del flujo.
- **Decisiones tomadas durante la fase:** El informe Markdown se organiza según el contenido y las pruebas disponibles; el PDF queda diferido.
- **Requisitos afectados en su cobertura:** RF-008 entregado con H1 aceptada para el ensayo; RNF-004 y RNF-005 reflejan las mediciones y correlación. RF-009 queda fuera de esta entrega.
- **Actualizaciones aplicadas a `00-plan-general.md`:** Entrega Markdown completada; PDF diferido y cobertura actualizada.
- **Actualizaciones aplicadas a `00-especificacion.md`:** Ninguna; los requisitos originales se conservan.
- **Pendientes trasladados:** H2, H3 y el PDF corresponden a ejecuciones o entregas independientes.
