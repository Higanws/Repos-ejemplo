# Router fase 3: DynamoDB Stream → Step Functions (COPY Parquet→Redshift, luego gold).
# Código: ../../lambdas/redshift_sfn_stream_router/ (misma idea que lake_pipeline_stream_router en fase 2).

locals {
  redshift_sfn_stream_router_enabled = var.enable_pipeline_dynamo && var.enable_pipeline_ddb_stream_chain
  _copy_scripts                      = compact([for s in split(",", var.pipeline_copy_scripts_order) : trimspace(s)])
  _gold_scripts                      = compact([for s in split(",", var.pipeline_gold_scripts_order) : trimspace(s)])
  redshift_sfn_stream_router_deploy = local.redshift_sfn_stream_router_enabled && (length(local._copy_scripts) > 0 || length(local._gold_scripts) > 0)
}

data "archive_file" "zip_redshift_sfn_stream_router" {
  count       = local.redshift_sfn_stream_router_deploy ? 1 : 0
  type        = "zip"
  source_dir  = "${local.phase3_repo_root}/lambdas/redshift_sfn_stream_router"
  output_path = "${path.module}/.build/redshift_sfn_stream_router.zip"
}

resource "aws_iam_role" "redshift_sfn_stream_router" {
  count = local.redshift_sfn_stream_router_deploy ? 1 : 0
  name  = "${local.name_prefix}-redshift-sfn-stream-router"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "redshift_sfn_stream_router_logs" {
  count      = local.redshift_sfn_stream_router_deploy ? 1 : 0
  role       = aws_iam_role.redshift_sfn_stream_router[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "redshift_sfn_stream_router_sfn" {
  count = local.redshift_sfn_stream_router_deploy ? 1 : 0
  name  = "sfn-start-copy-gold"
  role  = aws_iam_role.redshift_sfn_stream_router[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["states:StartExecution"]
      Resource = compact([
        try(aws_sfn_state_machine.pipeline_copy[0].arn, null),
        try(aws_sfn_state_machine.pipeline_gold[0].arn, null),
      ])
    }]
  })
}

resource "aws_iam_role_policy" "redshift_sfn_stream_router_ddb_stream" {
  count = local.redshift_sfn_stream_router_deploy ? 1 : 0
  name  = "ddb-stream-read"
  role  = aws_iam_role.redshift_sfn_stream_router[0].id
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

resource "aws_lambda_function" "redshift_sfn_stream_router" {
  count            = local.redshift_sfn_stream_router_deploy ? 1 : 0
  filename         = data.archive_file.zip_redshift_sfn_stream_router[0].output_path
  function_name    = "${local.name_prefix}-redshift-sfn-stream-router"
  role             = aws_iam_role.redshift_sfn_stream_router[0].arn
  handler          = "main.handler"
  runtime          = "python3.12"
  timeout          = 120
  source_code_hash = data.archive_file.zip_redshift_sfn_stream_router[0].output_base64sha256

  environment {
    variables = {
      PROJECT                         = var.project
      ENVIRONMENT                     = var.environment
      PIPELINE_RUNS_TABLE             = data.terraform_remote_state.dynamo_platform[0].outputs.dynamodb_table_name
      PIPELINE_COPY_STATE_MACHINE_ARN = try(aws_sfn_state_machine.pipeline_copy[0].arn, "")
      PIPELINE_GOLD_STATE_MACHINE_ARN = try(aws_sfn_state_machine.pipeline_gold[0].arn, "")
    }
  }

  depends_on = [
    aws_sfn_state_machine.pipeline_copy,
    aws_sfn_state_machine.pipeline_gold,
  ]
}

resource "aws_lambda_event_source_mapping" "redshift_sfn_stream_router" {
  count                              = local.redshift_sfn_stream_router_deploy ? 1 : 0
  event_source_arn                   = data.terraform_remote_state.dynamo_platform[0].outputs.dynamodb_stream_arn
  function_name                      = aws_lambda_function.redshift_sfn_stream_router[0].arn
  starting_position                  = "LATEST"
  batch_size                         = 10
  maximum_batching_window_in_seconds = 5
  bisect_batch_on_function_error     = true

  depends_on = [aws_lambda_function.redshift_sfn_stream_router]
}
