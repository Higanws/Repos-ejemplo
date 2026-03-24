data "archive_file" "dynamo_archive_zip" {
  count       = var.enable_archive_lambda ? 1 : 0
  type        = "zip"
  source_file = "${path.module}/../../../lambdas/dynamo_archive_job/main.py"
  output_path = "${path.module}/.build/dynamo_archive_job.zip"
}

resource "aws_lambda_function" "dynamo_archive" {
  count            = var.enable_archive_lambda ? 1 : 0
  function_name    = "${local.name_prefix}-dynamo-archive-job"
  role             = aws_iam_role.lambda_archive[0].arn
  handler          = "main.handler"
  runtime          = "python3.12"
  timeout          = 900
  filename         = data.archive_file.dynamo_archive_zip[0].output_path
  source_code_hash = data.archive_file.dynamo_archive_zip[0].output_base64sha256

  environment {
    variables = {
      TABLE_NAME     = aws_dynamodb_table.pipeline_runs.name
      ARCHIVE_BUCKET = aws_s3_bucket.dynamo_archive.bucket
      ENV_KEY        = local.env_key
      GSI_NAME       = "gsi_env_business_date"
      RETENTION_DAYS = tostring(var.retention_days)
    }
  }

  depends_on = [aws_iam_role_policy_attachment.lambda_archive_basic]
}

resource "aws_cloudwatch_event_rule" "archive_weekly" {
  count               = var.enable_archive_lambda ? 1 : 0
  name                = "${local.name_prefix}-dynamo-archive-weekly"
  description         = "Archivo semanal de corridas antiguas (UTC)"
  schedule_expression = var.archive_schedule_cron
}

resource "aws_cloudwatch_event_target" "archive_weekly" {
  count     = var.enable_archive_lambda ? 1 : 0
  rule      = aws_cloudwatch_event_rule.archive_weekly[0].name
  target_id = "DynamoArchiveLambda"
  arn       = aws_lambda_function.dynamo_archive[0].arn
}

resource "aws_lambda_permission" "allow_eventbridge_archive" {
  count         = var.enable_archive_lambda ? 1 : 0
  statement_id  = "AllowExecutionFromEventBridgeArchive"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.dynamo_archive[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.archive_weekly[0].arn
}
