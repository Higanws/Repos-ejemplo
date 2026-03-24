locals {
  name_prefix = "${var.project}-${var.environment}"
  env_key     = "PIPE#${var.project}#${var.environment}"
  ssm_prefix  = var.ssm_parameter_prefix != "" ? var.ssm_parameter_prefix : "/${var.project}/${var.environment}/pipeline"
}
