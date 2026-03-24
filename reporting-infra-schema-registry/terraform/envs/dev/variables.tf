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

variable "schema_registry_repository_root" {
  type        = string
  default     = null
  description = "Raíz absoluta del repo reporting-infra-schema-registry."
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

variable "phase3_state_bucket" {
  type    = string
  default = "ngel-reporting-tfstate-sa1-131189842834-sa-east-1-an"
}

variable "phase3_state_key" {
  type    = string
  default = "reporting-phase3-redshift/dev/terraform.tfstate"
}

variable "phase3_state_region" {
  type    = string
  default = "sa-east-1"
}

variable "invoke_on_apply" {
  type        = bool
  default     = true
  description = "Si true, Terraform invoca la Lambda en cada apply."
}

variable "invoke_target" {
  type        = string
  default     = "all"
  description = "all|glue|redshift"
}

variable "invoke_force_ddl" {
  type        = bool
  default     = false
  description = "Si true, no omite tablas ya existentes."
}
