variable "aws_region" {
  type = string
}

variable "project" {
  type    = string
  default = "reporting"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "phase3_repository_root" {
  type        = string
  default     = null
  description = "Raíz absoluta de este repo si movés terraform/ respecto a redshift/ y lambdas/."
}

variable "schema_registry_repository_root" {
  type        = string
  default     = null
  description = "Raíz absoluta del repo reporting-infra-schema-registry (si null usa repo hermano)."
}

variable "phase1_state_bucket" {
  type    = string
  default = "ngel-reporting-tfstate-sa1-131189842834-sa-east-1-an"
}

variable "phase1_state_key" {
  type    = string
  default = "reporting-phase1-landing-ingestion/dev/terraform.tfstate"
}

variable "phase1_state_region" {
  type    = string
  default = "sa-east-1"
}

variable "phase2_state_bucket" {
  type    = string
  default = "ngel-reporting-tfstate-sa1-131189842834-sa-east-1-an"
}

variable "phase2_state_key" {
  type    = string
  default = "reporting-phase2-data-lake/dev/terraform.tfstate"
}

variable "phase2_state_region" {
  type    = string
  default = "sa-east-1"
}

variable "redshift_base_capacity" {
  type    = number
  default = 8
}

variable "redshift_sql_secret_arn" {
  type     = string
  default  = null
  nullable = true
}

variable "redshift_publicly_accessible" {
  type    = bool
  default = false
}

variable "enable_pipeline_dynamo" {
  type        = bool
  default     = false
  description = "Si true, Lambda redshift_sql lee/escribe DynamoDB y valida capa lake_standardized_to_silver."
}

variable "dynamo_platform_state_bucket" {
  type    = string
  default = "angel-reporting-tfstate"
}

variable "dynamo_platform_state_key" {
  type    = string
  default = "reporting-dynamo-platform/dev/terraform.tfstate"
}

variable "pipeline_skip_layer_check" {
  type        = bool
  default     = false
  description = "Si true, env PIPELINE_SKIP_LAYER_CHECK=true (no validar capa anterior en Dynamo)."
}

variable "pipeline_skip_contract_check" {
  type        = bool
  default     = false
  description = "Si true, env PIPELINE_SKIP_CONTRACT_CHECK=true (no validar contratos S3 antes de COPY)."
}

variable "enable_pipeline_ddb_stream_chain" {
  type        = bool
  default     = false
  description = "Si true: despliega redshift_sfn_stream_router (stream → SFN COPY/gold). Requiere enable_pipeline_dynamo y stream en dynamo-platform."
}

variable "pipeline_copy_scripts_order" {
  type        = string
  default     = "copy_s3_to_silver/trade_event_parquet_s3_to_silver_fact.sql,copy_s3_to_silver/price_history_parquet_s3_to_silver_fact.sql"
  description = "Debe coincidir con fase 2 / router; último script emite capa redshift_silver."
}

variable "pipeline_gold_scripts_order" {
  type        = string
  default     = "silver_to_gold/silver_facts_to_gold_silver_pnl_daily.sql,silver_to_gold/gold_silver_pnl_daily_to_gold_report_pnl.sql"
  description = "Último script emite capa gold."
}
