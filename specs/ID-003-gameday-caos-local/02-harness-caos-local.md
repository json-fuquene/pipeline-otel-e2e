# ID-003 — Fase 2: Harness de caos local

## Identificación

| Campo | Detalle |
|---|---|
| **Plan** | ID-003 — Game Day de caos local |
| **Fase** | 2 — Harness de caos local |
| **Estado** | Pendiente |
| **Requisitos que cubre** | RF-002, RF-004; RNF-001, RNF-002, RNF-003, RNF-004 |
| **Sistemas y repositorios** | Compose local, auxiliar de red y scripts del proyecto |
| **Dependencias previas** | Fase 1; daemon local con NET_ADMIN y netem por confirmar |
| **Habilita a** | Fase 4; avance paralelo con fase 3 |

## Objetivo

Disponer de una ejecución de latencia selectiva, identificable y reversible sin afectar la instancia cotidiana ni la red del host.

## Contexto de la fase

Pedidos consulta catálogo antes de persistir y limita esa operación a cinco segundos. Las aplicaciones no necesitan endpoints de fallo ni cambios de timeout. El auxiliar debe ser el único componente con privilegios de red añadidos.

## Alcance técnico

### Cambios previstos

| Ubicación | Cambio | Requisito asociado |
|---|---|---|
| `compose.chaos.yaml` | Manifiesto autónomo con mismos builds, migraciones y healthchecks; volumen propio y puertos loopback dinámicos | RNF-001, RNF-003 |
| `docker/chaos/` | Imagen auxiliar con Python e iproute2, supervisor y watchdog | RF-004, RNF-002 |
| `scripts/chaos/run.py` | CLI prepare/run/rollback/status/down y coordinación de carga | RF-004, RNF-004 |
| `tests/chaos/` | Pruebas locales con comandos y reloj simulados | RNF-002 |

### No incluido en esta fase

- Implementar CPU o partición; sus fichas pertenecen a fase 1.
- Análisis de métricas y presentación de resultados, definidos en fases 3–5.
- Montaje del socket Docker en contenedores, modo host, contenedor privilegiado o cambios a las APIs.

## Diseño

### Identidad y ciclo de vida

`python3 scripts/chaos/run.py prepare --run-id ID` valida identificador, contexto local y ausencia de corrida previa; prepara archivos privados de configuración, construye y arranca `chaos-ID`. Obtiene puertos asignados y siembra un producto y un pedido de control. No usa ni imprime las credenciales de `.env` existente; genera credenciales propias en archivo privado excluido del versionado y de la evidencia pública. No guardar configuración Compose interpolada con contraseñas.

El cliente ejecuta Docker desde el host. Antes de cualquier operación futura se verifica por configuración local que no hay destino Docker remoto; si lo hay, se detiene y se aplica la autorización de recursos externos. No se hacen sondeos para descubrir identidad o destino.

`run --run-id ID` rechaza corridas ya ejecutadas, comprueba pertenencia de contenedores mediante etiquetas y conserva estados en events.jsonl. La secuencia es preflight → baseline → inyección → fallo → retirada → drenaje → recuperación → captura final. Se rechaza una segunda inyección concurrente. `status` muestra únicamente estado saneado, plazos y reglas propias. `rollback` retira reglas idempotentemente. `down` primero exige limpieza comprobada y detiene únicamente el proyecto identificado, conservando su volumen; no incorpora opción de borrado de datos.

### Inyección y reversión

El auxiliar comparte `network_mode: service:orders`, sin puertos propios ni red adicional, con `cap_drop: ALL` y `cap_add: NET_ADMIN`. El proceso que ejecuta tc opera como root solo dentro de ese contenedor. Resolver catálogo a IPv4 y determinar la interfaz desde la ruta del contenedor, sin asumir `eth0`. Fijar IPv4 para las llamadas del laboratorio; abortar si existe camino alternativo no cubierto.

Inspeccionar qdisc y filtros antes de actuar. Admitir únicamente la configuración vacía/predeterminada no administrada; rechazar handles ajenos y no usar `replace` sobre reglas desconocidas. Crear un árbol `prio` propio con todo el tráfico no coincidente dirigido a una banda sin netem. Añadir filtro IPv4 TCP por destino catálogo/32 y puerto destino 8000 hacia una banda con `netem delay 6000ms`. No retrasar DNS, PostgreSQL, OTLP, métricas ni respuestas hacia el host. Conservar clasificación y contadores antes/durante/después. La selección y sus límites se sustentan en el [manual tc-netem](https://man7.org/linux/man-pages/man8/tc-netem.8.html); el detalle de comandos debe comprobarse mediante las pruebas locales antes de utilizarlo.

Un supervisor independiente dentro del auxiliar mantiene el plazo y una concesión de diez segundos renovada por el runner. Armar y confirmar el watchdog antes de instalar reglas; TTL máximo sesenta segundos desde el inicio de la instalación. Si falta renovación, retirar antes. La expiración, SIGTERM/SIGINT y cualquier error parcial invocan la misma retirada idempotente de handles propios. Si falla el runner, el supervisor continúa; si falla el auxiliar, no se garantiza limpieza automática y el ensayo se declara inconcluso hasta comprobar la red. Nunca declarar reversión solo porque terminó un proceso.

La implementación confirmará retirada normal no después de cinco segundos desde el vencimiento del TTL, y no después de quince segundos desde la pérdida de renovación, bajo infraestructura operativa. La precisión temporal es un objetivo de laboratorio por validar, no garantía del kernel. Si cambia la IP de catálogo, se aborta: no se expande el filtro a toda la red.

### Carga

Sesenta segundos de baseline; sesenta de fallo; quince de drenaje sin nuevas creaciones; sesenta de recuperación. Programar 1 POST /orders por segundo con hasta diez solicitudes concurrentes y timeout ocho segundos. Programar además 1 GET de producto y 1 GET del pedido sembrado por segundo. Readiness cada cinco segundos y liveness para control; excluir ambas de SLI de negocio. Omitir una solicitud por falta de capacidad del generador invalida la corrida, sin ocultar la omisión.

Cada solicitud lleva UUID request_id único, hora UTC, fase y reloj monotónico para duración. No reintentar POST. El primer fallo al control o liveness, escritura inconsistente, pérdida de captura o watchdog no disponible detiene inyección y pasa a captura/limpieza. Una hipótesis de timeout refutada no obliga por sí sola a abortar si todos los controles siguen seguros.

### Comportamiento esperado por caso

| Caso | Condición | Resultado esperado |
|---|---|---|
| C-001 | Baseline válido | Todas las creaciones 201, controles 200, p95 menor de 1 s |
| C-002 | Regla activa | Solo dependencia HTTP afectada; 504 controlados sin escritura |
| C-004 | Runner interrumpido | Watchdog retira por concesión o TTL; evidencia de limpieza |
| C-005 | Reglas ajenas o destino ambiguo | Rechazo antes de modificar tráfico |
| C-006 | Daemon/auxiliar perdido | Marcar inconcluso y bloquear reutilización hasta limpieza comprobada |

## Tareas

| Estado | # | Tarea | Criterio de aceptación |
|---|---|---|---|
| [ ] | 1 | Implementar manifiesto e identidad aislada | Mismos servicios funcionales, volumen propio y puertos loopback |
| [ ] | 2 | Implementar CLI y archivo privado de credenciales | Sin lectura de credenciales existentes ni secretos en logs |
| [ ] | 3 | Implementar clasificación, supervisor y retirada | Solo destino/puerto acordado; TTL y concesión independientes |
| [ ] | 4 | Implementar carga, estados y aborto | Frecuencia y ventanas registradas; solicitudes omitidas detectadas |
| [ ] | 5 | `[P]` Probar seguridad de comandos y limpieza con dobles | Casos de error parcial, repetición y destino incorrecto cubiertos |
| [ ] | 6 | Documentar prueba operativa manual | Incluye interrupción, rollback y conservación de datos |

## Validación

Todos los comandos se refieren a herramientas futuras, no disponibles por crear este documento.

| Estado | Tipo | Qué verifica | Cómo se ejecuta | Resultado esperado |
|---|---|---|---|---|
| Pendiente | Automatizada | RNF-001, RNF-002, RNF-003 | `python3 -m unittest discover -s tests/chaos -p 'test_*.py'` | Sin acceso Docker real; filtros, TTL, renovación, limpieza y secreto probados |
| Pendiente de confirmación | Funcional | RF-004, RNF-001 | `python3 scripts/chaos/run.py prepare --run-id ensayo-01` | Laboratorio aislado y preflight aprobado |
| Pendiente de confirmación | Funcional | RF-004 | `python3 scripts/chaos/run.py run --run-id ensayo-01` | Secuencia completa, tráfico selectivo y retirada registrada |
| Pendiente de confirmación | Reversión | RNF-002 | En corrida nueva, interrumpir el runner con SIGINT durante fallo; después `python3 scripts/chaos/run.py status --run-id ensayo-02` | Sin reglas propias y plazo de limpieza verificado |
| Pendiente de confirmación | Reversión | RNF-002 | `python3 scripts/chaos/run.py rollback --run-id ensayo-02`, repetir el mismo comando | Dos salidas correctas; segunda sin cambios |
| Pendiente de confirmación | Persistencia | RNF-003 | `python3 scripts/chaos/run.py down --run-id ensayo-01` | Solo proyecto de ensayo detenido; volumen conservado |

La interrupción abrupta del runner y los errores del auxiliar se validan en corridas separadas de la corrida de resultados. Una vez implementada, esta fase queda `Implementada sin validar` mientras falten confirmaciones operativas.

## Riesgos y bloqueantes de la fase

| Estado | Elemento | Impacto | Mitigación o siguiente acción |
|---|---|---|---|
| Abierto | Daemon local/capacidades no comprobados | Alto | Confirmación manual previa a inyección |
| Abierto | Clasificación incorrecta o qdisc ajeno | Alto | Rechazo conservador, contadores y controles |
| Abierto | Caída del auxiliar o daemon | Alto | Registrar límite; exigir inspección y rollback antes de reutilizar |

## Cierre de la fase

- **Resultado obtenido:** No implementado; diseño documentado.
- **Desviaciones respecto al diseño:** Ninguna.
- **Decisiones tomadas durante la fase:** D-004, D-005 y D-007 definen el diseño previsto.
- **Requisitos afectados en su cobertura:** RF-002 y RF-004; RNF-001 a RNF-004: implementación y validación pendientes.
- **Actualizaciones aplicadas a `00-plan-general.md`:** Fase pendiente, interfaces y riesgos documentados.
- **Actualizaciones aplicadas a `00-especificacion.md`:** Ninguna adicional al diseño acordado.
- **Pendientes trasladados:** Implementación de fase 2 y validación operativa previa a fase 4.
