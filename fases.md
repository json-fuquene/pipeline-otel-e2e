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

## Fase 3 — Visualización y correlación en ECS:
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
