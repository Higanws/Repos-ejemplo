# Lambda dedicada: DynamoDB pipeline_runs + validación contratos S3 (paralelo a glue_job_status_dynamo en fase 2).
# Invocada síncronamente desde redshift_sql.

data "archive_file" "zip_pipeline_runs_dynamo" {
  count       = var.enable_pipeline_dynamo ? 1 : 0
  type        = "zip"
  source_dir  = "${local.phase3_repo_root}/lambdas/pipeline_runs_dynamo"
  output_path = "${path.module}/.build/pipeline_runs_dynamo.zip"
  excludes    = ["__pycache__", ".pytest_cache", "README.md"]
}

resource "aws_iam_role" "lambda_pipeline_runs_dynamo" {
  count = var.enable_pipeline_dynamo ? 1 : 0
  name  = "${local.name_prefix}-pipeline-runs-dynamo"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "pipeline_runs_dynamo_logs" {
  count      = var.enable_pipeline_dynamo ? 1 : 0
  role       = aws_iam_role.lambda_pipeline_runs_dynamo[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "pipeline_runs_dynamo_table" {
  count      = var.enable_pipeline_dynamo ? 1 : 0
  role       = aws_iam_role.lambda_pipeline_runs_dynamo[0].name
  policy_arn = data.terraform_remote_state.dynamo_platform[0].outputs.iam_policy_pipeline_runs_arn
}

resource "aws_iam_role_policy" "pipeline_runs_dynamo_s3_read" {
  count = var.enable_pipeline_dynamo ? 1 : 0
  name  = "s3-artifacts-silver-contracts"
  role  = aws_iam_role.lambda_pipeline_runs_dynamo[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["s3:GetObject", "s3:ListBucket"]
      Resource = [
        data.aws_s3_bucket.artifacts.arn,
        "${data.aws_s3_bucket.artifacts.arn}/*",
        data.aws_s3_bucket.silver.arn,
        "${data.aws_s3_bucket.silver.arn}/*"
      ]
    }]
  })
}

resource "aws_lambda_function" "pipeline_runs_dynamo" {
  count            = var.enable_pipeline_dynamo ? 1 : 0
  filename         = data.archive_file.zip_pipeline_runs_dynamo[0].output_path
  function_name    = "${local.name_prefix}-pipeline-runs-dynamo"
  role             = aws_iam_role.lambda_pipeline_runs_dynamo[0].arn
  handler          = "main.handler"
  runtime          = "python3.11"
  timeout          = 120
  source_code_hash = data.archive_file.zip_pipeline_runs_dynamo[0].output_base64sha256

  environment {
    variables = merge(
      {
        PIPELINE_RUNS_TABLE     = data.terraform_remote_state.dynamo_platform[0].outputs.dynamodb_table_name
        ARTIFACTS_BUCKET        = data.aws_s3_bucket.artifacts.bucket
        SILVER_BUCKET           = data.aws_s3_bucket.silver.bucket
        REDSHIFT_REGISTRY_KEY   = "redshift/contracts/registry.input.json"
        REDSHIFT_CONTRACTS_ROOT = "redshift/contracts"
        PROJECT                 = var.project
        ENVIRONMENT             = var.environment
      },
      var.pipeline_skip_layer_check ? { PIPELINE_SKIP_LAYER_CHECK = "true" } : {},
      var.pipeline_skip_contract_check ? { PIPELINE_SKIP_CONTRACT_CHECK = "true" } : {}
    )
  }

  depends_on = [
    aws_iam_role_policy_attachment.pipeline_runs_dynamo_logs,
    aws_iam_role_policy_attachment.pipeline_runs_dynamo_table
  ]
}
