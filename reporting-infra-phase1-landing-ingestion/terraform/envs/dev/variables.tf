variable "aws_region" {
  type        = string
  description = "Región AWS"
}

variable "project" {
  type        = string
  default     = "reporting"
  description = "Prefijo de nombres"
}

variable "environment" {
  type        = string
  default     = "dev"
  description = "dev | test | prod (debe coincidir con los JSON en lambdas/raw_ingestion/*/config/)"
}

variable "phase1_repository_root" {
  type        = string
  default     = null
  description = "Raíz absoluta de este repo si Terraform no vive en terraform/envs/<dev|test|prod> respecto a lambdas/ y orchestration/."
}

variable "ingest_schedule_cron" {
  type        = string
  default     = "cron(0 14 * * ? *)"
  description = "Cron EventBridge para SFN 04 (ingesta API → RAW)."
}

variable "enable_ingest_schedule" {
  type        = bool
  default     = false
  description = "Habilita/deshabilita la regla programada de EventBridge para ingesta API."
}

variable "enable_s3_eventbridge_raw" {
  type        = bool
  default     = true
  description = "Notificaciones EventBridge en RAW (útil cuando exista fase 4 con router)."
}

variable "s3_kms_key_arn" {
  type    = string
  default = null
}

variable "s3_abort_multipart_days" {
  type    = number
  default = 7
}

variable "s3_transition_current_to_ia_days" {
  type     = number
  default  = null
  nullable = true
}

# --- Secrets Manager (ingesta) ---
variable "create_ingest_api_secret" {
  type        = bool
  default     = true
  description = "Si es false, no crea el secreto (usalo si ya existe en AWS con el mismo nombre)."
}

variable "ingest_api_secret_name" {
  type        = string
  default     = "reporting/dev/apis/finanzas"
  description = "Nombre del secreto; debe coincidir con api_secret_name en lambdas/raw_ingestion/*/config/{env}.json"
}

variable "ingest_api_secret_string" {
  type        = string
  default     = null
  sensitive   = true
  nullable    = true
  description = "Opcional: token en texto plano o JSON {\"token\":\"...\"}. Si es null, creás el valor en la consola AWS después del apply. No commitear en Git."
}

# --- CloudWatch (logs Lambda ingesta) ---
variable "lambda_log_retention_days" {
  type        = number
  default     = 14
  description = "Días de retención de /aws/lambda/...-run-raw-api-ingestion. 0 = sin expirar (no recomendado)."
}

# --- DynamoDB pipeline_runs (repo reporting-infra-dynamo-platform) ---
variable "enable_pipeline_dynamo" {
  type        = bool
  default     = false
  description = "Si true, lee remote state del repo dynamo-platform, adjunta IAM y expone PIPELINE_RUNS_TABLE en la Lambda de ingesta."
}

variable "dynamo_platform_state_bucket" {
  type        = string
  default     = "angel-reporting-tfstate"
  description = "Bucket del state de reporting-infra-dynamo-platform."
}

variable "dynamo_platform_state_key" {
  type        = string
  default     = "reporting-dynamo-platform/dev/terraform.tfstate"
  description = "Key del state de dynamo-platform (mismo env que esta fase)."
}

variable "contract_set_version_phase1" {
  type        = string
  default     = ""
  description = "Opcional: versión del registry de contratos RAW (variable CONTRACT_SET_VERSION en Lambda)."
}

variable "enable_pipeline_ddb_stream_chain" {
  type        = bool
  default     = false
  description = "Si true y enable_pipeline_dynamo: la cadena entre fases sigue vía DynamoDB Stream (routers en fase 2/3); el estado RAW se escribe en Dynamo desde esta Lambda."
}

variable "pipeline_raw_tables" {
  type        = string
  default     = "trade_event,price_history"
  description = "Tablas que deben estar en validated antes de emitir capa raw completa (separadas por coma)."
}
