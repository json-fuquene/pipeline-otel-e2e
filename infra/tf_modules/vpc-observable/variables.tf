variable "name" { type = string }
variable "vpc_cidr" { type = string }
variable "allowed_cidr" { type = string }
variable "public_ports" {
  description = "Puertos publicados al CIDR autorizado (APIs públicas y consolas)."
  type        = list(number)
}
variable "flow_log_group_name" { type = string }
variable "log_retention_days" { type = number }
