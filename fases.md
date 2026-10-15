Fase 1 — Instrumentación con OTel SDK:
Instrumentar ambos servicios con OTel SDK: auto-instrumentation para HTTP y DB, custom spans para lógica de negocio crítica.
Emitir los 3 pilares: métricas (OTel → Prometheus endpoint), logs (structured JSON con trace_id/span_id), trazas (OTLP → OTel Collector).