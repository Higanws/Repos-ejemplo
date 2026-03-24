data "archive_file" "zip_redshift_sql" {
  type        = "zip"
  source_dir  = "${local.phase3_repo_root}/lambdas/redshift_sql"
  output_path = "${path.module}/.build/redshift_sql.zip"
  excludes    = ["__pycache__", ".pytest_cache"]
}

resource "aws_lambda_function" "redshift_sql" {
  filename         = data.archive_file.zip_redshift_sql.output_path
  function_name    = "${local.name_prefix}-run-redshift-sql"
  role             = aws_iam_role.lambda_redshift_sql.arn
  handler          = "main.handler"
  runtime          = "python3.11"
  timeout          = 300
  source_code_hash = data.archive_file.zip_redshift_sql.output_base64sha256

  environment {
    variables = local.lambda_redshift_sql_env
  }

  depends_on = [aws_redshiftserverless_workgroup.main]
}
