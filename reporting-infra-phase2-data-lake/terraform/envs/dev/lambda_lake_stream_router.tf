# Router fase 2 (solo lake): DynamoDB Stream → Glue siguiente cuando raw / lake_validated_to_standardized pasan a SUCCEEDED.

locals {
  lake_stream_router_enabled = var.enable_pipeline_dynamo && var.enable_pipeline_ddb_stream_chain
}

data "archive_file" "zip_lake_stream_router" {
  count       = local.lake_stream_router_enabled ? 1 : 0
  type        = "zip"
  source_dir  = "${local.phase2_repo_root}/lambdas/lake_pipeline_stream_router"
  output_path = "${path.module}/.build/lake_pipeline_stream_router.zip"
}

resource "aws_iam_role" "lake_stream_router" {
  count = local.lake_stream_router_enabled ? 1 : 0
  name  = "${local.name_prefix}-lake-pipeline-stream-router"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lake_stream_router_logs" {
  count      = local.lake_stream_router_enabled ? 1 : 0
  role       = aws_iam_role.lake_stream_router[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lake_stream_router_glue" {
  count = local.lake_stream_router_enabled ? 1 : 0
  name  = "glue-start"
  role  = aws_iam_role.lake_stream_router[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["glue:StartJobRun"]
      Resource = [aws_glue_job.validated_to_standardized.arn, aws_glue_job.standardized_to_silver.arn]
    }]
  })
}

resource "aws_iam_role_policy" "lake_stream_router_ddb_stream" {
  count = local.lake_stream_router_enabled ? 1 : 0
  name  = "ddb-stream-read"
  role  = aws_iam_role.lake_stream_router[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "dynamodb:GetRecords",
        "dynamodb:GetShardIterator",
        "dynamodb:DescribeStream",
        "dynamodb:ListStreams",
      ]
      Resource = data.terraform_remote_state.dynamo_platform[0].outputs.dynamodb_stream_arn
    }]
  })
}

resource "aws_lambda_function" "lake_stream_router" {
  count            = local.lake_stream_router_enabled ? 1 : 0
  filename         = data.archive_file.zip_lake_stream_router[0].output_path
  function_name    = "${local.name_prefix}-lake-pipeline-stream-router"
  role             = aws_iam_role.lake_stream_router[0].arn
  handler          = "main.handler"
  runtime          = "python3.12"
  timeout          = 120
  source_code_hash = data.archive_file.zip_lake_stream_router[0].output_base64sha256

  environment {
    variables = {
      PROJECT                        = var.project
      ENVIRONMENT                    = var.environment
      PIPELINE_RUNS_TABLE            = data.terraform_remote_state.dynamo_platform[0].outputs.dynamodb_table_name
      GLUE_JOB_VALIDATED_TO_STD_NAME = aws_glue_job.validated_to_standardized.name
      GLUE_JOB_STD_TO_SILVER_NAME    = aws_glue_job.standardized_to_silver.name
    }
  }
}

resource "aws_lambda_event_source_mapping" "lake_stream_router" {
  count                          = local.lake_stream_router_enabled ? 1 : 0
  event_source_arn               = data.terraform_remote_state.dynamo_platform[0].outputs.dynamodb_stream_arn
  function_name                  = aws_lambda_function.lake_stream_router[0].arn
  starting_position              = "LATEST"
  batch_size                     = 10
  maximum_batching_window_in_seconds = 5
  bisect_batch_on_function_error = true
}
