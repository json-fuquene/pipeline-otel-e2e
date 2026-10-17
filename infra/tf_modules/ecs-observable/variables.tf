variable "name" { type = string }
variable "aws_region" { type = string }
variable "environment" { type = string }
variable "desired_count" { type = number }
variable "image_tag" { type = string }
variable "ecr_urls" { type = map(string) }
variable "subnet_ids" { type = list(string) }
variable "security_group_id" { type = string }
variable "db_address" { type = string }
variable "db_port" { type = number }
variable "db_name" { type = string }
variable "db_master_secret_arn" { type = string }
variable "otel_log_group_name" { type = string }
variable "log_retention_days" { type = number }
variable "container_insights" {
  description = "enabled, enhanced o disabled. Agrega métricas por tarea/contenedor con costo adicional."
  type        = string
}
variable "extra_readable_log_group_arns" {
  description = "Grupos adicionales que Grafana puede consultar (flow logs, hallazgos, alertas)."
  type        = list(string)
  default     = []
}
variable "tags" { type = map(string) }
variable "devops_guru_tags" { type = map(string) }
