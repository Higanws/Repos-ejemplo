data "archive_file" "zip_glue_schema" {
  type        = "zip"
  source_file = "${local.phase2_repo_root}/lambdas/glue_schema_athena/main.py"
  output_path = "${path.module}/.build/glue_schema.zip"
}

resource "aws_lambda_function" "glue_schema" {
  filename         = data.archive_file.zip_glue_schema.output_path
  function_name    = "${local.name_prefix}-run-glue-schema-sql"
  role             = aws_iam_role.lambda_glue_schema.arn
  handler          = "main.handler"
  runtime          = "python3.11"
  timeout          = 300
  source_code_hash = data.archive_file.zip_glue_schema.output_base64sha256

  environment {
    variables = {
      ARTIFACTS_BUCKET    = aws_s3_bucket.artifacts.bucket
      RAW_BUCKET          = data.aws_s3_bucket.raw.bucket
      STANDARDIZED_BUCKET = aws_s3_bucket.standardized.bucket
      SILVER_BUCKET       = aws_s3_bucket.silver.bucket
      ATHENA_WORKGROUP    = aws_athena_workgroup.ddl.name
      ATHENA_OUTPUT_S3    = "s3://${aws_s3_bucket.athena_results.bucket}/output/"
    }
  }
}
