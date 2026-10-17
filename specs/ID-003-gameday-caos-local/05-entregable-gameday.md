# ID-003 — Fase 05: Entregable del Game Day

## Identificación

| Campo | Detalle |
|---|---|
| **Plan** | ID-003 — Game Day de caos local |
| **Fase** | 05 — Entregable del Game Day |
| **Estado** | Pendiente |
| **Requisitos que cubre** | RF-008, RF-009, RNF-004, RNF-005 |
| **Sistemas y repositorios** | Informe Markdown y evidencias locales del Game Day |
| **Dependencias previas** | Fase 04 con experimento ejecutado, análisis y evidencias verificadas |
| **Habilita a** | Revisión general del plan; entrega posterior del PDF |

## Objetivo

Producir un informe Markdown que permita revisar hipótesis, diseños, observabilidad y resultados reales del experimento local. El requisito original de PDF de cuatro a cinco páginas quedará identificado como pendiente hasta producir y revisar ese archivo.

## Contexto de la fase

El [requerimiento original](../../requeimientos.md) exige un PDF de cuatro a cinco páginas. La entrega inmediata autorizada comprende la especificación y planificación en Markdown; el informe ejecutado y el PDF son entregables futuros. La preparación editorial del contenido no acredita haber ejecutado un experimento ni haber generado un PDF.

## Alcance técnico

### Cambios previstos

| Ubicación | Cambio | Requisito asociado |
|---|---|---|
| `scripts/chaos/report.py` futuro | Generar informe desde evidencia validada | RF-008, RNF-004 |
| `artifacts/chaos/<run-id>/results.md` | Informe con resultados, enlaces y limitaciones reales | RF-008, RNF-005 |
| Organización editorial del informe | Preparar contenido para PDF posterior de 4–5 páginas | RF-009 |

### No incluido en esta fase

- Instalar motores de render ni implementar exportación a PDF durante la entrega Markdown.
- Inventar capturas, valores de métricas, debilidades observadas o resultados de experimentos no ejecutados.
- Ejecutar E2 y E3 para completar visualmente el informe; ambos permanecen como diseños.

## Diseño

La interfaz futura será `python3 scripts/chaos/report.py artifacts/chaos/ID`. Leerá artefactos del ID seleccionado, validará su consistencia mediante el mismo analizador de fase 03 y escribirá únicamente `results.md` dentro de esa ejecución. No accederá a servicios, no lanzará el experimento y no alterará los registros originales. Si faltan evidencias obligatorias, rechazará la presentación de conclusiones como verificadas e indicará la limitación; un resultado refutado debe poder informarse.

El informe tendrá esta secuencia:

1. Objetivo, arquitectura local, aislamiento, versión del formato e identificación del ensayo.
2. Las tres hipótesis con su redacción completa y tabla de los tres experimentos: tipo, impacto, duración y reversión. Explicación conceptual de Chaos Monkey, Gremlin o Litmus sin afirmar su instalación.
3. Indicadores, carga, ventanas, umbrales de laboratorio y evidencia esperada. Separación explícita entre SLI de negocio y readiness.
4. E1 ejecutado: configuración efectiva, baseline, fallo, drenaje y recuperación; tabla de esperado frente a obtenido con número de muestras, porcentajes, p95, errores, persistencia, tiempo de recuperación y resultado por criterio.
5. Debilidad sistémica sustentada por evidencia, remediación propuesta, prioridad y validación futura. Si la evidencia no permite identificar una debilidad adicional, se registrará esa limitación y lo aprendido sobre el comportamiento controlado.
6. Limitaciones, estado de reversión y enlaces relativos a datos originales, logs, trazas y capturas existentes.

Las conclusiones se derivarán del ensayo real de fase 04. H2 y H3 mostrarán estado «Solo diseño; sin ejecución» y no tendrán columna de resultados numéricos fabricados. Los datos sintéticos de pruebas quedarán excluidos del informe de ejecución.

Las capturas serán aportadas manualmente y solo se enlazarán si existen en los artefactos. Se podrá completar el informe Markdown sin capturas, declarando su ausencia. No se insertarán imágenes vacías ni se asegurará que una captura demuestra métricas que no contiene.

Para el PDF posterior se propone distribuir el contenido en cinco páginas: contexto e hipótesis; diseños; observabilidad y procedimiento; resultados reales; reflexión, remediación y fuentes. Podrán usarse cuatro páginas si sigue siendo legible. La extensión será una propiedad del PDF exportado, no una deducción por cantidad de líneas Markdown. No se elegirá ni instalará un renderer en esta entrega. RF-009 seguirá pendiente hasta comprobar archivo, apertura y extensión de cuatro a cinco páginas; ello no bloquea la entrega Markdown, pero sí el cumplimiento completo del requerimiento original.

### Comportamiento esperado por caso

| Caso | Condición | Resultado esperado |
|---|---|---|
| C-01 | Evidencia real completa y H1 confirmada | Informe muestra datos y criterios satisfechos con fuentes |
| C-02 | Evidencia completa y H1 refutada | Informe conserva el resultado y propone análisis/remediación sustentados |
| C-03 | Ensayo abortado o evidencia incompleta | Resultado no evaluable o parcial y causa visible; no declarar cumplimiento |
| C-04 | E2 y E3 sin ejecución | Solo hipótesis y diseños, sin resultados observados |
| C-05 | Capturas ausentes | Ausencia explícita; enlaces únicamente a archivos existentes |
| C-06 | Markdown entregado sin PDF | RF-008 puede validarse; RF-009 continúa pendiente |

## Tareas

Las tareas marcadas con `[P]` pueden ejecutarse en paralelo entre sí; las demás siguen el orden listado.

| Estado | # | Tarea | Criterio de aceptación |
|---|---|---|---|
| [ ] | 1 | Implementar generador del informe con analizador compartido | Reproduce valores desde artefactos sin llamadas externas |
| [ ] | 2 | `[P]` Preparar estructura editorial del PDF futuro | Contenido completo organizable en 4–5 páginas |
| [ ] | 3 | `[P]` Revisar enlaces y capturas aportadas | Ningún enlace a evidencia inexistente ni secretos |
| [ ] | 4 | Generar y revisar informe del ensayo real | Comparación esperado/obtenido y reflexión trazables |
| [ ] | 5 | Registrar transferencia y RF-009 diferido | Markdown y PDF tienen estados separados y honestos |

## Validación

| Estado | Tipo | Qué verifica | Cómo se ejecuta | Resultado esperado |
|---|---|---|---|---|
| Pendiente | Automatizada futura | RF-008 y RNF-004 | `python3 -m unittest discover -s tests/chaos -p 'test_*.py'` | Generación determinista; casos incompletos y refutados cubiertos sin servicios |
| Pendiente | Estática futura | Estructura, indicadores y enlaces | `python3 scripts/chaos/check_evidence.py artifacts/chaos/ID` y revisión de `results.md` | Cifras reproducibles, enlaces existentes, ausencia de afirmaciones sin evidencia |
| Pendiente de confirmación | Funcional / operativa | Informe basado en E1 real | Después de fase 04: `python3 scripts/chaos/report.py artifacts/chaos/ID`; contrastar tabla con datos del mismo ID | Resultado y limitaciones coinciden con el ensayo |
| Pendiente de confirmación | Entregable diferido | RF-009 | Abrir el PDF que se genere posteriormente y comprobar contenido y 4–5 páginas | Archivo legible con todos los apartados y extensión requerida |
| Pendiente | Reversión | Preservación de evidencia | Regenerar solo `results.md` desde los mismos artefactos y comparar resultados | Archivos de origen intactos; salida reproducible |

Los comandos son interfaces futuras. Mientras exista validación funcional pendiente tras implementar, el estado será `Implementada sin validar`; la fase actual permanece `Pendiente`. La entrega Markdown no autoriza marcar RF-009 como validado.

## Riesgos y bloqueantes de la fase

| Estado | Elemento | Impacto | Mitigación o siguiente acción |
|---|---|---|---|
| Abierto | Confundir planificación con resultados reales | Alto | Estados y tablas separadas; exigir artefactos del ensayo |
| Abierto | Capturas no disponibles | Bajo | Conservar evidencia textual y declarar pendiente visual |
| Abierto | PDF todavía no generado | Alto para RF-009 | Registrar entregable diferido y validar páginas después de su exportación |

## Cierre de la fase

Sección pendiente de ejecutar el Gate 3 de [GUIA-AGENTE.md](../GUIA-AGENTE.md).

- **Resultado obtenido:** No implementado: entrega actual de planificación del informe.
- **Desviaciones respecto al diseño:** Ninguna registrada.
- **Decisiones tomadas durante la fase:** Ninguna de implementación; diferimiento del PDF documentado en la especificación.
- **Requisitos afectados en su cobertura:** RF-008, RF-009, RNF-004 y RNF-005 planificados; PDF sin producir y ejecución pendiente.
- **Actualizaciones aplicadas a `00-plan-general.md`:** Fase planificada con estado Pendiente y RF-009 explícitamente diferido.
- **Actualizaciones aplicadas a `00-especificacion.md`:** Ningún cambio del requerimiento original; el PDF continúa exigido.
- **Pendientes trasladados:** Generación del informe tras fase 04, capturas manuales y generación/revisión posterior del PDF.
