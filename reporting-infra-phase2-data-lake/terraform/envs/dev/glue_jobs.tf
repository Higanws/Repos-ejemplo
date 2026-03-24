locals {
  glue_extra_py = {
    "--extra-py-files" = join(",", [
      "s3://${aws_s3_bucket.artifacts.bucket}/glue-scripts/jobs/pipeline_layer_gate.py",
      "s3://${aws_s3_bucket.artifacts.bucket}/glue-scripts/jobs/pipeline_contract_validate.py",
      "s3://${aws_s3_bucket.artifacts.bucket}/glue-scripts/jobs/pipeline_layer_finish.py",
    ])
  }
}
resource "aws_glue_job" "validated_to_standardized" {
  name         = "${local.name_prefix}-glue-grupo-finanzas-validated-to-std"
  role_arn     = aws_iam_role.glue_job.arn
  glue_version = "5.0"

  number_of_workers = var.glue_number_of_workers
  worker_type       = var.glue_worker_type

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${aws_s3_bucket.artifacts.bucket}/glue-scripts/jobs/validated_to_standardized.py"
  }

  default_arguments = merge(
    {
      "--job-language"                     = "python"
      "--enable-metrics"                   = "true"
      "--enable-continuous-cloudwatch-log" = "true"
      "--PRICE_HISTORY_SEP"                = ","
      "--ARTIFACTS_BUCKET"                 = aws_s3_bucket.artifacts.bucket
      "--GLUE_SQL_S3_PREFIX"               = "glue-sql/sqls"
      "--GLUE_PIPELINE_CONFIG_KEY"         = "glue-sql/config/glue_pipeline.json"
    },
    local.glue_extra_py,
    var.enable_pipeline_dynamo ? {
      "--PIPELINE_RUNS_TABLE" = data.terraform_remote_state.dynamo_platform[0].outputs.dynamodb_table_name
      "--PIPELINE_PROJECT"     = var.project
      "--PIPELINE_ENVIRONMENT" = var.environment
      "--GLUE_REGISTRY_KEY"    = "glue-data-lake/contracts/registry.input.json"
      "--GLUE_CONTRACTS_ROOT"  = "glue-data-lake/contracts"
    } : {},
  )

  depends_on = [
    aws_s3_object.glue_script_validated_to_standardized,
    aws_s3_object.glue_pipeline_config,
    aws_s3_object.pipeline_layer_gate,
    aws_s3_object.pipeline_contract_validate,
    aws_s3_object.pipeline_layer_finish,
  ]
}

resource "aws_glue_job" "standardized_to_silver" {
  name         = "${local.name_prefix}-glue-grupo-finanzas-std-to-silver"
  role_arn     = aws_iam_role.glue_job.arn
  glue_version = "5.0"

  number_of_workers = var.glue_number_of_workers
  worker_type       = var.glue_worker_type

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${aws_s3_bucket.artifacts.bucket}/glue-scripts/jobs/standardized_to_silver.py"
  }

  default_arguments = merge(
    {
      "--job-language"                     = "python"
      "--enable-metrics"                   = "true"
      "--enable-continuous-cloudwatch-log" = "true"
      "--ARTIFACTS_BUCKET"                 = aws_s3_bucket.artifacts.bucket
      "--GLUE_SQL_S3_PREFIX"               = "glue-sql/sqls"
      "--GLUE_PIPELINE_CONFIG_KEY"         = "glue-sql/config/glue_pipeline.json"
    },
    local.glue_extra_py,
    var.enable_pipeline_dynamo ? {
      "--PIPELINE_RUNS_TABLE" = data.terraform_remote_state.dynamo_platform[0].outputs.dynamodb_table_name
      "--PIPELINE_PROJECT"     = var.project
      "--PIPELINE_ENVIRONMENT" = var.environment
      "--GLUE_REGISTRY_KEY"    = "glue-data-lake/contracts/registry.input.json"
      "--GLUE_CONTRACTS_ROOT"  = "glue-data-lake/contracts"
    } : {},
  )

  depends_on = [
    aws_s3_object.glue_script_standardized_to_silver,
    aws_s3_object.glue_pipeline_config,
    aws_s3_object.pipeline_layer_gate,
    aws_s3_object.pipeline_contract_validate,
    aws_s3_object.pipeline_layer_finish,
  ]
}
