variable "aws_region" {
  description = "Región AWS del laboratorio observable."
  type        = string
  default     = "us-east-1"
}

variable "allowed_cidr" {
  description = "CIDR IPv4 autorizado para APIs públicas (catálogo, pedidos) y consolas (Grafana, Jaeger, Prometheus)."
  type        = string
  validation {
    condition     = can(cidrnetmask(var.allowed_cidr)) && var.allowed_cidr != "0.0.0.0/0"
    error_message = "allowed_cidr debe ser un CIDR IPv4 válido y no puede ser 0.0.0.0/0."
  }
}

variable "image_tag" {
  description = "Tag inmutable de las imágenes publicadas en ECR."
  type        = string
  default     = "obs-v1"
}

variable "desired_count" {
  description = "Tareas por servicio ECS. 0 detiene el cómputo sin destruir la infraestructura."
  type        = number
  default     = 1
}

variable "alert_email" {
  description = "Correo suscrito al tópico de alertas enriquecidas (requiere confirmar la suscripción). Vacío = sin correo."
  type        = string
  default     = ""
}

variable "latency_slo_ms" {
  description = "SLO de latencia p99 por servicio (ms). Las claves deben coincidir con el campo service de los logs."
  type        = map(number)
  default = {
    "catalog"      = 150
    "orders"       = 400
    "data-service" = 300
  }
}

variable "static_error_rate_pct" {
  description = "Umbral estático de tasa de error (%) usado como línea base de ruido frente a la regla AIOps."
  type        = number
  default     = 1
}

variable "anomaly_band_stddev" {
  description = "Ancho de la banda de anomalías en desviaciones estándar (2 = baseline + 2σ)."
  type        = number
  default     = 2
}

variable "db_engine_version" {
  description = "Versión de PostgreSQL en Amazon RDS."
  type        = string
  default     = "17.6"
}

variable "db_instance_class" {
  description = "Clase de instancia RDS del laboratorio."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_performance_insights" {
  description = "Habilita Performance Insights (necesario para DevOps Guru for RDS)."
  type        = bool
  default     = true
}

variable "enable_devops_guru" {
  description = "Cobertura de DevOps Guru por etiqueta sobre data-service y RDS. El servicio deja de aceptar clientes nuevos el 29-10-2026."
  type        = bool
  default     = true
}

variable "enable_security_hub" {
  description = "Habilita Security Hub CSPM y el estándar AWS Foundational Security Best Practices. Desactivar si la cuenta ya lo tiene habilitado."
  type        = bool
  default     = true
}

variable "enable_inspector" {
  description = "Habilita Amazon Inspector para imágenes ECR (CVEs activos)."
  type        = bool
  default     = true
}

variable "enable_guardduty" {
  description = "Habilita GuardDuty (opcional; hallazgos adicionales en Security Hub)."
  type        = bool
  default     = false
}

variable "container_insights" {
  description = "Container Insights del cluster: disabled, enabled o enhanced."
  type        = string
  default     = "disabled"
}

variable "log_retention_days" {
  description = "Retención de los grupos de logs del laboratorio."
  type        = number
  default     = 3
}
