locals {
  repo_root        = coalesce(var.schema_registry_repository_root, abspath("${path.module}/../../.."))
  name_prefix      = "${var.project}-${var.environment}"
  athena_output_s3 = "s3://${data.terraform_remote_state.phase2.outputs.s3_athena_results_bucket}/schema-registry/"
}
