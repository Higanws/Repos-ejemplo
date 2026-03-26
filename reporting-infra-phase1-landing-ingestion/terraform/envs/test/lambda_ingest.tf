data "archive_file" "zip_raw_ingest" {
  type        = "zip"
  source_dir  = "${local.phase1_repo_root}/lambdas/raw_ingestion"
  output_path = "${path.module}/.build/raw_ingest.zip"
  excludes = [
    "requirements.txt",
    "__pycache__",
    ".pytest_cache",
  ]
}

resource "aws_lambda_function" "raw_ingest" {
  filename         = data.archive_file.zip_raw_ingest.output_path
  function_name    = "${local.name_prefix}-run-raw-api-ingestion"
  role             = aws_iam_role.lambda_raw_ingest.arn
  handler          = "handler.handler"
  runtime          = "python3.11"
  timeout          = 180
  source_code_hash = data.archive_file.zip_raw_ingest.output_base64sha256

  environment {
    variables = {
      RAW_BUCKET  = aws_s3_bucket.raw.bucket
      ENVIRONMENT = var.environment
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda_raw_ingest]
}
