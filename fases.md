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