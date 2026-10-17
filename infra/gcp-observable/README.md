# GCP — referencia del data-service con Cloud SQL (no aplicada)

Este directorio documenta la contraparte GCP del Módulo A/C de ID-003: el mismo contenedor
`services/data` desplegado en Cloud Run con acceso privado a Cloud SQL for PostgreSQL 17,
VPC Flow Logs en la subred y una política de alerta en Cloud Monitoring.

**Estado:** IaC de referencia. Por decisión de alcance (ID-003, D-301) la validación funcional se
ejecuta únicamente en AWS; aquí no se ejecutó `terraform validate`, `plan` ni `apply`.
El data-service ya admite este destino sin cambios de código: `DB_CLOUD_PROVIDER=gcp`, `DB_SSLMODE=require`
y las mismas convenciones OTel DB (`db.system.name=postgresql`, `db.namespace=pipeline|data`).

Pendientes para activarlo: proyecto con facturación, Artifact Registry con la imagen, un Collector
alcanzable por OTLP desde Cloud Run, inicializar el esquema `data` (rol `data_app`) y Security Command Center.
