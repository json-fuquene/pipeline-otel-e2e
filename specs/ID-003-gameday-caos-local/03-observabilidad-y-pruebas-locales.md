# ID-003 — Fase 03: Observabilidad y pruebas locales

## Identificación

| Campo | Detalle |
|---|---|
| **Plan** | ID-003 — Game Day de caos local |
| **Fase** | 03 — Observabilidad y pruebas locales |
| **Estado** | Implementada sin validar |
| **Requisitos que cubre** | RF-003, RNF-003, RNF-004, RNF-005 |
| **Sistemas y repositorios** | Telemetría local, scripts de caos y pruebas unitarias |
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
| `docker/otel-collector/chaos.yaml` y captura del laboratorio | Salida detallada, métricas crudas y logs acotados por ejecución | RF-003, RNF-004 |
| `scripts/chaos/check_evidence.py`, `analyze.py` y módulos compartidos | Verificar integridad y calcular indicadores offline desde artefactos | RF-003, RNF-004 |
| `tests/chaos/` | Pruebas unitarias aisladas de análisis, carga y limpieza | RNF-003, RNF-004, RNF-005 |

### No incluido en esta fase

- Instalar Prometheus, Grafana o Jaeger; consultar AWS o APIs remotas.
- Ejecutar integración, E2E, builds o servicios durante esta implementación.
- Dar por verificada una hipótesis a partir de pruebas con datos sintéticos.

## Diseño

Los artefactos vivirán bajo `artifacts/chaos/<run-id>/` y se conservarán aun cuando el ensayo aborte. La estructura mínima será:

| Artefacto | Contrato mínimo |
|---|---|
| `metadata.json` | Identificador, `format_version: 2`, `evidence_kind: measured` o `synthetic`, configuración no sensible, imágenes utilizadas, semilla e identificadores del producto y pedido de control, ventanas UTC y duración monotónica |
| `requests.jsonl` | Una línea por intento con UUID de solicitud, operación, ventana de inicio, inicio/fin UTC, duración monotónica, estado HTTP o error de transporte, `error.code` y UUID del recurso exitoso si existe; sin cuerpos ni credenciales |
| `events.jsonl` | Preparación, activación, vencimiento, aborto, retirada y verificación; tiempo UTC y monotónico; destinatario IP/puerto y causa |
| `metrics/` y `metrics/index.jsonl` | Muestras Prometheus crudas de catálogo y pedidos cada 5 s; índice con UTC, monotónico del host, fase, HTTP, archivo, hash SHA-256 y errores |
| `logs/` | stdout y stderr combinados de ambas APIs, auxiliar y Collector; JSON y salida detallada acotados temporalmente al ensayo |
| `summary.json` | Indicadores derivados, número de muestras, cobertura de evidencia, hipótesis aceptada/refutada/inconclusa y motivos |
| `results.md` | Informe legible generado en fase 05 a partir de evidencia validada |

El registro canónico del SLI es `requests.jsonl`, porque permite asociar solicitudes a ventanas y usar la misma definición entre servicios. Prometheus aporta confirmación agregada; los nombres de las series se descubren de la exposición real y se registran en metadatos, sin fijar nombres inventados de instrumentación automática. La captura utiliza un hilo por servicio; un error de captura activa aborto, queda registrado y no se disimula como muestra válida.

La verificación exige secuencias contiguas por servicio, SHA-256 coincidente, al menos `max(1, ceil(duración/5)-2)` muestras por ventana y separaciones máximas de diez segundos incluyendo los bordes. El reconocimiento de muestras numéricas usa un perfil acotado del formato de exposición; los formatos no reconocidos quedan incompletos. No se exige un nombre específico de instrumentación.

Los tiempos usan el dominio monotónico declarado. UTC sirve para correlación, no para restar relojes de procesos distintos. Los límites del IPC `host_before`/`host_after` y `removed_monotonic` del supervisor permiten construir límites conservadores de activación y retirada sin asumir que coinciden los relojes de host y contenedor. Los registros de dominio o identidad inconsistentes invalidan evidencia; la incertidumbre no se convierte en una ventana de fallo más amplia.

Se calcularán indicadores por operación y ventana, sin mezclar POST, GET y healthchecks:

- Éxito POST = respuestas `201` / intentos iniciados en la ventana; errores de transporte cuentan como fallo.
- Éxito de cada GET de control = respuestas `200` / intentos de esa operación.
- p95 por rango más próximo: ordenar duraciones y seleccionar el elemento `ceil(0,95 × N)` con índice inicial uno. Incluye intentos fallidos y sus timeouts; `N=0` produce indicador no evaluable.
- Proporción `504 catalog_timeout` = respuestas con ambos valores / intentos de la ventana estable de fallo; debe alcanzar 95 %. Proporción temporal = respuestas `504 catalog_timeout` de 4,5–6,5 s / total de respuestas `504 catalog_timeout` elegibles; debe alcanzar 95 %. Exigir al menos treinta intentos elegibles; un denominador cero no es evaluable.
- Persistencia: el conjunto exacto de UUID de pedidos finales debe coincidir con el conjunto inicial unido a los UUID únicos retornados por creaciones `201`, incluyendo tránsito. No basta comparar cantidades; discrepancias, duplicados o identificadores ausentes impiden aceptar integridad.
- Recuperación: tiempo desde retirada confirmada hasta primera readiness exitosa de pedidos, con resolución de 5 s, y criterios de éxito/p95 de la ventana de recuperación de 60 s. Readiness no forma parte del SLI de negocio.

Se conservan por separado baseline, fallo estable, drenaje y recuperación, además de los intentos de transición. Baseline y recuperación exigen al menos sesenta creaciones y sesenta intentos por cada lectura de control, 100 % de éxito y p95 inferior a un segundo. La readiness debe recuperarse en sesenta segundos. Para fallo estable se eligen únicamente intentos iniciados al menos diez segundos después de la activación conservadora y terminados antes de la retirada conservadora. Un incumplimiento observado se reporta sin eliminar muestras; la ausencia de evidencia necesaria da resultado inconcluso, nunca confirmación. Los errores de transporte y solicitudes pendientes al corte conservan su registro y resultado final; permanecen visibles en tasas globales y transición.

Para E2 se diseñan tasa de creaciones exitosas >=99 %, p95 <2 s y muestras de CPU de catálogo cada 5 s; spans de catálogo y de su cliente permiten localizar la degradación. Para E3 se diseñan los indicadores de timeout, controles, persistencia y recuperación de E1, reduciendo solo la duración de fallo a 30 s; se exige al menos diez intentos elegibles. CPU y pérdida efectiva deberán demostrarse en caso de ejecutar esos diseños, pero no se implementarán recolectores ni ejecuciones adicionales en este alcance.

La configuración propia del laboratorio usa `exporters.debug.verbosity: detailed` y batch local de un segundo. La [guía oficial del Collector](https://opentelemetry.io/docs/collector/troubleshooting/) documenta la inspección con salida detallada; no se presupone que garantice entrega completa ni se añaden parámetros de muestreo sin respaldo documental. La configuración general existente se preserva. Los logs Docker se acotan con `--since` al inicio y `--until` al final de la captura; se concede un margen adicional de exportación de doce segundos antes de recopilar el Collector. La falta de trazas requeridas produce evidencia incompleta e hipótesis inconclusa.

La correlación exige al menos una creación de la fase de fallo con log JSON de pedidos cuyo `request_id`, estado y `trace_id` coincidan, más un span cliente HTTP hacia catálogo y su relación padre con `orders.order.create`. Para un `504 catalog_timeout`, el span cliente debe registrar estado de error. Una creación exitosa también puede aportar correlación para una hipótesis refutada. No se exige correlacionar todas las solicitudes ni un span servidor de catálogo cuando la inyección impide la recepción. El parser de debug admite el formato textual acotado cubierto por pruebas; otro formato se reporta como incompleto, sin inferir spans ausentes. La ausencia de un span servidor no demuestra por sí sola la inyección.

Las pruebas unitarias usan fixtures sintéticos identificados como tales, reloj simulado y adaptadores locales simulados. Cubren clasificación temporal, p95, denominadores, resultados incompletos, transporte fallido, persistencia discrepante, destinos cambiantes, temporizador, interrupción y limpieza repetida. No hacen llamadas HTTP, Docker ni accesos externos. Los fixtures no se guardan como resultados reales: con `evidence_kind: synthetic`, `hypothesis` siempre es inconclusa y `calculated_hypothesis` expone únicamente el resultado del cálculo probado.

`python3 scripts/chaos/check_evidence.py artifacts/chaos/ID` es solo de lectura y emite JSON por stdout: salida cero con evidencia completa y consistente; salida uno con archivos ausentes, formato inválido o inconsistencias. Una hipótesis refutada con datos completos no constituye error estructural. `python3 scripts/chaos/analyze.py artifacts/chaos/ID` realiza el mismo análisis offline y escribe `summary.json`; no consulta servicios ni genera `results.md`, reservado a fase 05. El formato versión 2 es obligatorio; artefactos previos no se presentan como evidencia completa mediante valores inventados.

El verificador no exige `summary.json`, pero lo compara exactamente con el cálculo si ya existe. `analyze.py` escribe únicamente ese archivo y `run` lo genera automáticamente al finalizar. La evidencia exige metadatos permitidos y `cleanup_verified: true`; corridas abortadas, formato anterior o tiempos inconsistentes quedan inconclusos. El runner distingue `evidence_incomplete` cuando la limpieza se verificó de `cleanup_unverified` cuando falta comprobarla.

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
| [x] | 1 | Implementar contrato de artefactos y cálculo de indicadores | Formato versión 2 y análisis offline reproducible |
| [x] | 2 | `[P]` Preparar configuración detallada y captura acotada | Captura de métricas crudas y configuración propia del Collector |
| [x] | 3 | `[P]` Implementar pruebas y verificador de evidencia | Casos sintéticos aislados y verificador de solo lectura |
| [x] | 4 | Documentar comandos y transferir observación a fase 04 | Checks locales separados de operación manual |

## Validación

| Estado | Tipo | Qué verifica | Cómo se ejecuta | Resultado esperado |
|---|---|---|---|---|
| Aprobada: 90 pruebas en 2,122 s | Automatizada local | RF-003, RNF-004 y RNF-005 | `python3 -m unittest discover -s tests/chaos -p 'test_*.py'` | Suite conjunta del harness y evidencia aprobada; fixtures únicamente en directorios temporales |
| Aprobada | Estática local | RNF-003 y contrato de evidencia | Verificador y analizador sobre fixtures temporales identificados, invocados desde las unitarias; AST de 11 archivos y ayuda CLI | Campos y cálculo consistentes; hipótesis refutada completa con salida cero; evidencia incompleta con salida uno; sintaxis y ayuda correctas |
| Aprobada | Estática Compose | RNF-003 y aislamiento de configuración | Normalización local sin daemon | Collector del laboratorio montado en solo lectura y puertos en loopback; configuración habitual preservada |
| Pendiente de confirmación | Funcional / operativa | RF-003 en E1 real | Tras fase 04, ejecutar el verificador sobre su ID y contrastar una solicitud con logs y span cliente | Indicadores reproducibles y trazabilidad de extremo a extremo cuando haya recepción |
| Pendiente | Reversión | Configuración aislada | Detener el manifiesto autónomo del laboratorio y revisar que no modificó configuración general | Telemetría habitual preservada y artefactos conservados |

Las interfaces están implementadas. La evidencia sintética prueba el analizador y nunca se almacena como corrida real bajo `artifacts/chaos/`. La validación funcional pendiente conserva el estado `Implementada sin validar`.

## Riesgos y bloqueantes de la fase

| Estado | Elemento | Impacto | Mitigación o siguiente acción |
|---|---|---|---|
| Abierto | Pérdida de trazas al detener el Collector | Alto | Capturar antes del apagado y comprobar completitud |
| Abierto | Bajo número de muestras o ventanas contaminadas | Medio | Registrar N y tránsito; resultado no evaluable cuando no alcance evidencia |
| Abierto | Credenciales en metadatos o comandos | Alto | Lista permitida de configuración no sensible; no copiar `.env` ni cuerpos |

## Cierre de la fase

Transferencia documental del Gate 3 de [GUIA-AGENTE.md](../GUIA-AGENTE.md); el cierre operativo permanece pendiente.

- **Resultado obtenido:** Captura avanzada, Collector aislado, analizador offline y verificador implementados; suite conjunta de 90 pruebas aprobada en 2,122 s, AST de once archivos, ayuda CLI y Compose normalizado correctos; sin corrida real.
- **Desviaciones respecto al diseño:** Contrato de artefactos versión 2 y límites temporales conservadores explícitos; formatos debug no reconocidos producen evidencia incompleta. Se añade `analyze.py` para producir summary.json y se reserva results.md a fase 05.
- **Decisiones tomadas durante la fase:** D-013 separa integridad de evidencia y resultado de hipótesis; D-014 explicita dominios temporales conservadores y límites de la salida detallada del Collector.
- **Requisitos afectados en su cobertura:** RF-003, RNF-003, RNF-004 y RNF-005 con implementación; confirmación operativa pendiente.
- **Actualizaciones aplicadas a `00-plan-general.md`:** Fase 03 Implementada sin validar; interfaces, evidencia y pendientes actualizados.
- **Actualizaciones aplicadas a `00-especificacion.md`:** Decisiones técnicas de fase 03 registradas; no se afirma ejecución ni resultado de hipótesis.
- **Pendientes trasladados:** Confirmar captura real, exportación detallada, correlación, límites temporales y reversión en fase 04; informe y capturas en fase 05.
