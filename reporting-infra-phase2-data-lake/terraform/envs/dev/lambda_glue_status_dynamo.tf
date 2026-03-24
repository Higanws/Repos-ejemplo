data "archive_file" "zip_glue_status_dynamo" {
  count       = var.enable_pipeline_dynamo ? 1 : 0
  type        = "zip"
  source_dir  = "${local.phase2_repo_root}/lambdas/glue_job_status_dynamo"
  output_path = "${path.module}/.build/glue_job_status_dynamo.zip"
}

resource "aws_iam_role" "lambda_glue_status_dynamo" {
  count = var.enable_pipeline_dynamo ? 1 : 0
  name  = "${local.name_prefix}-glue-status-dynamo"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "glue_status_logs" {
  count      = var.enable_pipeline_dynamo ? 1 : 0
  role       = aws_iam_role.lambda_glue_status_dynamo[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "glue_status_get_job_run" {
  count = var.enable_pipeline_dynamo ? 1 : 0
  name  = "glue-get-job-run"
  role  = aws_iam_role.lambda_glue_status_dynamo[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["glue:GetJobRun"]
      Resource = "*"
    }]
  })
}

resource "aws_iam_role_policy" "glue_status_start_next" {
  count = var.enable_pipeline_dynamo && var.glue_auto_chain_to_next_job && !var.enable_pipeline_ddb_stream_chain ? 1 : 0
  name  = "glue-start-next-job"
  role  = aws_iam_role.lambda_glue_status_dynamo[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["glue:StartJobRun"]
      Resource = aws_glue_job.standardized_to_silver.arn
    }]
  })
}

resource "aws_iam_role_policy_attachment" "glue_status_dynamo_table" {
  count      = var.enable_pipeline_dynamo ? 1 : 0
  role       = aws_iam_role.lambda_glue_status_dynamo[0].name
  policy_arn = data.terraform_remote_state.dynamo_platform[0].outputs.iam_policy_pipeline_runs_arn
}

resource "aws_lambda_function" "glue_status_dynamo" {
  count            = var.enable_pipeline_dynamo ? 1 : 0
  filename         = data.archive_file.zip_glue_status_dynamo[0].output_path
  function_name    = "${local.name_prefix}-glue-job-status-dynamo"
  role             = aws_iam_role.lambda_glue_status_dynamo[0].arn
  handler          = "main.handler"
  runtime          = "python3.12"
  timeout          = 60
  source_code_hash = data.archive_file.zip_glue_status_dynamo[0].output_base64sha256

  environment {
    variables = merge(
      {
        PIPELINE_RUNS_TABLE = data.terraform_remote_state.dynamo_platform[0].outputs.dynamodb_table_name
        PROJECT             = var.project
        ENVIRONMENT         = var.environment
      },
      var.enable_pipeline_dynamo ? {
        GLUE_SELF_REPORTS_PIPELINE_STATE = "true"
      } : {},
      var.glue_auto_chain_to_next_job && !var.enable_pipeline_ddb_stream_chain ? {
        GLUE_JOB_NAME_STD_TO_SILVER = aws_glue_job.standardized_to_silver.name
      } : {}
    )
  }

  depends_on = [aws_iam_role_policy_attachment.glue_status_logs]
}

resource "aws_cloudwatch_event_rule" "glue_job_state" {
  count       = var.enable_pipeline_dynamo ? 1 : 0
  name        = "${local.name_prefix}-glue-job-state-to-dynamo"
  description = "Glue SUCCEEDED/FAILED → capa en DynamoDB"
  event_pattern = jsonencode({
    source      = ["aws.glue"]
    detail-type = ["Glue Job State Change"]
    detail = {
      state = ["SUCCEEDED", "FAILED"]
      jobName = [{ prefix = "${local.name_prefix}-glue-" }]
    }
  })
}

resource "aws_cloudwatch_event_target" "glue_job_state_lambda" {
  count     = var.enable_pipeline_dynamo ? 1 : 0
  rule      = aws_cloudwatch_event_rule.glue_job_state[0].name
  target_id = "GlueStatusToDynamo"
  arn       = aws_lambda_function.glue_status_dynamo[0].arn
}

resource "aws_lambda_permission" "allow_eventbridge_glue_status" {
  count         = var.enable_pipeline_dynamo ? 1 : 0
  statement_id  = "AllowExecutionFromEventBridgeGlueStatus"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.glue_status_dynamo[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.glue_job_state[0].arn
}
