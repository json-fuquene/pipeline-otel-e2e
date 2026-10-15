variable "aws_region" {
  description = "Región AWS para el laboratorio ECS."
  type        = string
  default     = "us-east-1"
}

variable "allowed_cidr" {
  description = "CIDR IPv4 autorizado para acceder a las APIs y consolas del laboratorio."
  type        = string
  default     = "181.61.246.55/32"
  validation {
    condition     = can(cidrnetmask(var.allowed_cidr)) && var.allowed_cidr != "0.0.0.0/0"
    error_message = "allowed_cidr debe ser un CIDR IPv4 válido y no puede ser 0.0.0.0/0."
  }
}

variable "image_tag" {
  description = "Etiqueta idéntica de las imágenes publicadas en ECR."
  type        = string
  default     = "phase2-test-4"
}

variable "desired_count" {
  description = "Cantidad de tareas ECS; una tarea agrupa las APIs y los backends efímeros."
  type        = number
  default     = 1
}
