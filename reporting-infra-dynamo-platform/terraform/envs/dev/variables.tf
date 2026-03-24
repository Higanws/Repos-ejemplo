variable "aws_region" {
  type    = string
  default = "sa-east-1"
}

variable "project" {
  type    = string
  default = "reporting"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "retention_days" {
  type        = number
  default     = 30
  description = "Corridas con business_date más antigua que hoy - retention_days son candidatas al archivo semanal."
}

variable "archive_schedule_cron" {
  type        = string
  default     = "cron(0 0 ? * MON *)"
  description = "UTC. Job semanal (lunes 00:00 UTC). Ajustar según TZ de negocio."
}

variable "enable_archive_lambda" {
  type        = bool
  default     = true
  description = "Si false, solo se crean tabla S3 e IAM base (útil para pruebas incrementales)."
}

variable "ssm_parameter_prefix" {
  type        = string
  default     = ""
  description = "Prefijo SSM; por defecto /{project}/{environment}/dynamodb/..."
}
