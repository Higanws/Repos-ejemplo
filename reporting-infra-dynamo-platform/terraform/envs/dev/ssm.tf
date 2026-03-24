resource "aws_ssm_parameter" "pipeline_runs_table_name" {
  name  = "${local.ssm_prefix}/dynamodb/pipeline_runs_table_name"
  type  = "String"
  value = aws_dynamodb_table.pipeline_runs.name
}

resource "aws_ssm_parameter" "pipeline_runs_table_arn" {
  name  = "${local.ssm_prefix}/dynamodb/pipeline_runs_table_arn"
  type  = "String"
  value = aws_dynamodb_table.pipeline_runs.arn
}

resource "aws_ssm_parameter" "pipeline_env_key" {
  name  = "${local.ssm_prefix}/dynamodb/env_key"
  type  = "String"
  value = local.env_key
}

resource "aws_ssm_parameter" "dynamo_archive_bucket" {
  name  = "${local.ssm_prefix}/dynamodb/archive_bucket_name"
  type  = "String"
  value = aws_s3_bucket.dynamo_archive.bucket
}

resource "aws_ssm_parameter" "iam_policy_pipeline_runs_arn" {
  name  = "${local.ssm_prefix}/iam/policy_pipeline_runs_access_arn"
  type  = "String"
  value = aws_iam_policy.pipeline_phases_dynamo.arn
}
