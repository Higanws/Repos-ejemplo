locals {
  # terraform/envs/<dev|test|prod> -> ../../.. = raíz de ESTE repo (landing + ingesta).
  phase1_repo_root = coalesce(var.phase1_repository_root, abspath("${path.module}/../../.."))

  name_prefix = "${var.project}-${var.environment}"

  lambda_ingest_env = merge(
    {
      RAW_BUCKET  = aws_s3_bucket.raw.bucket
      ENVIRONMENT = var.environment
    },
    var.enable_pipeline_dynamo ? merge(
      {
        PIPELINE_RUNS_TABLE = data.terraform_remote_state.dynamo_platform[0].outputs.dynamodb_table_name
        PROJECT             = var.project
        PIPELINE_ENV_KEY    = data.terraform_remote_state.dynamo_platform[0].outputs.env_key
        PIPELINE_RAW_TABLES = var.pipeline_raw_tables
      },
      var.contract_set_version_phase1 != "" ? { CONTRACT_SET_VERSION = var.contract_set_version_phase1 } : {}
    ) : {}
  )
}
