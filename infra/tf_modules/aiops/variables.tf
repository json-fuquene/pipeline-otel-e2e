variable "name" { type = string }
variable "aws_region" { type = string }
variable "otel_log_group_name" { type = string }
variable "otel_log_group_arn" { type = string }
variable "flow_log_group_name" { type = string }
variable "findings_log_group_name" { type = string }
variable "ecs_log_group_name" { type = string }
variable "vpc_cidr" { type = string }
variable "extra_query_log_group_arns" {
  description = "Grupos de logs que la Lambda puede consultar además de los logs OTel."
  type        = list(string)
  default     = []
}
variable "latency_slo_ms" {
  description = "Umbral de latencia p99 (SLO) por servicio, en milisegundos."
  type        = map(number)
}
variable "static_error_rate_pct" {
  description = "Umbral estático de tasa de error usado como línea base de comparación de ruido."
  type        = number
}
variable "anomaly_band_stddev" {
  description = "Ancho de la banda de anomalías en desviaciones estándar (2 = baseline + 2σ)."
  type        = number
}
variable "alert_email" { type = string }
variable "lambda_source_dir" { type = string }
variable "log_retention_days" { type = number }
variable "enable_devops_guru" { type = bool }
variable "devops_guru_tag_key" { type = string }
variable "devops_guru_tag_value" { type = string }
variable "tags" { type = map(string) }
