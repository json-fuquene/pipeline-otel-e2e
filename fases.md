## Fase 1 — Instrumentación con OTel SDK

- Instrumentar ambos servicios con OTel SDK:
  - auto-instrumentation para HTTP y DB
  - custom spans para lógica de negocio crítica
- Emitir los 3 pilares:
  - métricas: OTel → Prometheus endpoint
  - logs: structured JSON con trace_id/span_id
  - trazas: OTLP → OTel Collector

## Fase 2 — Despliegue del OTel Collector:
- Configurar el OTel Collector con:
  - receiver OTLP (gRPC + HTTP)
  - processor: batch, memory_limiter y resource
  - exporters hacia Jaeger (trazas), Prometheus (métricas) y Cloud Logging/CloudWatch (logs)
- Entorno de despliegue:
  - AWS: ECS Fargate

## Fase 3 — Visualización y correlación en ECS (despliegue de revisión 8 en curso; validación del dashboard y correlación log→traza pendientes):
- Trazas: conservar Jaeger UI dentro de ECS. Verificar en Jaeger/Grafana Explore la misma traza para el flujo pedidos → catálogo → PostgreSQL.
- Métricas: configurar Grafana efímero dentro de ECS, conectado a Prometheus y CloudWatch; aprovisionar un dashboard con 6 paneles:
  - Éxito HTTP de catálogo.
  - Latencia HTTP p95 de catálogo.
  - Éxito HTTP de pedidos.
  - Latencia HTTP p95 de pedidos.
  - Uso de CPU del servicio ECS.
  - Errores del contenedor OTel Collector.
- Logs: consultar CloudWatch Logs desde Grafana Explore y usar `trace_id` para localizar la traza correspondiente en Jaeger.
- Acceso: publicar Grafana solo para el CIDR permitido; aprovisionar credenciales y datasources sin secretos versionados.
- Alcance elegido: no desplegar Jaeger en GCP ni agregar AWS X-Ray o Tempo.

## Fase 4 — Análisis de Overhead

- Implementación local lista: ambas APIs permiten alternar OTel con `OTEL_ENABLED` (por defecto `true`); el runner y el escenario k6 están en `scripts/benchmark/`.
- Comparar ambas APIs en local bajo el mismo dataset, recursos y carga, con OTel activado y desactivado por una opción de configuración explícita.
- Usar k6 con una carga de llegada constante y endpoints de lectura de catálogo y pedidos; no crear datos durante las ventanas medidas.
- Medir p99 de latencia HTTP, CPU de los contenedores de aplicación y memoria de los contenedores. Calcular diferencia absoluta y relativa contra la ejecución sin OTel.
- Repetir ejecuciones, guardar salidas crudas y metadatos del entorno, y presentar una tabla comparativa. No declarar resultados ni conclusiones hasta que los benchmarks se ejecuten.
- Estado: mediciones pendientes. Para ejecutarlas, instala Docker Compose y k6, prepara `.env` mediante `python3 scripts/init-local-env.py`, libera los puertos 8001/8002 y ejecuta `scripts/benchmark/run-overhead.sh`. La configuración predeterminada realiza 6 corridas medidas de 180 s más 30 s de calentamiento por corrida (aprox. 21 min, además de la construcción de imágenes); los artefactos quedan en `artifacts/overhead/`.
- Especificación y procedimiento: [`04-analisis-overhead.md`](specs/ID-002-observabilidad-otel/04-analisis-overhead.md).
