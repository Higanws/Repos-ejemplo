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

variable "phase2_repository_root" {
  type        = string
  default     = null
  description = "Raíz absoluta de este repo si movés terraform/ respecto a glue-data-lake/ y lambdas/."
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

variable "glue_worker_type" {
  type    = string
  default = "G.1X"
}

variable "glue_number_of_workers" {
  type    = number
  default = 2
}

variable "enable_pipeline_dynamo" {
  type        = bool
  default     = false
  description = "Si true, Lambda glue_job_status_dynamo escribe capas Glue en DynamoDB (remote state dynamo-platform)."
}

variable "glue_auto_chain_to_next_job" {
  type        = bool
  default     = true
  description = "Si true y enable_pipeline_dynamo, al terminar OK el job validated→std arranca std→silver directo (ignorado si enable_pipeline_ddb_stream_chain: el encadenamiento va por DynamoDB Stream / routers por fase)."
}

variable "enable_pipeline_ddb_stream_chain" {
  type        = bool
  default     = false
  description = "Si true: lake_pipeline_stream_router (esta fase) consume el stream y arranca Glue; en fase 3 redshift_sfn_stream_router arranca las SFN. Requiere stream en dynamo-platform y enable_pipeline_dynamo."
}

variable "dynamo_platform_state_bucket" {
  type    = string
  default = "angel-reporting-tfstate"
}

variable "dynamo_platform_state_key" {
  type    = string
  default = "reporting-dynamo-platform/dev/terraform.tfstate"
}
