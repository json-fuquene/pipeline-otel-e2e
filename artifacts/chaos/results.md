<div align="center">
<br><br><br>

# Observabilidad en ambientes productivos

### Game Day local · Resultados de E1

<br><br>

## Jeisson Fuquene<br>Santiago López Amaya

<br><br>

### Maestría en arquitectura de software

<br>

**María Ochoa**  
Universidad de La Sabana

<br><br><br>

17 de octubre de 2026

<br><br>

[Repositorio · rama `game-day`](https://github.com/json-fuquene/pipeline-otel-e2e/tree/game-day)

</div>

<div style="page-break-after: always;"></div>

# Game Day local: resultados de E1

## Resultado ejecutivo

Se aplicaron seis segundos de latencia al tráfico TCP de pedidos hacia catálogo durante la ventana de fallo. En las 45 solicitudes elegibles, el servicio respondió `504 catalog_timeout`, todas las duraciones quedaron entre 4,5 y 6,5 segundos y las 45 quedaron correlacionadas desde la respuesta hasta el log y la traza correspondiente. Cada traza contiene el span de negocio `orders.order.create` en error y su span HTTP cliente hijo hacia catálogo. Las lecturas de control siguieron respondiendo `200`; readiness de pedidos devolvió `503` durante el fallo y se recuperó después de retirar la latencia.

La persistencia quedó conciliada: el laboratorio pasó de un pedido semilla a 125 pedidos, con 124 creaciones exitosas y ninguna escritura inexplicada. El supervisor terminó `clean`, sin filtros propios activos, y el proyecto se detuvo conservando volumen y artefactos.

La correlación se establece por `request_id` entre la respuesta 504 y el log, y por `trace_id` entre el log y los spans de la misma operación. El span HTTP cliente figura con estado `Unset`; el span de negocio asociado figura en error. El contrato del experimento usa el estado del span cliente como señal diagnóstica y la presencia de ambos spans vinculados como evidencia de correlación. El verificador confirma integridad completa y calcula la clasificación de H1 como aceptada; el resultado conserva el indicador `requires_manual_confirmation` del flujo establecido.

## Hipótesis y alcance

| Hipótesis | Diseño | Resultado de esta entrega |
|---|---|---|
| H1 | Con seis segundos de latencia en pedidos → catálogo durante 60 s, las creaciones deberían terminar en `504 catalog_timeout` sin persistir pedidos fallidos, mientras las lecturas independientes siguen disponibles. | E1 ejecutado. Tasas, duraciones, correlación, controles, persistencia y recuperación cumplen sus umbrales. **Clasificación calculada: aceptada.** |
| H2 | Con carga de CPU controlada en catálogo, al menos 99 % de las creaciones deberían tener éxito y p95 menor de dos segundos. | Diseño definido para una ejecución independiente. |
| H3 | Al descartar el tráfico hacia catálogo, las creaciones deberían fallar de forma controlada y recuperarse al retirar la partición. | Diseño definido para una ejecución independiente. |

La ejecución usó un proyecto Compose aislado con catálogo, pedidos, PostgreSQL, Collector OpenTelemetry y un supervisor auxiliar en el espacio de red de pedidos. La regla `netem` afectó solo el destino de catálogo en TCP/8000. No se modificó el Compose cotidiano ni se ejecutaron experimentos de CPU o partición.

## Método y criterios

La carga programó una creación y dos lecturas de control por segundo, sin reintentar POST. Readiness y liveness se sondearon cada cinco segundos. Las ventanas fueron baseline 60 s, fallo 60 s, drenaje 15 s y recuperación 60 s. Los criterios de H1 requerían al menos 30 solicitudes elegibles, 95 % o más de `504 catalog_timeout`, 95 % o más de esos timeouts entre 4,5 y 6,5 s, controles sin fallos, persistencia conciliada y evidencia de trazas suficiente.

## Mediciones

| Ventana / señal | Esperado | Observado |
|---|---|---|
| Baseline: creación | 60 respuestas `201`; p95 < 1 s | 60/60 `201`; p95 0,050 s |
| Baseline: lecturas de catálogo y pedidos | 60 respuestas `200` por operación; p95 < 1 s | 60/60 en ambas; p95 0,025 s y 0,028 s |
| Fallo: POST programados | 60 intentos; sin reintentos | 60: 55 respuestas `504`, 4 `201` y 1 `503`; p95 5,034 s |
| Fallo: muestra estable elegible | ≥30 solicitudes; ≥95 % `504 catalog_timeout`; ≥95 % de esos timeouts entre 4,5–6,5 s | 45 elegibles; 45/45 `504 catalog_timeout`; 45/45 entre 4,5–6,5 s |
| Fallo: lecturas de control | 100 % `200`; p95 < 1 s | 60/60 por operación; p95 0,019 s en catálogo y 0,030 s en pedidos |
| Fallo: readiness de pedidos | Se registra aparte de liveness | 12/12 `503`; p95 2,052 s |
| Fallo: liveness | Sin fallos de proceso | 12/12 `200` en ambos servicios |
| Drenaje | Sin nuevas creaciones; solicitudes en tránsito conservadas | 15 s; 15/15 lecturas de control `200`; readiness volvió a `200` |
| Recuperación: creación | 60/60 `201`; p95 < 1 s | 60/60 `201`; p95 0,051 s |
| Recuperación: lecturas de control | 100 % `200`; p95 < 1 s | 60/60 por operación; p95 0,026 s en catálogo y 0,024 s en pedidos |
| Readiness después de retirar el fallo | `200` dentro de 60 s | 12/12 `200`; recuperación medida entre 1,19 y 1,46 s |
| Persistencia | Diferencia de pedidos igual a POST exitosos; sin escrituras inexplicadas | 1 antes, 125 después; 124 creaciones exitosas; diferencia inexplicada 0; UUID conciliados |
| Correlación | Emparejamiento request/log por `request_id` y log/traza por `trace_id`; span HTTP cliente hijo de `orders.order.create` | 45/45 timeouts elegibles correlacionados. En cada traza, el span de negocio está en error y el span HTTP cliente hijo hacia catálogo aparece con estado `Unset` |

Los valores de p95 se calculan por operación y no mezclan readiness con disponibilidad de negocio. Las cifras proceden del analizador y de la correlación directa de los artefactos de `fase4-01`; las muestras sintéticas de pruebas unitarias no se usan en este informe.

## Inyección y reversión

La captura muestra tráfico contabilizado por la regla `netem` durante el fallo y el supervisor en estado `clean` después de vencer el TTL. La instantánea final contiene `noqueue` y ningún filtro propio. `run.py down` dejó el proyecto `stopped`; el volumen y los artefactos permanecen disponibles.

![Estado activo de netem y limpieza automática del supervisor](../../../specs/ID-003-gameday-caos-local/evidencias/inyeccion-f4.png)

## Diagnóstico del primer cálculo

El primer cálculo encontró 45 timeouts elegibles, pero solo correlacionó cinco solicitudes de fallo y ninguna solicitud 504 elegible con su traza; por eso clasificó la hipótesis como inconclusa. La captura conserva ese diagnóstico intermedio. Tras ajustar la correlación para verificar la relación padre entre la llamada cliente y el span de negocio en error, el análisis final encontró las 45 solicitudes elegibles correlacionadas. El `summary.json` actual tiene integridad completa y H1 aceptada para las condiciones del ensayo.

![Diagnóstico intermedio de correlación, reemplazado por el análisis final](../../../specs/ID-003-gameday-caos-local/evidencias/recalculo-f4.png)

## Análisis y aprendizaje

Los resultados observados son consistentes con la dependencia síncrona de pedidos hacia catálogo: al degradarse esa llamada, las creaciones elegibles agotaron el límite de catálogo y readiness de pedidos también falló, mientras liveness y las lecturas independientes siguieron disponibles. Tras retirar la regla, las creaciones y readiness volvieron a responder dentro de los umbrales medidos.

La correlación confirma que cada uno de los 45 timeouts elegibles pertenece a una traza del flujo de creación: el `request_id` enlaza la respuesta con el log de pedidos y el `trace_id` enlaza ese log con el span de negocio y la llamada HTTP cliente hija hacia catálogo. El span de negocio en error coincide con el `504 catalog_timeout`; el cliente conserva estado `Unset`, que se interpreta como dato diagnóstico y no invalida el vínculo entre spans. La correlación, junto con las tasas, controles, persistencia y recuperación, sustenta la clasificación calculada de H1 como aceptada.

## Fuente del análisis

La ruta principal de evidencias de esta fase es `specs/ID-003-gameday-caos-local/evidencias/`.
