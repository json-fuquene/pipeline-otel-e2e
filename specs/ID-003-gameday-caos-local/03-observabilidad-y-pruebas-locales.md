# ID-003 — Fase 03: Observabilidad y pruebas locales

## Identificación

| Campo | Detalle |
|---|---|
| **Plan** | ID-003 — Game Day de caos local |
| **Fase** | 03 — Observabilidad y pruebas locales |
| **Estado** | Pendiente |
| **Requisitos que cubre** | RF-003, RNF-003, RNF-004, RNF-005 |
| **Sistemas y repositorios** | Telemetría local, scripts futuros de caos y pruebas unitarias |
| **Dependencias previas** | Diseño de fase 01; contrato de artefactos de fase 02; fase 02 necesaria para validación operativa |
| **Habilita a** | Fases 04 y 05 |

## Objetivo

Contar con evidencia correlacionada y un análisis reproducible para evaluar hipótesis sin depender de capturas ni servicios remotos. Las verificaciones unitarias y estáticas quedarán separadas de la confirmación funcional local.

## Contexto de la fase

Las APIs ya exponen métricas Prometheus, logs JSON y trazas OTLP; el Collector actual permite inspección mediante `debug`, sin almacenamiento ni búsqueda de trazas. El [README](../../README.md) establece correlación por `request_id`, `trace_id` y `span_id`, además de exclusión de healthchecks de los spans. Se necesita conservar evidencia del ensayo antes de detener el laboratorio. No se cambiarán contratos de las APIs para lograrlo.

## Alcance técnico

### Cambios previstos

| Ubicación | Cambio | Requisito asociado |
|---|---|---|
| Configuración específica del Collector del laboratorio | Activar salida detallada y conservarla por ejecución | RF-003, RNF-004 |
| `scripts/chaos/check_evidence.py` y analizador compartido futuro | Verificar integridad y calcular indicadores desde artefactos | RF-003, RNF-004 |
| `tests/chaos/` | Pruebas unitarias aisladas de análisis, carga y limpieza | RNF-003, RNF-004, RNF-005 |

### No incluido en esta fase

- Instalar Prometheus, Grafana o Jaeger; consultar AWS o APIs remotas.
- Ejecutar integración, E2E, builds o servicios por iniciativa de la implementación documental.
- Dar por verificada una hipótesis a partir de pruebas con datos sintéticos.

## Diseño

Los artefactos vivirán bajo `artifacts/chaos/<run-id>/` y se conservarán aun cuando el ensayo aborte. La estructura mínima será:

| Artefacto | Contrato mínimo |
|---|---|
| `metadata.json` | Identificador, versión del formato, configuración no sensible, imágenes utilizadas, semilla e identificadores del producto y pedido de control, ventanas UTC y duración monotónica |
| `requests.jsonl` | Una línea por intento con UUID de solicitud, operación, ventana de inicio, inicio/fin UTC, duración monotónica, estado HTTP o error de transporte, `error.code` y UUID del recurso exitoso si existe; sin cuerpos ni credenciales |
| `events.jsonl` | Preparación, activación, vencimiento, aborto, retirada y verificación; tiempo UTC y monotónico; destinatario IP/puerto y causa |
| `metrics/` | Muestras Prometheus de catálogo y pedidos cada 5 s con fecha y ventana; fallos de muestreo explícitos |
| `logs/` | Logs JSON de ambas APIs y salida detallada del Collector, acotados temporalmente al ensayo |
| `summary.json` | Indicadores derivados, número de muestras, cobertura de evidencia, hipótesis aceptada/refutada/inconclusa y motivos |
| `results.md` | Informe legible generado en fase 05 a partir de evidencia validada |

El registro canónico del SLI será `requests.jsonl`, porque permite asociar solicitudes a ventanas y usar la misma definición entre servicios. Prometheus aportará confirmación agregada; los nombres de las series se descubrirán de la exposición real y se registrarán en metadatos, sin fijar nombres inventados de instrumentación automática. Los tiempos se medirán con reloj monotónico; UTC servirá para correlación.

Se calcularán indicadores por operación y ventana, sin mezclar POST, GET y healthchecks:

- Éxito POST = respuestas `201` / intentos iniciados en la ventana; errores de transporte cuentan como fallo.
- Éxito de cada GET de control = respuestas `200` / intentos de esa operación.
- p95 por rango más próximo: ordenar duraciones y seleccionar el elemento `ceil(0,95 × N)` con índice inicial uno. Incluye intentos fallidos y sus timeouts; `N=0` produce indicador no evaluable.
- Proporción `504 catalog_timeout` = respuestas con ambos valores / intentos de la ventana estable de fallo; debe alcanzar 95 %. Proporción temporal = respuestas `504 catalog_timeout` de 4,5–6,5 s / total de respuestas `504 catalog_timeout` elegibles; debe alcanzar 95 %. Exigir al menos treinta intentos elegibles; un denominador cero no es evaluable.
- Persistencia indebida = incremento total de pedidos del laboratorio menos creaciones confirmadas con `201`, contrastado con identificadores retornados. Debe ser cero; el pedido sembrado se cuenta en el estado inicial. La comprobación exige exclusividad del laboratorio y lectura paginada de todos sus pedidos antes y después, incluyendo solicitudes en tránsito.
- Recuperación: tiempo desde retirada confirmada hasta primera readiness exitosa de pedidos, con resolución de 5 s, y criterios de éxito/p95 de la ventana de recuperación de 60 s. Readiness no forma parte del SLI de negocio.

Se conservarán por separado las solicitudes que crucen límites de ventanas. Para la ventana estable de fallo se elegirán únicamente las iniciadas al menos diez segundos después de la activación y terminadas antes de la retirada. Un incumplimiento observado se reportará sin eliminar muestras; la ausencia de evidencia necesaria da resultado inconcluso, nunca confirmación. Los errores de transporte y solicitudes pendientes al corte conservan su registro y resultado final; se reportan en las tasas globales y en el grupo de transición cuando no cumplen la ventana elegible.

Para E2 se diseñan tasa de creaciones exitosas >=99 %, p95 <2 s y muestras de CPU de catálogo cada 5 s; spans de catálogo y de su cliente permiten localizar la degradación. Para E3 se diseñan los indicadores de timeout, controles, persistencia y recuperación de E1, reduciendo solo la duración de fallo a 30 s; se exige al menos diez intentos elegibles. CPU y pérdida efectiva deberán demostrarse en caso de ejecutar esos diseños, pero no se implementarán recolectores ni ejecuciones adicionales en este alcance.

La configuración propia del laboratorio usará `exporters.debug.verbosity: detailed`; este nivel está documentado en la [guía oficial del Collector](https://opentelemetry.io/docs/collector/troubleshooting/). La configuración general existente se preservará. El archivo detallado debe permitir seguir una creación mediante `X-Request-ID`, logs y traza. Se exigirá evidencia del span cliente HTTP de pedidos y del error propagado; no se exigirá span servidor de catálogo cuando la inyección impida que la solicitud llegue. No se considerará ausencia de ese span como prueba suficiente de la inyección.

Las pruebas unitarias usarán fixtures sintéticos identificados como tales, reloj simulado y adaptadores locales simulados. Cubrirán clasificación temporal, p95, denominadores, resultados incompletos, transporte fallido, persistencia discrepante, destinos cambiantes, temporizador, interrupción y limpieza repetida. No harán llamadas HTTP, Docker ni accesos externos. Los fixtures no se guardarán como resultados reales.

`python3 scripts/chaos/check_evidence.py artifacts/chaos/ID` será una interfaz futura, solo de lectura: salida cero con estructura suficiente y cálculo consistente; salida distinta de cero con archivos ausentes, formato inválido o inconsistencias. Una hipótesis refutada con datos completos no constituye error estructural. El informe distinguirá integridad de evidencia de resultado de resiliencia.

### Comportamiento esperado por caso

| Caso | Condición | Resultado esperado |
|---|---|---|
| C-01 | Solicitud finaliza fuera de su ventana | Se conserva como tránsito; no se reasigna |
| C-02 | Falta captura de métricas o traza relevante | Se registra limitación; hipótesis no evaluable si falta evidencia obligatoria |
| C-03 | Collector no recibe span de catálogo durante timeout | Puede ser compatible con la inyección; evaluar span cliente y logs |
| C-04 | POST responde timeout de transporte | Cuenta como fallo y permanece visible en el denominador |
| C-05 | Incremento de pedidos no coincide con `201` | Señal de aborto y discrepancia de persistencia |
| C-06 | Fixture sintético satisface todos los criterios | Solo demuestra funcionamiento del analizador, no éxito real del Game Day |

## Tareas

Las tareas marcadas con `[P]` pueden ejecutarse en paralelo entre sí; las demás siguen el orden listado.

| Estado | # | Tarea | Criterio de aceptación |
|---|---|---|---|
| [ ] | 1 | Implementar contrato de artefactos y cálculo de indicadores | Salidas reproducibles desde los mismos registros |
| [ ] | 2 | `[P]` Preparar configuración detallada y captura acotada | Logs y trazas correlacionables sin exposición de secretos |
| [ ] | 3 | `[P]` Implementar pruebas y verificador de evidencia | Casos de límite, ausencia y fallo cubiertos sin servicios |
| [ ] | 4 | Documentar comandos y transferir observación a fase 04 | Separación clara entre checks locales y validación operativa |

## Validación

| Estado | Tipo | Qué verifica | Cómo se ejecuta | Resultado esperado |
|---|---|---|---|---|
| Pendiente | Automatizada futura | RF-003, RNF-004 y RNF-005 | `python3 -m unittest discover -s tests/chaos -p 'test_*.py'` | Pruebas rápidas, aisladas y sin servicios aprobadas |
| Pendiente | Estática futura | RNF-003 y contrato de evidencia | `python3 scripts/chaos/check_evidence.py artifacts/chaos/ID` sobre fixture identificado | Campos y cálculo consistentes; sin secretos ni resultados presentados como reales |
| Pendiente de confirmación | Funcional / operativa | RF-003 en E1 real | Tras fase 04, ejecutar el verificador sobre su ID y contrastar una solicitud con logs y span cliente | Indicadores reproducibles y trazabilidad de extremo a extremo cuando haya recepción |
| Pendiente | Reversión | Configuración aislada | Detener el manifiesto autónomo del laboratorio y revisar que no modificó configuración general | Telemetría habitual preservada y artefactos conservados |

Los comandos corresponden a interfaces por implementar. Mientras exista validación funcional pendiente tras implementar, el estado será `Implementada sin validar`; actualmente permanece `Pendiente`.

## Riesgos y bloqueantes de la fase

| Estado | Elemento | Impacto | Mitigación o siguiente acción |
|---|---|---|---|
| Abierto | Pérdida de trazas al detener el Collector | Alto | Capturar antes del apagado y comprobar completitud |
| Abierto | Bajo número de muestras o ventanas contaminadas | Medio | Registrar N y tránsito; resultado no evaluable cuando no alcance evidencia |
| Abierto | Credenciales en metadatos o comandos | Alto | Lista permitida de configuración no sensible; no copiar `.env` ni cuerpos |

## Cierre de la fase

Sección pendiente de ejecutar el Gate 3 de [GUIA-AGENTE.md](../GUIA-AGENTE.md).

- **Resultado obtenido:** No implementado: contrato y validaciones documentados.
- **Desviaciones respecto al diseño:** Ninguna registrada.
- **Decisiones tomadas durante la fase:** Ninguna de implementación; decisiones de planificación en la especificación.
- **Requisitos afectados en su cobertura:** RF-003, RNF-003, RNF-004 y RNF-005 planificados; sin validación real.
- **Actualizaciones aplicadas a `00-plan-general.md`:** Fase planificada con estado Pendiente.
- **Actualizaciones aplicadas a `00-especificacion.md`:** Ningún cambio derivado de ejecución.
- **Pendientes trasladados:** Evidencia real a fase 04 y presentación del informe a fase 05.
